import base64
import hashlib
import hmac
import json
import os
import struct
import time
import uuid
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, SecurityAuditLog
from packages.payments.gateways import generate_matrix_qr_svg


class SovereignSecurityGuard:
    """
    Segurança Soberana do CEO:
      - Autenticação JWT (HS256, RFC 7519)
      - 2FA TOTP de 6 dígitos (RFC 6238 — compatível Google Authenticator / 1Password)
      - Global Emergency Kill-Switch (congelamento instantâneo de todos os agentes e custos)
      - Registo de Auditoria de Segurança (SecurityAuditLog)
    """

    _jwt_secret: str = os.getenv("EMPIRE_JWT_SECRET", "empire-sovereign-jwt-master-key-2026")
    _ceo_password_hash: str = hashlib.sha256(
        os.getenv("EMPIRE_CEO_PASSWORD", "empire2026").encode("utf-8")
    ).hexdigest()
    # Base32 Secret compatível com Google Authenticator (RFC 3548)
    _totp_secret_b32: str = os.getenv("EMPIRE_TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    _require_2fa: bool = True
    _kill_switch_active: bool = False

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        pad = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + pad)

    @classmethod
    def generate_totp(cls, timestamp: float | None = None, interval: int = 30) -> str:
        """Gera código TOTP 6 dígitos oficial RFC 6238."""
        ts = int((timestamp if timestamp is not None else time.time()) // interval)
        key = base64.b32decode(cls._totp_secret_b32.upper(), casefold=True)
        msg = struct.pack(">Q", ts)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        return f"{code:06d}"

    @classmethod
    def verify_totp(cls, code: str) -> bool:
        clean = (code or "").strip().replace(" ", "")
        if len(clean) != 6 or not clean.isdigit():
            return False
        now = time.time()
        for drift in (-30, 0, 30):
            if hmac.compare_digest(cls.generate_totp(now + drift), clean):
                return True
        return False

    @classmethod
    def issue_jwt(cls, subject: str = "CEO_SOVEREIGN", ttl_seconds: int = 14400) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "sub": subject,
            "role": "EMPIRE_OWNER",
            "iat": now,
            "exp": now + ttl_seconds,
            "jti": uuid.uuid4().hex[:12],
        }
        h_b64 = cls._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_b64 = cls._b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        sig = hmac.new(cls._jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        return f"{h_b64}.{p_b64}.{cls._b64url_encode(sig)}"

    @classmethod
    def verify_jwt(cls, token: str) -> dict | None:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
            expected_sig = hmac.new(
                cls._jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
            ).digest()
            if not hmac.compare_digest(cls._b64url_encode(expected_sig), parts[2]):
                return None
            payload = json.loads(cls._b64url_decode(parts[1]).decode("utf-8"))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            return payload
        except Exception:
            return None

    @classmethod
    def get_security_overview(cls) -> dict:
        # Nunca divulgar segredo 2FA, URI de provisionamento, código atual ou senha.
        return {
            "kill_switch_active": cls._kill_switch_active,
            "require_2fa": cls._require_2fa,
        }

    @classmethod
    async def authenticate_ceo(
        cls,
        db: AsyncSession,
        password: str,
        totp_code: str,
        ip_hint: str = "127.0.0.1",
    ) -> dict:
        pwd_hash = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        if not hmac.compare_digest(pwd_hash, cls._ceo_password_hash):
            await cls.log_audit(db, "AUTH_FAILED_PASSWORD", "Tentativa de login CEO com senha incorreta.", ip_hint)
            raise ValueError("Credencial Mestre inválida.")

        if cls._require_2fa and not cls.verify_totp(totp_code):
            await cls.log_audit(db, "AUTH_FAILED_2FA", "Código TOTP 2FA inválido ou expirado.", ip_hint)
            raise ValueError("Código 2FA TOTP inválido.")

        token = cls.issue_jwt("CEO_SOVEREIGN")
        await cls.log_audit(db, "AUTH_SUCCESS_JWT_2FA", "Sessão Soberana CEO autenticada via Senha + TOTP 2FA.", ip_hint)
        await event_bus.publish(
            event_type="SECURITY_CEO_LOGIN",
            agent_slug="master-orchestrator",
            level="SUCCESS",
            message="Sessão Soberana CEO validada com JWT HS256 + TOTP 2FA.",
        )
        return {"token": token, "role": "EMPIRE_OWNER"}

    @classmethod
    async def toggle_kill_switch(cls, db: AsyncSession, engage: bool) -> dict:
        cls._kill_switch_active = engage
        target_status = "PAUSED" if engage else "IDLE"
        await db.execute(update(AgentRegistry).values(status=target_status))
        await db.commit()

        action = "KILL_SWITCH_ENGAGED" if engage else "KILL_SWITCH_RELEASED"
        msg = (
            "GLOBAL KILL-SWITCH ATIVADO! Todos os agentes, crons autónomos e chamadas pagas foram congelados instantaneamente."
            if engage
            else "Kill-Switch desativado. Todos os departamentos retomaram prontidão operacional (IDLE)."
        )
        await cls.log_audit(db, action, msg)
        await event_bus.publish(
            event_type=action,
            agent_slug="master-orchestrator",
            level="ERROR" if engage else "SUCCESS",
            message=msg,
        )
        return {"kill_switch_active": cls._kill_switch_active, "agents_status": target_status}

    @classmethod
    async def log_audit(
        cls,
        db: AsyncSession,
        action: str,
        details: str,
        ip_hint: str = "127.0.0.1",
    ) -> None:
        entry = SecurityAuditLog(
            id=f"sec-{uuid.uuid4().hex[:10]}",
            action=action,
            actor="CEO_SOVEREIGN",
            ip_hint=ip_hint,
            details=details,
        )
        db.add(entry)
        await db.commit()
