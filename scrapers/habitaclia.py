"""
Scraper per Habitaclia (annunci affitto Barcellona).
Habitaclia renderizza gli annunci lato server con markup schema.org/Product
(article[itemscope]) e classi CSS stabili (list-item-*), quindi il parsing e'
piu diretto rispetto a Fotocasa.

Nota: l'ordinamento di default non e' "piu recenti" e cambiare l'ordine via query
string non ha effetto (il sort e' gestito client-side). Per non perdere annunci
nuovi si scansionano le prime N pagine ad ogni esecuzione e si fa affidamento sul
dedup (seen_listings.json) lato pipeline.
"""
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.habitaclia.com/alquiler-barcelona.htm"
PAGES_TO_SCAN = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

FEATURES_RE = re.compile(r"(\d+)\s*m2?\s*-\s*(\d+)\s*habitacion", re.IGNORECASE)
PRICE_RE = re.compile(r"([\d.,]+)\s*€")


def _page_url(page: int) -> str:
    if page == 1:
        return BASE_URL
    return BASE_URL.replace(".htm", f"-{page}.htm")


def _parse_card(article) -> dict | None:
    listing_id = article.get("data-id")
    href = article.get("data-href")
    if not listing_id or not href:
        return None

    title_el = article.select_one("h3.list-item-title a")
    title = title_el.get_text(strip=True) if title_el else None

    zone_el = article.select_one("p.list-item-location span")
    zone = zone_el.get_text(strip=True) if zone_el else None
    if zone and zone.lower().startswith("barcelona -"):
        zone = zone.split("-", 1)[1].strip()

    feature_el = article.select_one("p.list-item-feature")
    feature_text = feature_el.get_text(" ", strip=True) if feature_el else ""
    features_match = FEATURES_RE.search(feature_text)
    size_m2 = int(features_match.group(1)) if features_match else None
    rooms = int(features_match.group(2)) if features_match else None

    desc_el = article.select_one("p.list-item-description")
    description = desc_el.get_text(strip=True) if desc_el else None

    price_el = article.select_one("article.list-item-price")
    price = None
    if price_el:
        price_text = price_el.get_text(" ", strip=True)
        price_match = PRICE_RE.search(price_text)
        if price_match:
            price = int(price_match.group(1).replace(".", "").replace(",", ""))

    return {
        "id": f"habitaclia-{listing_id}",
        "source": "habitaclia",
        "url": href.split("?")[0],
        "title": title,
        "zone": zone,
        "price_eur": price,
        "rooms": rooms,
        "size_m2": size_m2,
        "furnished": None,  # non deducibile dalla card, richiederebbe la pagina di dettaglio
        "amenities": {},
        "description": description,
        "raw_text": feature_text,
    }


def fetch_listings(pages: int = PAGES_TO_SCAN, timeout: int = 20) -> list[dict]:
    listings = []
    seen_ids_this_run = set()
    for page in range(1, pages + 1):
        resp = requests.get(_page_url(page), headers=HEADERS, timeout=timeout)
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        articles = soup.select("article[itemscope]")
        if not articles:
            break

        new_on_this_page = 0
        for article in articles:
            parsed = _parse_card(article)
            if parsed and parsed["id"] not in seen_ids_this_run:
                seen_ids_this_run.add(parsed["id"])
                listings.append(parsed)
                new_on_this_page += 1

        if new_on_this_page == 0:
            break

    return listings


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_listings(), indent=2, ensure_ascii=False))
