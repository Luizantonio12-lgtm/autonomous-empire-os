const http = require('http');
const fs = require('fs');
const path = require('path');
const pino = require('pino');
const QRCode = require('qrcode');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  fetchLatestWaWebVersion,
  downloadMediaMessage,
  DisconnectReason,
  Browsers,
} = require('@whiskeysockets/baileys');

const PORT = parseInt(process.env.WA_BRIDGE_PORT || '3005', 10);
const API_PORT = process.env.PORT || '8000';
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, '..', '..', '.wa_auth');

let sock = null;
let connectionStatus = 'DISCONNECTED'; // DISCONNECTED | CONNECTING | QR_READY | PAIRING_CODE_READY | CONNECTED
let currentQrSvg = '';
let currentPairingCode = '';
let connectedPhone = '';
let sentCount = 0;
let starting = false;
let lastBridgeEvent = 'boot';
let lastBridgeError = '';
let reconnectTimer = null;
let ownerWelcomed = false;

// Guarda APENAS os números/JIDs comerciais abordados pelos Agentes (protege conversas pessoais do dono!)
const commercialContacts = new Set();
const commercialTails = new Set(); // últimos 8 dígitos (resolve 8 vs 9 dígitos no Brasil)
const answeredMsgIds = new Set();
const chatHistoryCache = new Map(); // remoteJid -> Array<msg>
let sweepingBacklog = false;
let triggerSweepFn = null;

const BOT_SIGNATURE_WORDS = [
  'agendacorte', 'zappedido', 'nexusflow', 'oficinazap', 'petagenda',
  'imobzap', 'autoestética', 'autoestetica', 'reativacliente', 'topmapa',
  'cobrafácil', 'cobrafacil', 'parceiroagência', 'parceiroagencia', 'trickspace',
  'diagnóstico rápido', 'diagnostico rapido', 'nota 0 a 10', 'whatsapp 24h',
  'pessoal da ', 'equipa da ', 'equipe da ', 'atendimento comercial pelo whatsapp',
];

const COMMERCIAL_REPLY_INTENTS = [
  'pode mandar', 'manda o diagnóstico', 'manda o diagnostico', 'manda aqui',
  'quero testar', 'quero conhecer', 'como funciona', 'qual o valor', 'quanto custa',
  'tenho interesse', 'pode liberar', 'manda o resumo',
];

function registerCommercial(idOrJid) {
  if (!idOrJid) return;
  const s = String(idOrJid).trim();
  if (!s) return;
  commercialContacts.add(s);
  const base = s.split('@')[0].split(':')[0];
  if (base) commercialContacts.add(base);
  const onlyDigits = base.replace(/\D/g, '');
  if (onlyDigits.length >= 8 && !s.endsWith('@lid')) {
    commercialContacts.add(onlyDigits);
    commercialTails.add(onlyDigits.slice(-8));
  }
}

function isOwnerSelf(jidOrDigits) {
  const d = String(jidOrDigits || '').split('@')[0].split(':')[0].replace(/\D/g, '');
  const own = String(connectedPhone || '5516993862008').replace(/\D/g, '');
  return d.length >= 8 && own.length >= 8 && d.slice(-8) === own.slice(-8);
}

function isKnownCommercial(remoteJid, altJid) {
  for (const candidate of [remoteJid, altJid]) {
    if (!candidate) continue;
    if (commercialContacts.has(candidate)) return true;
    const base = String(candidate).split('@')[0].split(':')[0];
    if (commercialContacts.has(base)) return true;
    if (!String(candidate).endsWith('@lid')) {
      const d = base.replace(/\D/g, '');
      if (d.length >= 8 && commercialTails.has(d.slice(-8))) return true;
    }
  }
  return false;
}

function getMsgTimestampSec(msg) {
  const t = msg?.messageTimestamp;
  if (!t) return 0;
  if (typeof t === 'number') return t;
  if (typeof t === 'object' && typeof t.low === 'number') return t.low;
  return Number(t) || 0;
}

function cleanDigits(raw) {
  let d = String(raw || '').replace(/\D/g, '');
  if (d.length === 10 || d.length === 11) {
    d = '55' + d;
  }
  return d;
}

