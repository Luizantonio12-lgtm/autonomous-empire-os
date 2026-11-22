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

// Guarda APENAS os números/JIDs comerciais abordados pelos Agentes (protege conversas pessoais do dono!)
const commercialContacts = new Set();

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

function extractMessageText(msg) {
  const m = msg?.message;
  if (!m) return '';
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
    }
    fs.mkdirSync(AUTH_DIR, { recursive: true });

    connectionStatus = 'CONNECTING';
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    let version;
    try {
      const waWeb = typeof fetchLatestWaWebVersion === 'function' ? await fetchLatestWaWebVersion() : null;
      version = waWeb && waWeb.version ? waWeb.version : (await fetchLatestBaileysVersion()).version;
    } catch (_) {
      version = (await fetchLatestBaileysVersion()).version;
    }

    sock = makeWASocket({
      version,
      auth: state,
      logger: pino({ level: 'silent' }),
      browser: Browsers.ubuntu('Chrome'),
      printQRInTerminal: false,
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    let pairingRequested = false;

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        try {
          currentQrSvg = await QRCode.toString(qr, { type: 'svg', margin: 1, width: 220 });
          if (connectionStatus !== 'PAIRING_CODE_READY') {
            connectionStatus = 'QR_READY';
          }
        } catch (_) {}

        if (pairingPhone && !pairingRequested && !sock.authState.creds.registered) {
          pairingRequested = true;
          try {
            const rawCode = await sock.requestPairingCode(pairingPhone);
            currentPairingCode =
              rawCode && rawCode.length === 8 ? `${rawCode.slice(0, 4)}-${rawCode.slice(4)}` : rawCode;
            connectionStatus = 'PAIRING_CODE_READY';
          } catch (err) {
            console.error('Pairing code error:', err?.message);
          }
        }
      }

      if (connection === 'open') {
        connectionStatus = 'CONNECTED';
        currentQrSvg = '';
        currentPairingCode = '';
        const meId = sock?.user?.id || '';
        connectedPhone = meId.split(':')[0].split('@')[0] || connectedPhone;
        console.log('[WA-BRIDGE] WhatsApp REAL conectado:', connectedPhone);
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const loggedOut = statusCode === DisconnectReason.loggedOut;
        if (loggedOut) {
          clearAuthDir();
          connectionStatus = 'DISCONNECTED';
          connectedPhone = '';
        } else {
          connectionStatus = 'DISCONNECTED';
          // Reconexão suave caso já tivesse sessão registada
          if (fs.existsSync(path.join(AUTH_DIR, 'creds.json'))) {
            setTimeout(() => startSocket({ resetAuth: false }), 4000);
          }
        }
      }
    });

    // Recebe respostas dos clientes abordados e aciona o Closer IA + Pix Asaas!
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify') return;
      for (const msg of messages || []) {
        if (!msg?.message || msg.key.fromMe) continue;
        const remoteJid = msg.key.remoteJid || '';
        if (!remoteJid || remoteJid.endsWith('@g.us') || remoteJid === 'status@broadcast') continue;

        const text = extractMessageText(msg);
        if (!text) continue;

        const senderDigits = remoteJid.split('@')[0].split(':')[0];
        const low = text.toLowerCase();
        const mentionsProduct =
          low.includes('agendacorte') ||
          low.includes('zappedido') ||
          low.includes('nexusflow') ||
          low.includes('sistema ia') ||
          low.includes('teste hoje');

        // Só responde automaticamente se for um cliente comercial abordado pelos agentes (ou que citou nossos produtos)
        if (!commercialContacts.has(remoteJid) && !commercialContacts.has(senderDigits) && !mentionsProduct) {
          continue;
        }

        const pushName = msg.pushName || `Cliente ${senderDigits}`;
        const replyData = await postJsonLocal('/api/webhooks/wa-bridge-inbound', {
          remote_jid: remoteJid,
          phone: senderDigits,
          contact_name: pushName,
          message: text,
        });

        if (replyData && replyData.auto_reply && sock && connectionStatus === 'CONNECTED') {
          try {
            await sock.sendPresenceUpdate('composing', remoteJid);
            await new Promise((r) => setTimeout(r, 1800));
            await sock.sendMessage(remoteJid, { text: replyData.auto_reply });
            await sock.sendPresenceUpdate('paused', remoteJid);
            sentCount += 1;
          } catch (e) {
            console.error('[WA-BRIDGE] Auto-reply send error:', e?.message);
          }
        }
      }
    });
  } finally {
    starting = false;
  }
}

// Se já existir credencial salva em disco, reconecta ao arrancar
if (fs.existsSync(path.join(AUTH_DIR, 'creds.json'))) {
  startSocket({ resetAuth: false });
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
      })
    );
  }

  if (req.method === 'POST' && req.url === '/connect-qr') {
    await startSocket({ resetAuth: connectionStatus === 'DISCONNECTED' });
    // Aguarda até 4s pelo primeiro QR
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
      })
    );
  }

  if (req.method === 'POST' && req.url === '/pair-code') {
    const body = await readJson(req);
    const digits = cleanDigits(body.phone);
    if (digits.length < 12) {
      res.statusCode = 400;
      return res.end(JSON.stringify({ ok: false, error: 'Informe DDD + Número (ex: 5517999999999)' }));
    }
    await startSocket({ resetAuth: true, pairingPhone: digits });
    for (let i = 0; i < 28; i++) {
      if (currentPairingCode || connectionStatus === 'CONNECTED') break;
      await new Promise((r) => setTimeout(r, 300));
    }
    return res.end(
      JSON.stringify({
        ok: true,
        status: connectionStatus,
        pairing_code: currentPairingCode,
        phone: digits,
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
      // Verifica se o número comercial (mesmo fixo c/ WhatsApp Business, ou c/ e s/ 9º dígito BR) tem WhatsApp ativo!
      const candidates = [digits];
      if (digits.startsWith('55') && digits.length === 13 && digits[4] === '9') {
        candidates.push('55' + digits.slice(2, 4) + digits.slice(5));
      } else if (digits.startsWith('55') && digits.length === 12) {
        candidates.push('55' + digits.slice(2, 4) + '9' + digits.slice(4));
      }

      let targetJid = null;
      for (const cand of candidates) {
        const check = await sock.onWhatsApp(cand);
        if (check && check[0] && check[0].exists) {
          targetJid = check[0].jid;
          break;
        }
      }

      if (!targetJid) {
        return res.end(JSON.stringify({ ok: false, exists: false, reason: 'NO_WHATSAPP_ACCOUNT' }));
      }

      commercialContacts.add(targetJid);
      commercialContacts.add(targetJid.split('@')[0]);
      commercialContacts.add(digits);

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

  if (req.method === 'POST' && req.url === '/disconnect') {
    try {
      if (sock) await sock.logout();
    } catch (_) {}
    clearAuthDir();
    sock = null;
    connectionStatus = 'DISCONNECTED';
    connectedPhone = '';
    currentQrSvg = '';
    currentPairingCode = '';
    return res.end(JSON.stringify({ ok: true, status: 'DISCONNECTED' }));
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ ok: false, error: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[WA-BRIDGE] Microserviço Baileys Real ativo em http://127.0.0.1:${PORT}`);
});
