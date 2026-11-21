import os
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models import RuntimeVault

SUPPORTED_VAULT_KEYS = [
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ASAAS_API_KEY",
    "STRIPE_SECRET_KEY",
    "CEO_WHATSAPP_NUMBER",
    "EVOLUTION_API_URL",
    "EVOLUTION_API_KEY",
    "VERCEL_TOKEN",
]


class ConfigVault:
    """
    Cofre Runtime de Credenciais.
    Permite injetar ou rodar chaves de API em quente pelo Painel ADM (sem reiniciar containers),
    com fallback automático para variáveis de ambiente (.env).
    """

    @staticmethod
    def _mask(val: str) -> str:
        if not val:
            return ""
        if val.startswith("http") or val.startswith("+") or val.isdigit():
            return val
        if len(val) <= 8:
            return "••••••••"
        return f"{val[:4]}••••••••{val[-4:]}"

    @classmethod
    async def get_secret(cls, db: AsyncSession, key_name: str) -> str:
        res = await db.execute(select(RuntimeVault).where(RuntimeVault.key_name == key_name))
        row = res.scalar_one_or_none()
        if row and row.secret_value.strip():
            return row.secret_value.strip()
        return os.getenv(key_name, "").strip()

    @classmethod
    async def set_secret(cls, db: AsyncSession, key_name: str, value: str) -> None:
        if key_name not in SUPPORTED_VAULT_KEYS:
            raise ValueError(f"Chave não suportada pelo Cofre: {key_name}")
        res = await db.execute(select(RuntimeVault).where(RuntimeVault.key_name == key_name))
        row = res.scalar_one_or_none()
        clean_val = value.strip()
        if not clean_val:
            if row:
                await db.delete(row)
                await db.commit()
            return

        if row:
            row.secret_value = clean_val
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(RuntimeVault(key_name=key_name, secret_value=clean_val))
        await db.commit()

    @classmethod
    async def list_status(cls, db: AsyncSession) -> list[dict]:
        res = await db.execute(select(RuntimeVault))
        db_map = {r.key_name: r.secret_value for r in res.scalars().all()}
        items = []
        for k in SUPPORTED_VAULT_KEYS:
            raw = db_map.get(k) or os.getenv(k, "")
            items.append(
                {
                    "key_name": k,
                    "configured": bool(raw.strip()),
                    "masked_value": cls._mask(raw.strip()) if raw.strip() else None,
                    "source": "VAULT_DB" if k in db_map else ("ENV" if os.getenv(k) else "UNSET"),
                }
            )
        return items