function clearAuthDir() {
  try {
    if (fs.existsSync(AUTH_DIR)) {
      fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    }
  } catch (_) {}
}

function hasRegisteredCreds() {
  try {
    const credsPath = path.join(AUTH_DIR, 'creds.json');
    if (!fs.existsSync(credsPath)) return false;
    const data = JSON.parse(fs.readFileSync(credsPath, 'utf8'));
    return Boolean(data && (data.registered === true || data.account));
  } catch (_) {
    return false;
  }
}

function extractMessageText(msg) {
  const root = msg?.message;
  if (!root) return '';
  const m = root.ephemeralMessage?.message || root.viewOnceMessage?.message || root;
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    ''
  ).trim();
}

function postJsonLocal(urlPath, payload) {
  return new Promise((resolve) => {
    const body = Buffer.from(JSON.stringify(payload), 'utf8');
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port: parseInt(API_PORT, 10),
        path: urlPath,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': body.length,
        },
        timeout: 25000,
      },
      (res) => {
        let chunks = '';
        res.on('data', (c) => (chunks += c));
        res.on('end', () => {
          try {
            resolve(JSON.parse(chunks));
          } catch (_) {
            resolve(null);
          }
        });
      }
    );
    req.on('error', () => resolve(null));
    req.on('timeout', () => {
      req.destroy();
      resolve(null);
    });
    req.write(body);
    req.end();
  });
}

