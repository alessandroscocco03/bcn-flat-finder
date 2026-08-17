"""
Applica i criteri di config.json a una lista di annunci normalizzati
(qualsiasi fonte: fotocasa, habitaclia, idealista) e restituisce solo
quelli che passano i filtri "hard", con un punteggio di rilevanza.

Schema atteso per ogni annuncio (chiavi mancanti = None/sconosciuto, non
si scarta mai un annuncio solo perche' un dato non e' stato estratto):
{
  "id": str, "source": str, "url": str, "title": str, "zone": str,
  "price_eur": int|None, "rooms": int|None, "size_m2": int|None,
  "furnished": bool|None, "amenities": dict, "description": str|None
}
"""
import json
import unicodedata
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    """Minuscolo + rimozione accenti, cosi' 'Gracia' matcha 'Gràcia'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _zone_matches(zone: str | None, zone_list: list[str]) -> bool:
    if not zone:
        return False
    zone_norm = _normalize(zone)
    return any(_normalize(z) in zone_norm or zone_norm in _normalize(z) for z in zone_list)


def classify_zone(zone: str | None, zones_cfg: dict) -> str:
    if _zone_matches(zone, zones_cfg["excluded"]):
        return "excluded"
    if _zone_matches(zone, zones_cfg["preferred"]):
        return "preferred"
    if _zone_matches(zone, zones_cfg["acceptable_low_priority"]):
        return "acceptable"
    return "unknown"


def passes_hard_filters(listing: dict, config: dict) -> tuple[bool, str]:
    """Ritorna (passa, motivo_scarto). Scarta solo su dati certi e sfavorevoli;
    se un dato manca (None) non blocca l'annuncio, verra' segnalato come 'da verificare'."""
    search = config["search"]
    zones_cfg = config["zones"]

    zone_class = classify_zone(listing.get("zone"), zones_cfg)
    if zone_class == "excluded":
        return False, f"zona esclusa: {listing.get('zone')}"

    price = listing.get("price_eur")
    if price is not None and price > search["price_max_eur"] + 150:
        # margine di tolleranza sul massimo (spese extra, ecc). Nessun limite minimo:
        # un affitto piu' economico del previsto non e' mai un motivo di scarto.
        return False, f"fuori budget: {price}€"

    rooms = listing.get("rooms")
    if rooms is not None and rooms < search["min_bedrooms"]:
        return False, f"troppe poche stanze: {rooms}"

    if listing.get("furnished") is False and search["furnished_required"]:
        return False, "non arredato"

    return True, ""


def score_listing(listing: dict, config: dict) -> int:
    score = 0
    zone_class = classify_zone(listing.get("zone"), config["zones"])
    score += {"preferred": 30, "acceptable": 10, "unknown": 5}.get(zone_class, 0)

    price = listing.get("price_eur")
    if price is not None:
        mid = (config["search"]["price_min_eur"] + config["search"]["price_max_eur"]) / 2
        score += max(0, 15 - int(abs(price - mid) / 50))

    amenities = listing.get("amenities") or {}
    if amenities.get("washing_machine"):
        score += 10
    if amenities.get("dishwasher"):
        score += 3
    if amenities.get("air_conditioning"):
        score += 3
    if listing.get("furnished") is True:
        score += 5

    return score


def filter_and_rank(listings: list[dict], config: dict | None = None) -> list[dict]:
    config = config or load_config()
    results = []
    for listing in listings:
        ok, reason = passes_hard_filters(listing, config)
        if not ok:
            continue
        listing = dict(listing)
        listing["zone_class"] = classify_zone(listing.get("zone"), config["zones"])
        listing["score"] = score_listing(listing, config)
        results.append(listing)

    results.sort(key=lambda l: l["score"], reverse=True)
    return results


if __name__ == "__main__":
    import sys
    data = json.loads(sys.stdin.read())
    print(json.dumps(filter_and_rank(data), indent=2, ensure_ascii=False))
