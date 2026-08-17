"""
Pipeline principale: scraping (Fotocasa, Habitaclia) + eventuali annunci Idealista
gia' estratti dalla routine cloud (via Gmail, vedi README) -> filtro -> dedup ->
notifica Telegram -> aggiornamento stato.

Uso (dalla routine cloud):
    python pipeline.py
    # opzionale: se e' stato prodotto un file idealista_listings.json con annunci
    # normalizzati (stesso schema degli altri), viene incluso automaticamente.

Il file seen_listings.json viene aggiornato in-place: chi esegue la routine deve
fare `git add seen_listings.json && git commit && git push` dopo l'esecuzione per
persistere il dedup al run successivo.
"""
import json
import sys
from pathlib import Path

from scrapers import fotocasa, habitaclia
from filter import filter_and_rank, load_config
from notify_telegram import notify_new_listings

ROOT = Path(__file__).parent
SEEN_PATH = ROOT / "seen_listings.json"
IDEALISTA_PATH = ROOT / "idealista_listings.json"


def load_seen_ids() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    return set(data.get("seen_ids", []))


def save_seen_ids(ids: set[str]) -> None:
    SEEN_PATH.write_text(
        json.dumps({"seen_ids": sorted(ids)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def collect_listings() -> list[dict]:
    listings = []

    try:
        listings.extend(fotocasa.fetch_listings())
    except Exception as e:
        print(f"[WARN] scraping Fotocasa fallito: {e}", file=sys.stderr)

    try:
        listings.extend(habitaclia.fetch_listings())
    except Exception as e:
        print(f"[WARN] scraping Habitaclia fallito: {e}", file=sys.stderr)

    if IDEALISTA_PATH.exists():
        try:
            listings.extend(json.loads(IDEALISTA_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[WARN] lettura idealista_listings.json fallita: {e}", file=sys.stderr)

    return listings


def main() -> dict:
    config = load_config()
    seen_ids = load_seen_ids()

    raw_listings = collect_listings()
    filtered = filter_and_rank(raw_listings, config)

    new_listings = [l for l in filtered if l["id"] not in seen_ids]

    if new_listings:
        notify_new_listings(new_listings)

    all_ids_this_run = {l["id"] for l in raw_listings}
    save_seen_ids(seen_ids | all_ids_this_run)

    summary = {
        "scraped_total": len(raw_listings),
        "passed_filters_total": len(filtered),
        "new_notified": len(new_listings),
        "new_listing_ids": [l["id"] for l in new_listings],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
