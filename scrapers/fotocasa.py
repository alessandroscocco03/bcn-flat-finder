"""
Scraper per Fotocasa (annunci affitto Barcellona).
Fotocasa renderizza gli annunci lato server nella pagina di ricerca (niente API JSON
separata individuata), ordinati di default per "Mas recientes" -> ci basta la prima
pagina ad ogni esecuzione periodica per intercettare i nuovi annunci.

Le classi CSS di Fotocasa sono utility-class generate (instabili), quindi il parsing
si basa su pattern piu stabili: struttura testuale delle card e URL degli annunci
(che contengono id numerico e uno slug con le dotazioni, es:
.../aire-acondicionado-calefaccion-terraza-ascensor-no-amueblado/190491036/d).
"""
import re
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.fotocasa.es/es/alquiler/viviendas/barcelona-capital/todas-las-zonas/l"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

LISTING_URL_RE = re.compile(r"/alquiler/vivienda/[^/]+/([a-z0-9-]+)/(\d+)/d")
FEATURES_RE = re.compile(r"(\d+)\s*habs?·(\d+)\s*ba[nñ]os?·(\d+)\s*m²")
PRICE_RE = re.compile(r"([\d.,]+)\s*€\s*/mes")

AMENITY_KEYWORDS = {
    "air_conditioning": ["aire-acondicionado"],
    "elevator": ["ascensor"],
    "heating": ["calefaccion"],
    "terrace": ["terraza"],
}


def _parse_amenities_from_slug(slug: str) -> dict:
    amenities = {}
    for key, keywords in AMENITY_KEYWORDS.items():
        amenities[key] = any(kw in slug for kw in keywords)
    furnished = None
    if "no-amueblado" in slug:
        furnished = False
    elif "amueblado" in slug:
        furnished = True
    amenities["furnished"] = furnished
    return amenities


def _parse_card(article) -> dict | None:
    link = article.find("a", href=LISTING_URL_RE)
    if not link:
        return None
    match = LISTING_URL_RE.search(link["href"])
    if not match:
        return None
    slug, listing_id = match.group(1), match.group(2)

    text = article.get_text("\n", strip=True)
    lines = [l for l in text.split("\n") if l]

    price_match = PRICE_RE.search(text)
    price = None
    if price_match:
        price = int(price_match.group(1).replace(".", "").replace(",", ""))

    features_match = FEATURES_RE.search(text)
    rooms = int(features_match.group(1)) if features_match else None
    size_m2 = int(features_match.group(3)) if features_match else None

    # La zona compare tipicamente su una riga tipo "La Maternitat i Sant Ramon, Barcelona"
    zone = None
    for line in lines:
        if line.endswith(", Barcelona"):
            zone = line.replace(", Barcelona", "").strip()
            break

    # Il titolo e' di solito la riga subito prima della zona
    title = None
    for i, line in enumerate(lines):
        if line == f"{zone}, Barcelona" and i > 0:
            title = lines[i - 1]
            break
    if title is None and lines:
        title = lines[0]

    amenities = _parse_amenities_from_slug(slug)

    return {
        "id": f"fotocasa-{listing_id}",
        "source": "fotocasa",
        "url": f"https://www.fotocasa.es/es/alquiler/vivienda/barcelona-capital/{slug}/{listing_id}/d",
        "title": title,
        "zone": zone,
        "price_eur": price,
        "rooms": rooms,
        "size_m2": size_m2,
        "furnished": amenities.pop("furnished"),
        "amenities": amenities,
        "description": None,
        "raw_text": text,
    }


def fetch_listings(timeout: int = 20) -> list[dict]:
    resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    listings = []
    for article in soup.find_all("article"):
        parsed = _parse_card(article)
        if parsed:
            listings.append(parsed)
    return listings


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_listings(), indent=2, ensure_ascii=False))
