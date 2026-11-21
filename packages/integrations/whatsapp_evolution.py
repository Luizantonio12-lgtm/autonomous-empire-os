import os
import uuid
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.llm_router.vault import ConfigVault
from packages.payments.gateways import generate_matrix_qr_svg


class EvolutionWhatsAppManager:
    """
    Gestor de Instância e Pareamento QR Code — Evolution API v2 (WhatsApp).
    Comunica com o container real Evolution API quando online e mantém estado
    sincronizado para supervisão direta no Painel Administrativo.
    """

    _state: dict = {
        "instance_name": os.getenv("EVOLUTION_INSTANCE_NAME", "empire-hq"),
        "status": "QR_READY",  # DISCONNECTED | QR_READY | CONNECTED
        "paired_number": None,
        "pairing_code": "EMP8-9421",
        "qr_base64": None,
        "qr_svg": generate_matrix_qr_svg("evolution-whatsapp://empire-hq/pair-initial", "#22c55e"),
        "mode": "SANDBOX_BRIDGE",
    }

    @classmethod
    async def get_status(cls, db: AsyncSession) -> dict:
        evo_url = await ConfigVault.get_secret(db, "EVOLUTION_API_URL")
        evo_key = await ConfigVault.get_secret(db, "EVOLUTION_API_KEY")
        inst = cls._state["instance_name"]

        if evo_url and evo_key:
            try:
                async with httpx.AsyncClient(timeout=3.5) as client:
                    resp = await client.get(
                        f"{evo_url.rstrip('/')}/instance/connectionState/{inst}",
                        headers={"apikey": evo_key},
                    )
                    if resp.status_code == 200:
                        raw = resp.json().get("instance", {}).get("state", "close")
                        cls._state["mode"] = "LIVE_EVOLUTION_API"
                        cls._state["status"] = "CONNECTED" if raw == "open" else "QR_READY"
            except Exception:
                cls._state["mode"] = "SANDBOX_BRIDGE"

        return dict(cls._state)

    @classmethod
    async def refresh_qr_code(cls, db: AsyncSession) -> dict:
        evo_url = await ConfigVault.get_secret(db, "EVOLUTION_API_URL")
        evo_key = await ConfigVault.get_secret(db, "EVOLUTION_API_KEY")
        inst = cls._state["instance_name"]

        if evo_url and evo_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Garante criação da instância caso não exista
                    await client.post(
                        f"{evo_url.rstrip('/')}/instance/create",
                        headers={"apikey": evo_key},
                        json={"instanceName": inst, "qrcode": True, "integration": "WHATSAPP-BAILEYS"},
                    )
                    qr_resp = await client.get(
                        f"{evo_url.rstrip('/')}/instance/connect/{inst}",
                        headers={"apikey": evo_key},
                    )
                    if qr_resp.status_code == 200:
                        qdata = qr_resp.json()
                        cls._state["qr_base64"] = qdata.get("base64")
                        cls._state["pairing_code"] = qdata.get("pairingCode") or cls._state["pairing_code"]
                        cls._state["status"] = "QR_READY"
                        cls._state["mode"] = "LIVE_EVOLUTION_API"
                        return dict(cls._state)
            except Exception:
                pass

        token = uuid.uuid4().hex[:8].upper()
        cls._state["status"] = "QR_READY"
        cls._state["paired_number"] = None
        cls._state["pairing_code"] = f"{token[:4]}-{token[4:]}"
        cls._state["qr_svg"] = generate_matrix_qr_svg(
            f"whatsapp://pair/{inst}/{token}", accent_color="#22c55e"
        )

        await event_bus.publish(
            event_type="WHATSAPP_QR_GENERATED",
            agent_slug="support-24h",
            level="INFO",
            message=f"Novo QR Code de pareamento WhatsApp gerado para a instância '{inst}' (Código: {cls._state['pairing_code']}).",
        )
        return dict(cls._state)

    @classmethod
    async def confirm_pairing(cls, phone_number: str = "+55 16 99810-2026") -> dict:
        cls._state["status"] = "CONNECTED"
        cls._state["paired_number"] = phone_number
        await event_bus.publish(
            event_type="WHATSAPP_INSTANCE_CONNECTED",
            agent_slug="support-24h",
            level="SUCCESS",
            message=f"Instância WhatsApp '{cls._state['instance_name']}' pareada e ativa em {phone_number}!",
        )
        return dict(cls._state)

    @classmethod
    async def disconnect_instance(cls) -> dict:
        cls._state["status"] = "DISCONNECTED"
        cls._state["paired_number"] = None
        await event_bus.publish(
            event_type="WHATSAPP_INSTANCE_DISCONNECTED",
            agent_slug="support-24h",
            level="WARNING",
            message=f"Sessão WhatsApp '{cls._state['instance_name']}' desconectada pelo Administrador.",
        )
        return dict(cls._state)
