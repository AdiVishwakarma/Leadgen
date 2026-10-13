# Lead Gen: local business leads, demo websites and outreach

A tool I built to find local businesses that have no website (or a weak one), generate a demo
landing page for them, and write the first outreach message. I review every lead and send every
message myself from the dashboard. Nothing is sent automatically.

> Status: working end to end on my machine. I have not measured reply rates yet, so there are no
> results numbers here.

## What it does

1. **Discover**: searches Google Places for a category and city (e.g. "dentist in Vasai") and stores the leads in PostgreSQL.
2. **Audit and score**: checks each lead's website with plain rules (no website, no HTTPS, not mobile friendly, and so on) and gives a 0 to 100 score. Scoring is deterministic and does not use an LLM.
3. **Draft outreach**: Gemini writes a short WhatsApp message from the real facts we have (name, rating, review count, gaps found). Drafts are validated (length, sender name, opt-out line) and retried if they fail.
4. **Demo site**: generates a light, single-page demo site for the business and deploys it to Vercel. Restaurants and salons get one layout, dentists and clinics get another.
5. **Dashboard**: a Streamlit app to pick a lead, open the demo, read the draft, open WhatsApp with the message pre-filled, and mark it as sent.

## How it works

```
Google Places -> FastAPI -> PostgreSQL
                    |-> audit + scoring (rules)
                    |-> Gemini (message + short site copy)
                    |-> Vercel API (demo site)
Streamlit dashboard -> FastAPI (HTTP)
```

Lead status flow: `new -> audited -> drafted -> site_ready -> contacted`.
Message status flow: `draft -> approved -> sent` (or `rejected`).

## Design choices

- **Demo pages only state real facts** (name, category, rating, reviews, address, phone). No invented services, prices or awards. Every page carries a demo banner and `noindex`.
- **No auto-sending.** Cold messages are sent by me, one by one, to avoid spam and WhatsApp bans.
- **The LLM is optional for pages.** If Gemini is down, the site falls back to plain text copy.
- **Everything user or LLM derived is HTML-escaped** before it goes into a page.

## Tech

Python, FastAPI, SQLAlchemy 2, PostgreSQL (Docker), httpx, BeautifulSoup, Streamlit, Google Places API (New), Gemini API, Vercel REST API, pytest.

## Setup

Requirements: Python 3.11+, Docker Desktop.

```bash
git clone https://github.com/AdiVishwakarma/Leadgen.git
cd Leadgen
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your own keys
docker compose up -d
```

`.env` needs:

| Variable | What for |
|---|---|
| `GOOGLE_PLACES_API_KEY` | finding leads |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | drafting messages and site copy |
| `VERCEL_TOKEN` | deploying demo pages (use a token for a personal account) |
| `SENDER_NAME` | name used in messages and the demo banner |

## Run

Terminal 1:
```bash
uvicorn app.main:app --reload
```
Terminal 2:
```bash
streamlit run app/streamlit_app.py
```

API docs: http://127.0.0.1:8000/docs. Dashboard: http://localhost:8501.

Daily flow in the dashboard: find leads, run the audit, pick a lead, confirm on Google that it really has no website, create the demo page, create the message, open WhatsApp, send, click "Maine bhej diya".

## Tests

```bash
pytest
```

## Known limits

- Landline numbers can't receive WhatsApp. The dashboard flags them.
- The demo pages are intentionally simple: no menu, photos or services until the business replies.
- Reply tracking and scheduled runs (n8n) are not built yet.