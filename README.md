# TrueBill

**Every Bill. Every Rupee. Verified.**

TrueBill is an AI electricity-bill auditor. A user sends a bill (photo or PDF) to a Telegram bot. TrueBill reads it, retrieves the applicable **official** tariff, recalculates the charges with a deterministic Python engine, and replies with an audit: which charges match, which don't, why, the official source and its effective date, and a draft clarification request.

> **AI reads. Rules verify. Evidence explains.**
> The LLM never does the arithmetic. Extraction and explanation use AI; every charge is recalculated by plain Python against the official tariff.

**Team LuvKush:** Lakshay Verma and Khushi Verma

**MVP scope:** one Delhi discom (BSES Rajdhani Power Limited, BRPL), one tariff category (Domestic).

---

## Try the prototype

| Way | What you need | Time |
|---|---|---|
| **1. Watch the demo** | Nothing | 2 min |
| **2. Use the live bot** | Telegram | 1 min |
| **3. Run it yourself** | Python 3.11+, three API keys | 10 min |

**1. Demo video:** [ADD DEMO VIDEO LINK HERE]

**2. Live bot:** [@MyHackathonHelperbot](https://t.me/MyHackathonHelperbot)
The bot and the audit API run on the team's own machines, so the bot answers only while they are running. [ADD THE HOURS THE BOT WILL BE ONLINE, OR "ask us to start it"]. If it does not reply, please use option 1 or 3.
Send it a **BRPL Domestic bill** (JPG, PNG or PDF) with a **28 to 31 day billing period**. Send one bill and wait up to a minute for the reply.

**3. Run it yourself:** see [Run it locally](#run-it-locally).

---

## How it works

```
 Telegram bill upload (photo / PDF)
          |
          v
 [bot]  Gemini vision reads the bill  ->  Bill JSON
          |
          |        [retrieval]  TinyFish Search + Fetch find the official tariff
          |                     Gemini extracts it  ->  Tariff JSON (+ source, effective date)
          v                     (cached in retrieval/tariff_cache/)
 [engine] POST /audit  { bill, tariff }
          Python rules engine recalculates each charge
          Gemini explains the result in plain language and drafts a clarification request
          |
          v
 Audit JSON  ->  Telegram report (checks, explanation, uncertainties, official sources, draft complaint)
```

Every audit names its tariff source, the tariff's effective date, and its uncertainties. When the system cannot verify something, it says so instead of guessing.

### Who built what

| Folder | Owner | What it does |
|---|---|---|
| `bot/` | Khushi | Telegram bot, Gemini vision bill extraction, retry and extraction cache, calls the audit API |
| `retrieval/` | Khushi | TinyFish official-source retrieval, tariff extraction, tariff cache |
| `engine/` | Lakshay | FastAPI `/audit`, deterministic rules engine, LLM explanation and draft complaint, tests |
| repo root (`src/`, `index.html`, ...) | Khushi | Web front end built in Google AI Studio (see status below) |
| `CONTRACT.md` | Both | The three JSON shapes the parts exchange (Bill, Tariff, Audit) |

---

## Status: what works and what doesn't yet

| Part | Status |
|---|---|
| Telegram bot receives photos and PDFs | Working |
| Bill extraction with Gemini vision (JPG, PNG, PDF, including scanned) | Working. It read a real BRPL bill in testing. Free-tier Gemini rate limits (HTTP 429) can slow it, so the bot retries and caches successful extractions |
| TinyFish retrieval of official tariff documents | Working (Search + Fetch). Found the BRPL FY 2021-22 tariff schedule and the DERC press note stating its effective date |
| Verified tariff data for BRPL Domestic | Committed in `retrieval/tariff_cache/brpl_domestic.json`, completed and checked by hand against official documents (see limitations) |
| Rules engine (energy slabs, fixed charge by load band, surcharges) | Working for billing periods of 28 to 31 days |
| Plain-language explanation and draft complaint | Working |
| Web front end | UI prototype built against sample audit data. It is **not** connected to the live backend |
| Evaluation on 30 to 50 bills | **Planned, not achieved.** No accuracy figures are claimed |

### Known limitations (please read)

- **Billing periods outside 28 to 31 days** (for example 32 days) are not audited. Proration rules are not built, so the bot reports "no charges were checked" and lists the reason.
- **Surcharge percentages:** 8% deficit recovery and 7% pension trust come from the DERC FY 2021-22 schedule as reviewed manually. The automated fetch could not confirm them, and an older FY 2020-21 document showed 5% for pension trust. They are listed as uncertainties in every audit.
- **FPPAS** (fuel and power purchase adjustment) is set by DERC every month. The tariff file holds only the months we could verify from an official page (currently June 2026). Bills from other months get an uncertainty note.
- **Fixed charge** is applied as sanctioned load times the rate of its load band. This reading is flagged as "to be confirmed on a real bill".
- **`retrieval/tariff.py`** writes the cache in an earlier field layout than `CONTRACT.md`. The committed cache is the corrected reference, so running `tariff.py` overwrites it. Restore it with `git checkout retrieval/tariff_cache/brpl_domestic.json`.
- **Live bot availability** depends on the team's machines running (see above).
- Only BRPL Domestic is supported.

---

## Run it locally

**Requirements:** Python 3.11 or newer, and API keys for Telegram (from @BotFather), Google Gemini (AI Studio) and TinyFish (agent.tinyfish.ai/api-keys).

**1. Install**
```bash
git clone https://github.com/khushivcreates/TrueBill.git
cd TrueBill
python -m pip install -r engine/requirements.txt
python -m pip install -r bot/requirements.txt
python -m pip install -r retrieval/requirements.txt
```

**2. Add your keys.** Create two files. They are git-ignored and must never be committed.

`.env` (repo root):
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_key
TINYFISH_API_KEY=your_tinyfish_key
AUDIT_API_URL=http://127.0.0.1:8001/audit
```
`engine/.env`:
```
GEMINI_API_KEY=your_gemini_key
```

**3. Start the audit API** (terminal 1)
```bash
cd engine
python -m uvicorn main:app --port 8001
```
Open http://127.0.0.1:8001/health. It should return `{"status":"ok"}`. Interactive API docs are at http://127.0.0.1:8001/docs.

**4. Start the bot** (terminal 2)
```bash
cd bot
python bot.py
```
Wait for `Application started`. Run only one copy of the bot per token, otherwise Telegram reports a conflict.

**5. Audit a bill.** Open your bot in Telegram, press Start, and send a BRPL Domestic bill (JPG, PNG or PDF) with a 28 to 31 day period.

**Optional: web front end** (UI prototype with sample data)
```bash
npm install
npm run dev
```

**Optional: tests**
```bash
cd engine && python -m pytest
cd ../bot && python test_cache.py && python test_retry.py
```

---

## Data contract

`CONTRACT.md` defines the three JSON shapes and is the reference if code and docs disagree.

- **Bill JSON** (from extraction): `discom`, `category`, `consumer_name`, `billing_period {start, end}`, `units_consumed`, `sanctioned_load_kw`, `charges {energy, fixed, surcharges, other, total}`, `missing_fields`. Anything unreadable is `null` and listed in `missing_fields`.
- **Tariff JSON** (from retrieval): `energy_slabs`, `fixed_charge` (by kW band), `surcharges`, `fppas_by_month`, `effective_date`, `source_url`, `other_sources`, `uncertainties`, `retrieved_at`.
- **Audit JSON** (from the engine): `checks [{item, status "ok"|"warning", billed, expected, note}]`, `explanation`, `sources [{title, url, effective_date}]`, `uncertainties`, `draft_complaint`.

## Safety and privacy by design

- Calculations are deterministic Python. The LLM only reads the bill and explains the result.
- Only official sources (DERC and BSES domains) are accepted for tariff data. Other sites are rejected.
- Missing or unreadable fields are reported as uncertainties, not guessed.
- Sample bills and the extraction cache are git-ignored and never committed. API keys live only in `.env` files.

## Built with

Telegram Bot API, Python, FastAPI, Google Gemini (vision and explanation), TinyFish Search and Fetch, Google AI Studio (front end), OpenCode and Codex (coding assistance), Claude (guidance).

## Roadmap

More discoms and consumer categories, proration for non-standard billing periods, historical bill comparison and tariff-update alerts, a live web front end, and the planned 30 to 50 bill evaluation with permission and privacy safeguards. Water and gas bill auditing is a longer-term idea.