async function startSocket({ resetAuth = false, pairingPhone = null } = {}) {
  if (starting) return;
  starting = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  try {
    if (sock) {
      try {
        sock.ev.removeAllListeners();
        sock.end(undefined);
      } catch (_) {}
      sock = null;
    }
    if (resetAuth) {
      clearAuthDir();
      currentPairingCode = '';
      currentQrSvg = '';
      lastBridgeError = '';
    }
    fs.mkdirSync(AUTH_DIR, { recursive: true });

    connectionStatus = 'CONNECTING';
    lastBridgeEvent = resetAuth ? 'starting_fresh_socket' : 'reconnecting_saved_session';

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    let saveChain = Promise.resolve();
    let backupTimer = null;
    const syncAuthToCloudDb = () => {
      if (backupTimer) clearTimeout(backupTimer);
      backupTimer = setTimeout(() => {
        try {
          if (!hasRegisteredCreds()) return;
          const filesMap = {};
          for (const fname of fs.readdirSync(AUTH_DIR)) {
            if (fname.endsWith('.json')) {
              filesMap[fname] = fs.readFileSync(path.join(AUTH_DIR, fname), 'utf8');
            }
          }
          postJsonLocal('/api/internal/wa-auth-backup', { files: filesMap });
        } catch (_) {}
      }, 2500);
    };
    const enqueueSaveCreds = () => {
      saveChain = saveChain
        .then(() => saveCreds())
        .then(() => syncAuthToCloudDb())
        .catch((err) => {
          console.error('[WA-BRIDGE] saveCreds error:', err?.message);
        });
      return saveChain;
    };

    let version;
    try {
      const waWeb = typeof fetchLatestWaWebVersion === 'function' ? await fetchLatestWaWebVersion() : null;
      version = waWeb && waWeb.version ? waWeb.version : (await fetchLatestBaileysVersion()).version;
    } catch (_) {
      version = (await fetchLatestBaileysVersion()).version;
    }

    const activeSock = makeWASocket({
      version,
      auth: state,
      logger: pino({ level: 'silent' }),
      browser: Browsers.macOS('Chrome'),
      printQRInTerminal: false,
      syncFullHistory: true,
      markOnlineOnConnect: false,
    });
    sock = activeSock;

    let pairingRequested = false;

    // Telemetria dos frames de pareamento para diagnóstico em tempo real
    if (activeSock.ws && typeof activeSock.ws.on === 'function') {
      activeSock.ws.on('frame', (frame) => {
        try {
          if (frame?.tag === 'notification' && frame?.attrs?.type === 'link_code_companion_reg') {
            const child = Array.isArray(frame.content)
              ? frame.content.find((c) => c?.tag === 'link_code_companion_reg')
              : null;
            const stage = child?.attrs?.stage || 'ack_ref';
            lastBridgeEvent = `notif_link_code:${stage}`;
          } else if (frame?.tag === 'iq' && Array.isArray(frame.content)) {
            if (frame.content.some((c) => c?.tag === 'pair-success')) {
              lastBridgeEvent = 'pair_success_received';
            }
          }
        } catch (_) {}
      });
    }

    activeSock.ev.on('creds.update', () => {
      enqueueSaveCreds();
    });

    activeSock.ev.on('connection.update', async (update) => {
      if (activeSock !== sock) return;
      const { connection, lastDisconnect, qr, isNewLogin } = update;

      if (isNewLogin) {
        lastBridgeEvent = 'new_login_configured_awaiting_515';
      }

      if (qr) {
        try {
          currentQrSvg = await QRCode.toString(qr, { type: 'svg', margin: 1, width: 220 });
          if (connectionStatus !== 'PAIRING_CODE_READY') {
            connectionStatus = 'QR_READY';
          }
        } catch (_) {}

        if (pairingPhone && !pairingRequested && !activeSock.authState.creds.registered) {
          pairingRequested = true;
          try {
            lastBridgeEvent = `requesting_companion_hello:${pairingPhone}`;
            const rawCode = await activeSock.requestPairingCode(pairingPhone);
            currentPairingCode = String(rawCode || '')
              .replace(/[^A-Za-z0-9]/g, '')
              .toUpperCase();
            connectionStatus = 'PAIRING_CODE_READY';
            lastBridgeEvent = `companion_hello_accepted:${pairingPhone}`;
          } catch (err) {
            lastBridgeError = err?.message || 'PAIRING_CODE_FAILED';
            lastBridgeEvent = `companion_hello_error:${lastBridgeError}`;
            console.error('[WA-BRIDGE] Pairing code error:', lastBridgeError);
          }
        }
      }

      if (connection === 'open') {
        connectionStatus = 'CONNECTED';
        currentQrSvg = '';
        currentPairingCode = '';
        lastBridgeError = '';
        const meId = activeSock?.user?.id || activeSock?.authState?.creds?.me?.id || '';
        connectedPhone = meId.split(':')[0].split('@')[0] || connectedPhone;
        lastBridgeEvent = `connected:${connectedPhone}`;
        console.log('[WA-BRIDGE] WhatsApp REAL conectado:', connectedPhone);

        if (!ownerWelcomed && connectedPhone) {
          ownerWelcomed = true;
          setTimeout(async () => {
            try {
              if (sock && connectionStatus === 'CONNECTED') {
                const selfJid = `${connectedPhone}@s.whatsapp.net`;
                await sock.sendMessage(selfJid, {
                  text:
                    '✅ *[Empire OS • Alerta VIP CEO Ativado]*\n\n' +
                    'Seu sistema autônomo 24/7 já está conectado!\n' +
                    '• 🟡 Quando um cliente pedir Pix, você será avisado aqui.\n' +
                    '• 🟢 Quando um Pix cair no Asaas, a confirmação chega aqui na hora!',
                });
              }
            } catch (e) {
              console.error('[WA-BRIDGE] Self welcome error:', e?.message);
            }
          }, 3500);
        }
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const errMsg = lastDisconnect?.error?.message || '';
        const loggedOut = statusCode === DisconnectReason.loggedOut;
        const isRestartRequired = statusCode === DisconnectReason.restartRequired || statusCode === 515;

        await saveChain;

        if (loggedOut) {
          clearAuthDir();
          connectionStatus = 'DISCONNECTED';
          connectedPhone = '';
          currentPairingCode = '';
          lastBridgeEvent = `logged_out:${statusCode}`;
        } else if (isRestartRequired || hasRegisteredCreds()) {
          // 515 restartRequired logo após confirmar no celular -> reconecta imediatamente com as credenciais salvas!
          connectionStatus = 'CONNECTING';
          currentPairingCode = '';
          lastBridgeEvent = `restarting_authenticated_session:${statusCode || 515}`;
          const delayMs = isRestartRequired ? 400 : 2500;
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            startSocket({ resetAuth: false });
          }, delayMs);
        } else {
          // Sessão não concluída expirou (ex: 408 QR timeout): limpa credenciais parciais
          clearAuthDir();
          connectionStatus = 'DISCONNECTED';
          currentPairingCode = '';
          lastBridgeEvent = `unpaired_socket_closed:${statusCode || 'unknown'}:${errMsg}`;
        }
      }
    });

    async function processIncomingCustomerMsg(msg, { forceCommercial = false } = {}) {
      if (!msg?.message || msg.key?.fromMe) return false;
      const remoteJid = msg.key.remoteJid || '';
      if (!remoteJid || remoteJid.endsWith('@g.us') || remoteJid === 'status@broadcast') return false;
      const altJid = msg.key.remoteJidAlt || msg.key.participantAlt || msg.key.senderPn || '';
      if (isOwnerSelf(remoteJid) || isOwnerSelf(altJid)) return false;

      const msgId = msg.key.id || '';
      if (msgId && answeredMsgIds.has(msgId)) return false;

      const realPhoneRaw = (!remoteJid.endsWith('@lid') ? remoteJid : altJid || remoteJid)
        .split('@')[0]
        .split(':')[0];

      const audioMsg =
        msg.message?.audioMessage ||
        msg.message?.ephemeralMessage?.message?.audioMessage ||
        null;
      let text = extractMessageText(msg);
      let audioBase64 = '';
      let audioMime = 'audio/ogg';

      if (!text && !audioMsg) return false;

      const low = (text || '').toLowerCase();
      const mentionsProductOrIntent =
        BOT_SIGNATURE_WORDS.some((w) => low.includes(w)) ||
        COMMERCIAL_REPLY_INTENTS.some((w) => low.includes(w));

      if (!forceCommercial && !isKnownCommercial(remoteJid, altJid) && !mentionsProductOrIntent) {
        return false;
      }

      registerCommercial(remoteJid);
      if (altJid) registerCommercial(altJid);
      if (msgId) answeredMsgIds.add(msgId);

      if (!text && audioMsg && typeof downloadMediaMessage === 'function') {
        try {
          const buf = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { logger: pino({ level: 'silent' }), reuploadRequest: activeSock.updateMediaMessage }
          );
          if (buf && buf.length > 0 && buf.length <= 4 * 1024 * 1024) {
            audioBase64 = Buffer.from(buf).toString('base64');
            audioMime = String(audioMsg.mimetype || 'audio/ogg').split(';')[0].trim();
          }
        } catch (e) {
          console.error('[WA-BRIDGE] Audio download error:', e?.message);
        }
        if (!audioBase64) {
          text = '[Áudio recebido — pedir resumo rápido ou oferecer demonstração]';
        }
      }

      const pushName = msg.pushName || `Cliente ${realPhoneRaw}`;
      const replyData = await postJsonLocal('/api/webhooks/wa-bridge-inbound', {
        remote_jid: remoteJid,
        phone: realPhoneRaw,
        contact_name: pushName,
        message: text || '[ÁUDIO_WHATSAPP]',
        audio_base64: audioBase64,
        audio_mime: audioMime,
      });

      if (replyData && replyData.auto_reply && sock && connectionStatus === 'CONNECTED') {
        try {
          await sock.sendPresenceUpdate('composing', remoteJid);
          await new Promise((r) => setTimeout(r, 1800));
          await sock.sendMessage(remoteJid, { text: replyData.auto_reply });
          await sock.sendPresenceUpdate('paused', remoteJid);
          sentCount += 1;
          return true;
        } catch (e) {
          console.error('[WA-BRIDGE] Auto-reply send error:', e?.message);
        }
      }
      return false;
    }

    function indexHistoryMsg(msg) {
      if (!msg?.message || !msg.key?.remoteJid) return;
      const jid = msg.key.remoteJid;
      if (jid.endsWith('@g.us') || jid === 'status@broadcast' || isOwnerSelf(jid)) return;
      const altJid = msg.key.remoteJidAlt || msg.key.senderPn || '';
      if (msg.key.fromMe) {
        const myTxt = extractMessageText(msg).toLowerCase();
        if (BOT_SIGNATURE_WORDS.some((w) => myTxt.includes(w))) {
          registerCommercial(jid);
          if (altJid) registerCommercial(altJid);
        }
      }
      const arr = chatHistoryCache.get(jid) || [];
      if (!arr.some((x) => x.key?.id && x.key.id === msg.key.id)) {
        arr.push(msg);
        arr.sort((a, b) => getMsgTimestampSec(a) - getMsgTimestampSec(b));
        if (arr.length > 25) arr.splice(0, arr.length - 25);
        chatHistoryCache.set(jid, arr);
      }
    }

    async function sweepUnansweredCommercialChats() {
      if (sweepingBacklog || !sock || connectionStatus !== 'CONNECTED') return 0;
      sweepingBacklog = true;
      let answeredNow = 0;
      try {
        const nowSec = Math.floor(Date.now() / 1000);
        for (const [jid, msgs] of chatHistoryCache.entries()) {
          if (!msgs.length || answeredNow >= 15) continue;
          const lastMsg = msgs[msgs.length - 1];
          if (!lastMsg || lastMsg.key?.fromMe) continue;
          const ageSec = nowSec - getMsgTimestampSec(lastMsg);
          if (ageSec > 72 * 3600) continue; // ignora conversas com mais de 3 dias
          const altJid = lastMsg.key?.remoteJidAlt || lastMsg.key?.senderPn || '';
          const hadBotPitch = msgs.some(
            (m) => m.key?.fromMe && BOT_SIGNATURE_WORDS.some((w) => extractMessageText(m).toLowerCase().includes(w))
          );
          if (hadBotPitch || isKnownCommercial(jid, altJid)) {
            const ok = await processIncomingCustomerMsg(lastMsg, { forceCommercial: true });
            if (ok) {
              answeredNow += 1;
              await new Promise((r) => setTimeout(r, 4500));
            }
          }
        }
      } finally {
        sweepingBacklog = false;
      }
      return answeredNow;
    }
    triggerSweepFn = sweepUnansweredCommercialChats;

    activeSock.ev.on('messaging-history.set', ({ messages }) => {
      try {
        for (const m of messages || []) indexHistoryMsg(m);
        setTimeout(() => sweepUnansweredCommercialChats().catch(() => {}), 5000);
      } catch (_) {}
    });

    // Recebe respostas dos clientes abordados (tempo real + sincronização offline) e aciona o Closer IA + Pix Asaas!
    activeSock.ev.on('messages.upsert', async ({ messages, type }) => {
      for (const m of messages || []) indexHistoryMsg(m);
      if (type !== 'notify') {
        setTimeout(() => sweepUnansweredCommercialChats().catch(() => {}), 3500);
        return;
      }
      for (const msg of messages || []) {
        await processIncomingCustomerMsg(msg);
      }
    });
  } finally {
    starting = false;
  }
}

