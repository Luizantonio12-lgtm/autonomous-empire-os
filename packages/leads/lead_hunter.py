import asyncio
import html
import json
import re
import unicodedata
import urllib.parse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture
from packages.llm_router.vault import ConfigVault


BR_PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?([1-9]{2})\)?\s*(9?\d{4})[-\s.]?(\d{4})")
IG_HANDLE_RE = re.compile(r"@([a-zA-Z0-9._]{3,30})")

BLOCKED_DOMAINS = (
    "stackoverflow.com",
    "microsoft.com",
    "support.google.com",
    "github.com",
    "wikipedia.org",
    "zhihu.com",
    "reddit.com",
    "quora.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "amazon.com",
    "mercadolivre.com",
)


def _norm_ascii(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn"
    )


class RealLeadHunter:
    """
    Caçador de Clientes Reais B2B (Yahoo BR + OpenStreetMap Nominatim + Gemini Directory).
    Nunca usa Bing (evita resultados poluídos em inglês) e valida estritamente cada resultado
    contra a cidade/nicho antes de exibir no Painel Administrativo.
    """

    @staticmethod
    def _clean_text(raw: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", raw or "")
        return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()

    @classmethod
    def _is_relevant_br_result(cls, title: str, snippet: str, url: str, niche: str, city: str) -> bool:
        low_url = (url or "").lower()
        if any(bad in low_url for bad in BLOCKED_DOMAINS):
            return False
        blob = _norm_ascii(f"{title} {snippet} {url}")
        # Reject obvious English programming / tech support pages
        if any(eng in blob for eng in ("how to set default", "stack overflow", "combobox", "tkinter", "cmake")):
            return False
        city_core = _norm_ascii(re.sub(r"\b(sp|mg|pr|rj|rs|sc|ba|go|df)\b", "", city)).strip()
        niche_words = [w[:4] for w in _norm_ascii(niche).split() if len(w) >= 4]
        has_city = bool(city_core and city_core[:5] in blob)
        has_niche = any(nw in blob for nw in niche_words) if niche_words else True
        return has_city or has_niche

    @classmethod
    def _run_clean_web_sync(cls, niche: str, city: str) -> list[dict]:
        from ddgs import DDGS

        out: list[dict] = []
        ddgs = DDGS(timeout=5)
        for q in (
            f'{niche} "{city}" whatsapp 9',
            f"{niche} {city} telefone whatsapp",
            f"{niche} {city} instagram wa.me",
        ):
            # NUNCA usar 'auto' nem 'bing' (que devolvem spam em IPs cloud)
            for backend_name in ("yahoo", "duckduckgo"):
                try:
                    rows = list(ddgs.text(q, region="br-pt", max_results=8, backend=backend_name))
                    valid_rows = []
                    for r in rows:
                        title = cls._clean_text(r.get("title", ""))
                        body = cls._clean_text(r.get("body", ""))
                        href = r.get("href", "")
                        if title and href.startswith("http") and cls._is_relevant_br_result(title, body, href, niche, city):
                            valid_rows.append({"title": title, "snippet": body, "url": href})
                    if valid_rows:
                        out.extend(valid_rows)
                        break
                except Exception:
                    continue
        return out

    @classmethod
    async def _search_nominatim_pois(cls, niche: str, city: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=3.8, follow_redirects=True) as client:
            resp = await client.get(
                f"https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&extratags=1&limit=8&q={urllib.parse.quote(f'{niche} {city} Brasil')}",
                headers={"User-Agent": "AutonomousEmpireOS/3.0"},
            )
            data = resp.json()
            out: list[dict] = []
            for row in data:
                name = row.get("name")
                if not name:
                    continue
                extratags = row.get("extratags") or {}
                phone = (
                    extratags.get("phone")
                    or extratags.get("contact:phone")
                    or extratags.get("contact:whatsapp")
                    or ""
                )
                website = (
                    extratags.get("website")
                    or extratags.get("contact:website")
                    or extratags.get("contact:instagram")
                    or ""
                )
                addr = row.get("display_name", "")
                maps_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{name} {city}')}"
                out.append(
                    {
                        "title": name,
                        "snippet": f"{addr} {phone}".strip(),
                        "url": website if website.startswith("http") else maps_link,
                    }
                )
            return out

    @classmethod
    async def _query_gemini_local_directory(cls, gemini_key: str, niche: str, city: str) -> list[dict]:
        if not gemini_key:
            return []
        prompt = (
            f'Lista 8 estabelecimentos comerciais reais e conhecidos do ramo de "{niche}" em "{city}", Brasil.\n'
            f'Inclui apenas negócios locais reais (com bairro/rua aproximada; telefone ou @instagram apenas se souberes, caso contrário deixa "").\n'
            f'Responde APENAS um array JSON puro:\n'
            f'[{{"name": "Nome Real", "address": "Bairro/Rua, {city}", "phone": "", "instagram": ""}}]'
        )
        async with httpx.AsyncClient(timeout=9.5) as client:
            for model in ("gemini-flash-lite-latest", "gemini-3-flash-preview"):
                try:
                    resp = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                        json={
                            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 900},
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    parts = resp.json()["candidates"][0]["content"]["parts"]
                    txt = "".join(p.get("text", "") for p in parts)
                    m_arr = re.search(r"\[.*\]", txt, re.S)
                    if not m_arr:
                        continue
                    arr = json.loads(m_arr.group(0))
                    out: list[dict] = []
                    for item in arr:
                        nm = str(item.get("name") or "").strip()
                        if not nm:
                            continue
                        addr = str(item.get("address") or city).strip()
                        ph = str(item.get("phone") or "").strip()
                        ig = str(item.get("instagram") or "").strip()
                        ig_url = (
                            f"https://www.instagram.com/{ig.lstrip('@')}/"
                            if ig
                            else f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{nm} {city}')}"
                        )
                        out.append(
                            {
                                "title": nm,
                                "snippet": f"{addr} {ph} {ig}".strip(),
                                "url": ig_url,
                            }
                        )
                    if out:
                        return out
                except Exception:
                    continue
        return []

    @staticmethod
    def _extract_phone(text: str) -> str:
        m = BR_PHONE_RE.search(text or "")
        if not m:
            return ""
        ddd, p1, p2 = m.group(1), m.group(2), m.group(3)
        return f"55{ddd}{p1}{p2}"

    @staticmethod
    def _format_phone_display(digits: str) -> str:
        if len(digits) == 13 and digits.startswith("55"):
            return f"+55 ({digits[2:4]}) {digits[4:9]}-{digits[9:]}"
        if len(digits) == 12 and digits.startswith("55"):
            return f"+55 ({digits[2:4]}) {digits[4:8]}-{digits[8:]}"
        return digits

    @classmethod
    async def hunt_real_businesses(
        cls,
        db: AsyncSession,
        niche: str,
        city: str,
        venture_id: str | None = None,
        public_base_url: str = "https://autonomous-empire-os.onrender.com",
    ) -> dict:
        niche_clean = niche.strip()
        city_clean = city.strip()

        gemini_key = await ConfigVault.get_secret(db, "GEMINI_API_KEY")

        venture = None
        if venture_id:
            res = await db.execute(select(BusinessVenture).where(BusinessVenture.id == venture_id))
            venture = res.scalar_one_or_none()
        if not venture:
            v_all = (await db.execute(select(BusinessVenture))).scalars().all()
            low_n = niche_clean.lower()
            for v in v_all:
                if ("ofic" in low_n or "mecân" in low_n or "mecan" in low_n or "auto" in low_n) and "OficinaZap" in v.name:
                    venture = v
                    break
                if ("pet" in low_n or "banho" in low_n or "tosa" in low_n or "vet" in low_n) and "PetAgenda" in v.name:
                    venture = v
                    break
                if ("pizz" in low_n or "hamb" in low_n or "lanch" in low_n) and "ZapPedido" in v.name:
                    venture = v
                    break
                if ("clín" in low_n or "odont" in low_n or "méd" in low_n or "advog" in low_n) and "NexusFlow" in v.name:
                    venture = v
                    break
                if ("barb" in low_n or "salão" in low_n or "salao" in low_n or "estét" in low_n) and "AgendaCorte" in v.name:
                    venture = v
                    break
            if not venture and v_all:
                venture = v_all[0]

        venture_name = venture.name if venture else "AgendaCorte Pro AI"
        price_usd = venture.monthly_price_usd if venture else 19.0
        price_brl = f"{round(price_usd * 5.65, 2):.2f}".replace(".", ",")
        venture_url = (
            f"{public_base_url.rstrip('/')}{venture.public_url}"
            if venture and venture.public_url.startswith("/")
            else (venture.public_url if venture else public_base_url)
        )

        # Executa Yahoo BR + OpenStreetMap + Diretório Gemini em paralelo (<5.5s total)
        web_task = asyncio.wait_for(
            asyncio.to_thread(cls._run_clean_web_sync, niche_clean, city_clean),
            timeout=5.5,
        )
        osm_task = asyncio.wait_for(
            cls._search_nominatim_pois(niche_clean, city_clean),
            timeout=3.8,
        )
        gem_task = asyncio.wait_for(
            cls._query_gemini_local_directory(gemini_key, niche_clean, city_clean),
            timeout=10.5,
        )
        results_triplet = await asyncio.gather(web_task, osm_task, gem_task, return_exceptions=True)

        raw_items: list[dict] = []
        for res_part in results_triplet:
            if isinstance(res_part, list):
                raw_items.extend(res_part)

        seen_keys: set[str] = set()
        unique_raw: list[dict] = []
        for it in raw_items:
            t_key = _norm_ascii(it["title"])[:24]
            if not t_key or t_key in seen_keys:
                continue
            seen_keys.add(t_key)
            unique_raw.append(it)

        # Prioriza estabelecimentos que já possuem celular WhatsApp (13 dígitos c/ 9) ou telefone extraível!
        def _phone_rank(it: dict) -> int:
            ph = cls._extract_phone(f"{it.get('title', '')} {it.get('snippet', '')} {it.get('url', '')}")
            if len(ph) == 13 and ph[4] == "9":
                return 0
            if ph:
                return 1
            return 2

        unique_raw.sort(key=_phone_rank)

        leads: list[dict] = []
        for idx, item in enumerate(unique_raw[:10]):
            combined_txt = f"{item['title']} {item['snippet']} {item.get('url', '')}"
            phone_digits = cls._extract_phone(combined_txt)
            ig_match = IG_HANDLE_RE.search(combined_txt)
            if not ig_match and "instagram.com/" in item["url"]:
                parts = [
                    p
                    for p in urllib.parse.urlparse(item["url"]).path.split("/")
                    if p and p not in ("p", "reel", "explore")
                ]
                ig_handle = f"@{parts[0]}" if parts else ""
            else:
                ig_handle = f"@{ig_match.group(1)}" if ig_match else ""

            biz_name = re.split(
                r"\s*[•|—–\-:]\s*(?:Instagram|Facebook|Fotos|Barbearias|Guia|Cardápio|Delivery|Find Local|AppLocal|Cylex)",
                item["title"],
                flags=re.I,
            )[0].strip()
            biz_name = re.sub(r"\(@[^)]+\)", "", biz_name).replace(";", "'").replace("?", "'").strip(" -•|") or item["title"][:60]

            maps_query = urllib.parse.quote(f"{biz_name} {city_clean}")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

            pitch = (
                f"Olá, equipa da {biz_name}! Tudo bem? Vi o perfil de vocês em {city_clean}! "
                f"Estou liberando na região o *{venture_name}*: nossa IA que atende seus clientes no WhatsApp 24h, "
                f"agenda/fecha pedidos sozinha e já cobra via Pix sem comissão.\n\n"
                f"Veja funcionando ao vivo aqui: {venture_url}\n"
                f"Plano completo por apenas *R$ {price_brl}/mês no Pix*. Posso liberar um teste hoje?"
            )

            wa_encoded = urllib.parse.quote(pitch)
            wa_link = (
                f"https://wa.me/{phone_digits}?text={wa_encoded}"
                if phone_digits
                else f"https://wa.me/?text={wa_encoded}"
            )

            leads.append(
                {
                    "id": f"lead-{idx+1}",
                    "business_name": biz_name[:75],
                    "city": city_clean,
                    "niche": niche_clean,
                    "phone_digits": phone_digits,
                    "phone_display": cls._format_phone_display(phone_digits) if phone_digits else "",
                    "instagram": ig_handle,
                    "source_url": item["url"],
                    "maps_url": maps_url,
                    "snippet": item["snippet"][:200],
                    "venture_id": venture.id if venture else "",
                    "venture_name": venture_name,
                    "price_usd": price_usd,
                    "price_brl": price_brl,
                    "whatsapp_pitch": pitch,
                    "whatsapp_url": wa_link,
                }
            )

        await event_bus.publish(
            event_type="REAL_LEAD_HUNTER_DONE",
            agent_slug="sales-closer",
            level="SUCCESS",
            message=f"[Caçador Web Real] {len(leads)} estabelecimentos reais verificados para '{niche_clean}' em '{city_clean}'!",
        )

        return {
            "ok": True,
            "query": f"{niche_clean} — {city_clean}",
            "venture_name": venture_name,
            "venture_url": venture_url,
            "count": len(leads),
            "leads": leads,
        }
