# BCN Flat Finder

Sistema automatico di ricerca appartamenti a Barcellona (2 camere + zona comune,
budget 1000-1300€, zone specifiche), con notifiche Telegram per i nuovi annunci.

## Come funziona

Una routine cloud (Claude Code / RemoteTrigger) gira ogni 2 ore e ad ogni esecuzione:

1. **Fotocasa + Habitaclia**: `pipeline.py` lancia gli scraper in `scrapers/` e
   recupera gli annunci piu recenti direttamente via HTTP (nessun browser headless
   necessario, i due siti renderizzano gli annunci lato server).
2. **Idealista**: NON viene scrapato direttamente (protezioni anti-bot troppo
   aggressive per farlo in modo affidabile da un ambiente cloud). Invece, la routine
   usa il connettore Gmail per leggere le email di alert che Idealista manda sulla
   ricerca salvata dall'utente, ne estrae gli annunci e li scrive in
   `idealista_listings.json` (stesso schema degli altri, vedi `filter.py`) prima di
   lanciare `pipeline.py`. Questo passaggio e' descritto nel prompt della routine
   stessa, non in uno script Python (serve l'accesso Gmail dell'agente, non credenziali
   API separate).
3. **Filtro**: `filter.py` applica i criteri di `config.json` (budget, zone, stanze,
   arredato) e assegna un punteggio (zona preferita, dotazioni, vicinanza al budget
   ideale).
4. **Dedup**: `seen_listings.json` tiene traccia degli annunci gia' notificati. Solo i
   nuovi vengono mandati su Telegram. Il file viene aggiornato e ricommittato ad ogni
   esecuzione (persistenza tra un run e l'altro tramite il repo Git).
5. **Notifica**: `notify_telegram.py` manda un messaggio per ogni nuovo annuncio che
   passa i filtri.

## File

- `config.json` — criteri di ricerca (modificabile in qualsiasi momento)
- `scrapers/fotocasa.py`, `scrapers/habitaclia.py` — scraping dei due portali
- `filter.py` — applica criteri e scoring
- `notify_telegram.py` — invio messaggi Telegram
- `pipeline.py` — orchestratore, punto di ingresso della routine
- `seen_listings.json` — stato persistente degli annunci gia' notificati
- `secrets.json` — token bot Telegram + chat_id (NON nel repo di esempio, va creato
  a partire da `secrets.json.example`; il repo e' privato quindi tenerlo li' e'
  accettabile — revocabile in ogni momento da @BotFather)

## Modificare i criteri di ricerca

Basta editare `config.json` (budget, zone, stanze, dotazioni richieste) e fare commit.
Al giro successivo la routine usera' i nuovi criteri automaticamente.

## Test manuale locale

```bash
pip install -r requirements.txt
cp secrets.json.example secrets.json   # poi inserire i valori veri
python notify_telegram.py              # invia un messaggio di test
python pipeline.py                     # esegue l'intera pipeline una volta
```