// Restaura backup criptografado do Banco Cloud com retentativas até o API Gateway subir!
function restoreFromCloudWithRetry(attemptsLeft = 40) {
  const req = http.get(
    { hostname: '127.0.0.1', port: parseInt(API_PORT, 10), path: '/api/internal/wa-auth-restore', timeout: 12000 },
    (res) => {
      let chunks = '';
      res.on('data', (c) => (chunks += c));
      res.on('end', () => {
        if (res.statusCode !== 200) {
          if (attemptsLeft > 1) setTimeout(() => restoreFromCloudWithRetry(attemptsLeft - 1), 3000);
          return;
        }
        try {
          const parsed = JSON.parse(chunks || '{}');
          if (Array.isArray(parsed?.known_contacts)) {
            for (const ph of parsed.known_contacts) registerCommercial(ph);
          }
          if (parsed && parsed.ok && parsed.files && parsed.files['creds.json']) {
            if (!hasRegisteredCreds()) {
              fs.mkdirSync(AUTH_DIR, { recursive: true });
              for (const [fn, content] of Object.entries(parsed.files)) {
                if (fn.endsWith('.json') && !fn.includes('/') && !fn.includes('..')) {
                  fs.writeFileSync(path.join(AUTH_DIR, fn), String(content), 'utf8');
                }
              }
            }
            if (hasRegisteredCreds() && connectionStatus === 'DISCONNECTED') {
              console.log('[WA-BRIDGE] Sessão WhatsApp restaurada automaticamente do Banco Neon Cloud!');
              startSocket({ resetAuth: false });
            }
          }
        } catch (_) {
          if (attemptsLeft > 1) setTimeout(() => restoreFromCloudWithRetry(attemptsLeft - 1), 3000);
        }
      });
    }
  );
  req.on('error', () => {
    if (attemptsLeft > 1) setTimeout(() => restoreFromCloudWithRetry(attemptsLeft - 1), 3000);
  });
}

