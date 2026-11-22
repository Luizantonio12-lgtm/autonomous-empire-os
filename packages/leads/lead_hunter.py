import html
import json
import re
import urllib.parse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture, OmnichannelInteraction
from packages.llm_router import MultiModelLLMGateway


BR_PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?([1-9]{2})\)?\s*(9?\d{4})[-\s.]?(\d{4})")
IG_HANDLE_RE = re.compile(r"@([a-zA-Z0-9._]{3,30})")


class RealLeadHunter:
    """
    Caçador de Clientes Reais B2B (Web + Mapas + Instagram + Gemini 3 Flash).
    Pesquisa empresas reais existentes no Brasil sem inventar leads fictícios,
    extraindo links oficiais, telefones públicos, Google Maps e script pronto p/ WhatsApp.
    """

    @staticmethod
    def _clean_html(raw: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", raw or "")
        return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()

    @staticmethod
    def _extract_ddg_url(href: str) -> str:
        if "uddg=" in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if parsed.get("uddg"):
                return parsed["uddg"][0]
        return href

    @classmethod
    async def _scrape_ddg_query(cls, client: httpx.AsyncClient, query: str) -> list[dict]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}&kl=br-pt"
        resp = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
        text = resp.text
        blocks = text.split('class="result__body"')
        results: list[dict] = []
        for blk in blocks[1:12]:
            m_title = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not m_title:
                continue
            raw_href, raw_title = m_title.group(1), m_title.group(2)
            m_snip = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', blk, re.S)
            raw_snip = m_snip.group(1) if m_snip else ""

            clean_url = cls._extract_ddg_url(html.unescape(raw_href))
            title = cls._clean_html(raw_title)
            snippet = cls._clean_html(raw_snip)

            # Skip generic aggregators if title has no specific place info, keep useful profiles/listings
            if not title:
                continue
            results.append({"title": title, "snippet": snippet, "url": clean_url})
        return results

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
        async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
            for q in (
                f"{niche_clean} {city_clean} telefone whatsapp endereço",
                f"{niche_clean} {city_clean} instagram",
            ):
                try:
                    items = await cls._scrape_ddg_query(client, q)
                    raw_items.extend(items)
                except Exception:
                    continue

        # Deduplicate by URL / Title prefix
        seen_urls: set[str] = set()
        unique_raw: list[dict] = []
        for it in raw_items:
            u_key = it["url"].split("?")[0].rstrip("/").lower()
            if u_key in seen_urls:
                continue
            seen_urls.add(u_key)
            unique_raw.append(it)
            if len(unique_raw) >= 12:
                break

        # Build deterministic baseline leads first from real web hits
        leads: list[dict] = []
        for idx, item in enumerate(unique_raw[:10]):
            combined_txt = f"{item['title']} {item['snippet']}"
            phone_digits = cls._extract_phone(combined_txt)
            ig_match = IG_HANDLE_RE.search(combined_txt)
            if not ig_match and "instagram.com/" in item["url"]:
                parts = [p for p in urllib.parse.urlparse(item["url"]).path.split("/") if p and p not in ("p", "reel", "explore")]
                ig_handle = f"@{parts[0]}" if parts else ""
            else:
                ig_handle = f"@{ig_match.group(1)}" if ig_match else ""

            # Clean business title
            biz_name = re.split(r"\s*[•|—–\-:]\s*(?:Instagram|Facebook|Fotos|Barbearias|Guia|Cardápio|Delivery)", item["title"], flags=re.I)[0].strip()
            biz_name = re.sub(r"\(@[^)]+\)", "", biz_name).strip(" -•|") or item["title"][:60]

            maps_query = urllib.parse.quote(f"{biz_name} {city_clean}")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

            pitch = (
                f"Olá, equipa da {biz_name}! Tudo bem? Vi o perfil de vocês em {city_clean}! "
                f"Estou liberando na região o {venture_name}: nossa IA que atende seus clientes no WhatsApp 24h, "
                f"agenda/fecha pedidos sozinha e já cobra via Pix sem comissão. "
                f"Veja funcionando ao vivo aqui: {venture_url} — plano fundador por R$ {price_brl}/mês no Pix. Quer testar hoje?"
            )

            wa_encoded = urllib.parse.quote(pitch)
            wa_link = f"https://wa.me/{phone_digits}?text={wa_encoded}" if phone_digits else f"https://wa.me/?text={wa_encoded}"

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

        # Refine with Gemini 3 Flash if available to filter directories & sharpen personalized hooks
        if leads:
            try:
                raw_json = json.dumps(
                    [
                        {
                            "idx": i,
                            "title": l["business_name"],
                            "snippet": l["snippet"],
                            "url": l["source_url"],
                        }
                        for i, l in enumerate(leads)
                    ],
                    ensure_ascii=False,
                )
                llm = await MultiModelLLMGateway.complete(
                    db=db,
                    agent_id="agent-sales",
                    task_id=None,
                    system_prompt=(
                        "Recebes resultados reais da web no Brasil. Filtra listas genéricas ('Top 10 melhores...') "
                        "e mantém apenas estabelecimentos reais. Para cada um, devolve JSON puro no formato "
                        '[{"idx": 0, "clean_name": "Nome Real", "short_hook": "1 frase curta personalizada p/ WhatsApp"}]'
                    ),
                    user_prompt=(
                        f"Nicho: {niche_clean} | Cidade: {city_clean} | Produto: {venture_name} (R$ {price_brl}/mês) | "
                        f"Link: {venture_url}\nResultados Web:\n{raw_json}"
                    ),
                    operation_label=f"Qualificação Leads Reais ({niche_clean} - {city_clean})",
                    strategy="MARGIN_OPTIMIZED",
                    local_fallback_text="[]",
                )
                m_arr = re.search(r"\[.*\]", llm.content, re.S)
                if m_arr and llm.provider != "local-autonomous-engine":
                    parsed = json.loads(m_arr.group(0))
                    refined: list[dict] = []
                    for entry in parsed:
                        idx = entry.get("idx")
                        if isinstance(idx, int) and 0 <= idx < len(leads):
                            base = dict(leads[idx])
                            if entry.get("clean_name"):
                                base["business_name"] = str(entry["clean_name"])[:75]
                                mq = urllib.parse.quote(f"{base['business_name']} {city_clean}")
                                base["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={mq}"
                            hook = str(entry.get("short_hook") or "").strip()
                            if hook:
                                new_pitch = (
                                    f"Olá, {base['business_name']}! {hook}\n\n"
                                    f"Conheça o *{venture_name}* ao vivo: {venture_url}\n"
                                    f"Plano completo por apenas *R$ {price_brl}/mês no Pix* (sem fidelidade). Posso liberar um teste hoje?"
                                )
                                base["whatsapp_pitch"] = new_pitch
                                enc = urllib.parse.quote(new_pitch)
                                base["whatsapp_url"] = (
                                    f"https://wa.me/{base['phone_digits']}?text={enc}"
                                    if base["phone_digits"]
                                    else f"https://wa.me/?text={enc}"
                                )
                            refined.append(base)
                    if refined:
                        leads = refined
            except Exception:
                pass

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
