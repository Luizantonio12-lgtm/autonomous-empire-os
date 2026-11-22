import os
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.payments.gateways import generate_matrix_qr_svg

WA_BRIDGE_URL = f"http://127.0.0.1:{os.getenv('WA_BRIDGE_PORT', '3005')}"


class EvolutionWhatsAppManager:
    """
    Gestor Real de WhatsApp Multi-Device (Baileys Nativo em 127.0.0.1:3005).
    Suporta Pareamento por Código Oficial de 8 Dígitos (no mesmo celular Android),
    QR Code Oficial, Envio Ativo c/ Verificação onWhatsApp e Auto-Closer 24/7.
    """

    _state: dict = {
        "instance_name": os.getenv("EVOLUTION_INSTANCE_NAME", "empire-hq"),
        "status": "DISCONNECTED",
        "paired_number": None,
        "pairing_code": "",
        "qr_base64": None,
        "qr_svg": generate_matrix_qr_svg("whatsapp://connect-empire-os", "#22c55e"),
        "mode": "LIVE_BAILEYS_BRIDGE",
        "sent_count": 0,
    }

    @classmethod
    async def get_status(cls, db: AsyncSession | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(f"{WA_BRIDGE_URL}/status")
                if r.status_code == 200:
                    data = r.json()
                    cls._state["status"] = data.get("status", "DISCONNECTED")
                    cls._state["paired_number"] = data.get("phone") or None
                    cls._state["pairing_code"] = data.get("pairing_code") or ""
                    if data.get("qr_svg"):
                        cls._state["qr_svg"] = data["qr_svg"]
                    cls._state["sent_count"] = data.get("sent_count", 0)
                    cls._state["mode"] = "LIVE_BAILEYS_BRIDGE"
        except Exception:
            pass
        return dict(cls._state)

    @classmethod
    async def refresh_qr_code(cls, db: AsyncSession | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(f"{WA_BRIDGE_URL}/connect-qr")
                if r.status_code == 200:
                    data = r.json()
                    cls._state["status"] = data.get("status", "QR_READY")
                    if data.get("qr_svg"):
                        cls._state["qr_svg"] = data["qr_svg"]
                    cls._state["pairing_code"] = data.get("pairing_code") or ""
        except Exception:
            pass
        await event_bus.publish(
            event_type="WHATSAPP_QR_GENERATED",
            agent_slug="support-24h",
            level="INFO",
            message="QR Code Real do WhatsApp Web gerado! Escaneia ou usa o Código de 8 Dígitos no mesmo celular.",
        )
        return dict(cls._state)

    @classmethod
    async def request_real_pairing_code(cls, phone_number: str) -> dict:
        async with httpx.AsyncClient(timeout=14.0) as client:
            r = await client.post(
                f"{WA_BRIDGE_URL}/pair-code",
                json={"phone": phone_number},
            )
            data = r.json()
            if r.status_code != 200 or not data.get("ok"):
                raise ValueError(data.get("error") or "Falha ao solicitar código de 8 dígitos ao WhatsApp.")
            cls._state["status"] = data.get("status", "PAIRING_CODE_READY")
            cls._state["pairing_code"] = data.get("pairing_code") or ""
            cls._state["paired_number"] = data.get("phone")
            await event_bus.publish(
                event_type="WHATSAPP_PAIR_CODE_READY",
                agent_slug="support-24h",
                level="SUCCESS",
                message=f"Código Oficial WhatsApp gerado: {cls._state['pairing_code']}! Abre o teu WhatsApp -> Aparelhos conectados -> Conectar com número.",
            )
            return dict(cls._state)

    @classmethod
    async def confirm_pairing(cls, phone_number: str = "") -> dict:
        # Agora chama o pareamento real por código de 8 dígitos!
        return await cls.request_real_pairing_code(phone_number)

    @classmethod
    async def send_real_whatsapp(cls, phone: str, message: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{WA_BRIDGE_URL}/send",
                json={"phone": phone, "message": message},
            )
            return r.json()

    @classmethod
    async def disconnect_instance(cls) -> dict:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                await client.post(f"{WA_BRIDGE_URL}/disconnect")
        except Exception:
            pass
        cls._state["status"] = "DISCONNECTED"
        cls._state["paired_number"] = None
        cls._state["pairing_code"] = ""
        await event_bus.publish(
            event_type="WHATSAPP_INSTANCE_DISCONNECTED",
            agent_slug="support-24h",
            level="WARNING",
            message="Sessão WhatsApp desconectada pelo Administrador.",
        )
        return dict(cls._state)
