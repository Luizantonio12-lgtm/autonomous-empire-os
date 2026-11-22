import base64
import html
import json
import re
import urllib.parse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture
from packages.llm_router import MultiModelLLMGateway


BR_PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?([1-9]{2})\)?\s*(9?\d{4})[-\s.]?(\d{4})")
IG_HANDLE_RE = re.compile(r"@([a-zA-Z0-9._]{3,30})")


class RealLeadHunter:
    """
    Caçador de Clientes Reais B2B (DuckDuckGo Web + OpenStreetMap Nominatim + Gemini 3 Flash).
    Pesquisa estabelecimentos reais existentes no Brasil sem inventar leads fictícios,
    extraindo links oficiais, telefones públicos, Google Maps e script pronto p/ WhatsApp.
    """

    @staticmethod
    def _clean_html(raw: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", raw or "")
        return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()

    @staticmethod
    def _extract_ddg_url(href: str) -> str:
        if href.startswith("//"):
            href = "https:" + href
        if "uddg=" in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if parsed.get("uddg"):
                return parsed["uddg"][0]
        return href

    @classmethod
    async def _scrape_ddg_html(cls, client: httpx.AsyncClient, query: str) -> list[dict]:
        resp = await client.get(
            f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        text = resp.text
        results: list[dict] = []
        # Match <a ... class="result__a" ... href="..."> or href before class
        for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, re.S):
            raw_href, raw_title = m.group(1), m.group(2)
            tail = text[m.end() : m.end() + 1800]
            m_snip = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', tail, re.S)
            snippet = cls._clean_html(m_snip.group(1)) if m_snip else ""
            title = cls._clean_html(raw_title)
            clean_url = cls._extract_ddg_url(html.unescape(raw_href))
            if title and clean_url.startswith("http"):
                results.append({"title": title, "snippet": snippet, "url": clean_url})
            if len(results) >= 10:
                break
        return results

    @classmethod
    async def _scrape_ddg_lite(cls, client: httpx.AsyncClient, query: str) -> list[dict]:
        resp = await client.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        text = resp.text
        results: list[dict] = []
        for m in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*class=[\"']result-link[\"'][^>]*>(.*?)</a>", text, re.S):
            raw_href, raw_title = m.group(1), m.group(2)
            tail = text[m.end() : m.end() + 1400]
            m_snip = re.search(r"class=[\"']result-snippet[\"'][^>]*>(.*?)</td>", tail, re.S)
            snippet = cls._clean_html(m_snip.group(1)) if m_snip else ""
            title = cls._clean_html(raw_title)
            clean_url = cls._extract_ddg_url(html.unescape(raw_href))
            if title and clean_url.startswith("http"):
                results.append({"title": title, "snippet": snippet, "url": clean_url})
            if len(results) >= 10:
                break
        return results

    @classmethod
    async def _search_nominatim_pois(cls, client: httpx.AsyncClient, niche: str, city: str) -> list[dict]:
        resp = await client.get(
            f"https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&extratags=1&limit=10&q={urllib.parse.quote(f'{niche} {city} Brasil')}",
            headers={"User-Agent": "AutonomousEmpireOS/3.0"},
        )
        data = resp.json()
        out: list[dict] = []
        for row in data:
            name = row.get("name")
            if not name:
                continue
            extratags = row.get("extratags") or {}
            phone = extratags.get("phone") or extratags.get("contact:phone") or extratags.get("contact:whatsapp") or ""
            website = extratags.get("website") or extratags.get("contact:website") or extratags.get("contact:instagram") or ""
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

        venture = None
        if venture_id:
            res = await db.execute(select(BusinessVenture).where(BusinessVenture.id == venture_id))
            venture = res.scalar_one_or_none()
        if not venture:
            res = await db.execute(select(BusinessVenture).limit(1))
            venture = res.scalar_one_or_none()

        venture_name = venture.name if venture else "AgendaCorte Pro AI"
        price_usd = venture.monthly_price_usd if venture else 19.0
        price_brl = f"{round(price_usd * 5.65, 2):.2f}".replace(".", ",")
        venture_url = (
            f"{public_base_url.rstrip('/')}{venture.public_url}"
            if venture and venture.public_url.startswith("/")
            else (venture.public_url if venture else public_base_url)
        )

        await event_bus.publish(
            event_type="REAL_LEAD_HUNTER_START",
            agent_slug="sales-closer",
            level="INFO",
            message=f"[Caçador Web Real] Buscando estabelecimentos reais de '{niche_clean}' em '{city_clean}'...",
        )

        raw_items: list[dict] = []
        async with httpx.AsyncClient(timeout=16.0, follow_redirects=True) as client:
            for q in (
                f"{niche_clean} {city_clean} telefone whatsapp",
                f"{niche_clean} {city_clean} instagram",
            ):
                try:
                    items = await cls._scrape_ddg_html(client, q)
                    if not items:
                        items = await cls._scrape_ddg_lite(client, q)
                    raw_items.extend(items)
                except Exception:
                    continue

            try:
                osm_items = await cls._search_nominatim_pois(client, niche_clean, city_clean)
                raw_items.extend(osm_items)
            except Exception:
                pass

            if len(raw_items) < 4:
                try:
                    bing_resp = await client.get(
                        f"https://www.bing.com/search?q={urllib.parse.quote(f'{niche_clean} \"{city_clean}\" whatsapp instagram')}&setlang=pt-br&cc=BR",
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                            ),
                            "Accept-Language": "pt-BR,pt;q=0.9",
                        },
                    )
                    for blk in re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', bing_resp.text, re.S)[:10]:
                        m_b = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
                        if not m_b:
                            continue
                        b_href = html.unescape(m_b.group(1))
                        if "u=a1" in b_href:
                            u_val = urllib.parse.parse_qs(urllib.parse.urlparse(b_href).query).get("u", [""])[0][2:]
                            u_val += "=" * (-len(u_val) % 4)
                            try:
                                b_href = base64.urlsafe_b64decode(u_val).decode("utf-8", "ignore")
                            except Exception:
                                pass
                        m_p = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
                        raw_items.append(
                            {
                                "title": cls._clean_html(m_b.group(2)),
                                "snippet": cls._clean_html(m_p.group(1)) if m_p else "",
                                "url": b_href,
                            }
                        )
                except Exception:
                    pass

        seen_keys: set[str] = set()
        unique_raw: list[dict] = []
        for it in raw_items:
            u_key = it["url"].split("?")[0].rstrip("/").lower()
            t_key = it["title"][:28].lower()
            if u_key in seen_keys or t_key in seen_keys:
                continue
            seen_keys.add(u_key)
            seen_keys.add(t_key)
            unique_raw.append(it)
            if len(unique_raw) >= 12:
                break

        leads: list[dict] = []
        for idx, item in enumerate(unique_raw[:10]):
            combined_txt = f"{item['title']} {item['snippet']}"
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
                r"\s*[•|—–\-:]\s*(?:Instagram|Facebook|Fotos|Barbearias|Guia|Cardápio|Delivery)",
                item["title"],
                flags=re.I,
            )[0].strip()
            biz_name = re.sub(r"\(@[^)]+\)", "", biz_name).strip(" -•|") or item["title"][:60]

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
            message=f"[Caçador Web Real] {len(leads)} estabelecimentos reais encontrados para '{niche_clean}' em '{city_clean}'!",
        )

        return {
            "ok": True,
            "query": f"{niche_clean} — {city_clean}",
            "venture_name": venture_name,
            "venture_url": venture_url,
            "count": len(leads),
            "leads": leads,
        }
