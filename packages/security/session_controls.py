"""Controles preliminares do painel. Devem ser homologados antes do deploy."""
import base64
import binascii
import hashlib
import hmac
import os
from urllib.parse import urlsplit

from packages.security.auth_guard import SovereignSecurityGuard

COOKIE_NAME = 'empire_admin'


def secure_credentials_configured() -> bool:
    password = os.environ.get('EMPIRE_CEO_PASSWORD', '')
    jwt_secret = os.environ.get('EMPIRE_JWT_SECRET', '')
    totp = os.environ.get('EMPIRE_TOTP_SECRET', '')
    if len(password) < 16 or len(jwt_secret) < 32 or len(totp) < 32:
        return False
    if password == 'empire2026' or totp == 'JBSWY3DPEHPK3PXP':
        return False
    try:
        if len(base64.b32decode(totp.upper(), casefold=True)) < 20:
            return False
    except (ValueError, binascii.Error):
        return False
    # Valores devem coincidir com os carregados no início do processo.
    return (hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), SovereignSecurityGuard._ceo_password_hash)
            and hmac.compare_digest(jwt_secret, SovereignSecurityGuard._jwt_secret)
            and hmac.compare_digest(totp, SovereignSecurityGuard._totp_secret_b32))


def valid_session(token: str | None) -> bool:
    if not secure_credentials_configured() or not token:
        return False
    claims = SovereignSecurityGuard.verify_jwt(token)
    return bool(claims and claims.get('sub') == 'CEO_SOVEREIGN' and claims.get('role') == 'EMPIRE_OWNER')


def valid_internal_secret(value: str | None) -> bool:
    secret = os.getenv('WA_INTERNAL_SECRET', '')
    return bool(len(secret) >= 32 and value and hmac.compare_digest(secret, value))


def same_origin(origin: str | None, host: str | None) -> bool:
    if not origin or not host:
        return False
    try:
        parts = urlsplit(origin)
        return (parts.scheme in ('http', 'https') and parts.netloc.lower() == host.lower()
                and parts.path in ('', '/') and not parts.query and not parts.fragment
                and '@' not in parts.netloc)
    except ValueError:
        return False