if (hasRegisteredCreds()) {
  startSocket({ resetAuth: false });
  restoreFromCloudWithRetry(15);
} else {
  clearAuthDir();
  setTimeout(() => restoreFromCloudWithRetry(40), 2500);
}

function readJson(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      try {
        resolve(JSON.parse(body || '{}'));
      } catch (_) {
        resolve({});
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'GET' && req.url === '/status') {
    return res.end(
      JSON.stringify({
        ok: true,
        status: connectionStatus,
        phone: connectedPhone,
        qr_svg: currentQrSvg,
        pairing_code: currentPairingCode,
        sent_count: sentCount,
        tracked_leads: commercialContacts.size,
        last_event: lastBridgeEvent,
        last_error: lastBridgeError,
      })
    );
  }

  if (req.method === 'POST' && req.url === '/connect-qr') {
    if (connectionStatus === 'CONNECTED') {
      return res.end(
        JSON.stringify({
          ok: true,
          status: 'CONNECTED',
          phone: connectedPhone,
          already_connected: true,
          last_event: lastBridgeEvent,
        })
      );
    }
    await startSocket({ resetAuth: connectionStatus === 'DISCONNECTED' });
    for (let i = 0; i < 16; i++) {
      if (currentQrSvg || connectionStatus === 'CONNECTED') break;
      await new Promise((r) => setTimeout(r, 250));
    }
    return res.end(
      JSON.stringify({
        ok: true,
        status: connectionStatus,
        phone: connectedPhone,
        qr_svg: currentQrSvg,
        pairing_code: currentPairingCode,
        last_event: lastBridgeEvent,
      })
    );
  }

  if (req.method === 'POST' && req.url === '/pair-code') {
    const body = await readJson(req);
    if (connectionStatus === 'CONNECTED' && !body.force) {
      return res.end(
        JSON.stringify({
          ok: true,
          status: 'CONNECTED',
          phone: connectedPhone,
          pairing_code: '',
          already_connected: true,
          last_event: lastBridgeEvent,
        })
      );
    }
    const digits = cleanDigits(body.phone);
    if (digits.length < 12 || digits.length > 13) {
      res.statusCode = 400;
      return res.end(
        JSON.stringify({
          ok: false,
          error: 'Número inválido. Informe DDD + Número com 10 ou 11 dígitos (ex: 16 99386-2008).',
        })
      );
    }
    await startSocket({ resetAuth: true, pairingPhone: digits });
    for (let i = 0; i < 35; i++) {
      if (currentPairingCode || connectionStatus === 'CONNECTED' || lastBridgeError) break;
      await new Promise((r) => setTimeout(r, 300));
    }
    if (!currentPairingCode && lastBridgeError) {
      res.statusCode = 502;
      return res.end(
        JSON.stringify({
          ok: false,
          error: `WhatsApp rejeitou solicitação de código: ${lastBridgeError}`,
          last_event: lastBridgeEvent,
        })
      );
    }
    return res.end(
      JSON.stringify({
        ok: true,
        status: connectionStatus,
        pairing_code: currentPairingCode,
        phone: digits,
        last_event: lastBridgeEvent,
      })
    );
  }

  if (req.method === 'POST' && req.url === '/send') {
    if (!sock || connectionStatus !== 'CONNECTED') {
      res.statusCode = 409;
      return res.end(JSON.stringify({ ok: false, error: 'WHATSAPP_NOT_CONNECTED' }));
    }
    const body = await readJson(req);
    const digits = cleanDigits(body.phone);
    const message = String(body.message || '').trim();
    if (!digits || !message) {
      res.statusCode = 400;
      return res.end(JSON.stringify({ ok: false, error: 'Dados incompletos' }));
    }

    try {
      const candidates = [digits];
      if (digits.startsWith('55') && digits.length === 13 && digits[4] === '9') {
        candidates.push('55' + digits.slice(2, 4) + digits.slice(5));
      } else if (digits.startsWith('55') && digits.length === 12) {
        candidates.push('55' + digits.slice(2, 4) + '9' + digits.slice(4));
      }

      let targetJid = null;
      let targetLid = null;
      for (const cand of candidates) {
        const check = await sock.onWhatsApp(cand);
        if (check && check[0] && check[0].exists) {
          targetJid = check[0].jid;
          targetLid = check[0].lid || null;
          break;
        }
      }

      if (!targetJid) {
        return res.end(JSON.stringify({ ok: false, exists: false, reason: 'NO_WHATSAPP_ACCOUNT' }));
      }

      registerCommercial(targetJid);
      if (targetLid) registerCommercial(targetLid);
      registerCommercial(digits);

      await sock.sendPresenceUpdate('composing', targetJid);
      await new Promise((r) => setTimeout(r, 1400));
      await sock.sendMessage(targetJid, { text: message });
      await sock.sendPresenceUpdate('paused', targetJid);
      sentCount += 1;

      return res.end(JSON.stringify({ ok: true, exists: true, jid: targetJid, sent_count: sentCount }));
    } catch (err) {
      res.statusCode = 500;
      return res.end(JSON.stringify({ ok: false, error: err?.message || 'SEND_FAILED' }));
    }
  }

  if (req.method === 'POST' && req.url === '/notify-owner') {
    if (!sock || connectionStatus !== 'CONNECTED') {
      res.statusCode = 409;
      return res.end(JSON.stringify({ ok: false, error: 'WHATSAPP_NOT_CONNECTED' }));
    }
    const body = await readJson(req);
    const message = String(body.message || '').trim();
    const ownerDigits = cleanDigits(body.owner_phone || connectedPhone || '5516993862008');
    if (!message || !ownerDigits) {
      res.statusCode = 400;
      return res.end(JSON.stringify({ ok: false, error: 'Dados incompletos' }));
    }
    try {
      const selfJid = `${ownerDigits}@s.whatsapp.net`;
      await sock.sendMessage(selfJid, { text: message });
      return res.end(JSON.stringify({ ok: true, jid: selfJid }));
    } catch (err) {
      res.statusCode = 500;
      return res.end(JSON.stringify({ ok: false, error: err?.message || 'NOTIFY_OWNER_FAILED' }));
    }
  }

  if (req.method === 'POST' && req.url === '/sweep') {
    if (!sock || connectionStatus !== 'CONNECTED' || typeof triggerSweepFn !== 'function') {
      return res.end(JSON.stringify({ ok: false, error: 'WHATSAPP_NOT_CONNECTED', cached_chats: chatHistoryCache.size }));
    }
    const answered = await triggerSweepFn();
    return res.end(JSON.stringify({ ok: true, answered_now: answered, cached_chats: chatHistoryCache.size }));
  }

  if (req.method === 'POST' && req.url === '/disconnect') {
    try {
      if (sock) await sock.logout();
    } catch (_) {}
    clearAuthDir();
    postJsonLocal('/api/internal/wa-auth-backup', { files: {} });
    sock = null;
    ownerWelcomed = false;
    connectionStatus = 'DISCONNECTED';
    connectedPhone = '';
    currentQrSvg = '';
    currentPairingCode = '';
    lastBridgeEvent = 'disconnected_by_admin';
    return res.end(JSON.stringify({ ok: true, status: 'DISCONNECTED' }));
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ ok: false, error: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[WA-BRIDGE] Microserviço Baileys Real ativo em http://127.0.0.1:${PORT}`);
});
