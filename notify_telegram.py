"""
Invio notifiche Telegram per i nuovi annunci trovati.
Richiede secrets.json con {"telegram_bot_token": "...", "telegram_chat_id": "..."}.
"""
import json
import requests
from pathlib import Path

SECRETS_PATH = Path(__file__).parent / "secrets.json"


def load_secrets() -> dict:
    return json.loads(SECRETS_PATH.read_text(encoding="utf-8"))


def format_message(listing: dict) -> str:
    price = f"{listing['price_eur']}€/mese" if listing.get("price_eur") else "prezzo non rilevato"
    rooms = f"{listing['rooms']} stanze" if listing.get("rooms") else "stanze n/d"
    size = f"{listing['size_m2']}m²" if listing.get("size_m2") else ""
    zone_tag = {"preferred": "✅ zona preferita", "acceptable": "🟡 zona accettabile",
                "unknown": "❔ zona da verificare"}.get(listing.get("zone_class"), "")

    lines = [
        f"🏠 <b>{listing.get('title') or 'Annuncio'}</b>",
        f"📍 {listing.get('zone') or 'zona n/d'} {zone_tag}",
        f"💶 {price} · {rooms} {('· ' + size) if size else ''}",
        f"🔗 <a href=\"{listing['url']}\">Vedi annuncio ({listing['source']})</a>",
    ]
    if listing.get("furnished") is False:
        lines.append("⚠️ NON arredato (segnalato dal sito)")
    return "\n".join(lines)


def send_telegram_message(text: str, secrets: dict | None = None, timeout: int = 15) -> None:
    secrets = secrets or load_secrets()
    url = f"https://api.telegram.org/bot{secrets['telegram_bot_token']}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": secrets["telegram_chat_id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=timeout)
    resp.raise_for_status()


def notify_new_listings(listings: list[dict], secrets: dict | None = None) -> None:
    secrets = secrets or load_secrets()
    for listing in listings:
        send_telegram_message(format_message(listing), secrets)


if __name__ == "__main__":
    send_telegram_message("✅ Test: il bot BCN Flat Finder e' collegato correttamente.")
