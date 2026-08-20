# Agent-Copy-Writer — AI Marketing Copilot (MVP)

A multi-agent pipeline built with **Google ADK** that turns operational data (transactions, deadstock,
reviews) into **ready-to-use promotional content in 3 formats** (TikTok/Shopee Video, Instagram/Shopee
Feed, Broadcast Chat/WhatsApp) for UMKM fashion sellers, and delivers it to **Telegram** at prime time.

```
[CLI trigger / cron (prime time)] -> [SQL sub-agents: velocity + deadstock + social proof]
 -> [Copywriter Agent (ADK LiteLlm)] -> [Reviewer Agent (loop, max 2x)]
 -> [Blueprint-style message formatting] -> [Telegram bot / dry-run to outputs/]
```

## Tech Stack

- Python 3.14.7 (managed with `uv`, plus a companion `requirements.txt`)
- PostgreSQL 18 via Docker/Podman (`docker-compose.yml`)
- Google ADK (`LiteLlm`) pointed at an OpenAI-compatible endpoint (e.g., 9Router) via env vars
- `python-telegram-bot` v21+
- Brand profile stored as a **config file** (`app/data/brand_profile.py`), not a table

## Structure

```
app/
├── config.py            # reads .env: DATABASE_URL, LLM, Telegram, prime-time slots
├── cli.py               # init-db | seed [--force] | trigger --slot ... [--dry-run]
├── db/
│   ├── connection.py    # async psycopg pool
│   ├── schema.sql       # idempotent DDL: inventory, orders, reviews
│   └── seed.py          # deterministic dummy data (7 fashion UMKM SKUs)
├── data/brand_profile.py# brand voice (config, not a table)
├── agents/
│   ├── data_subagents.py# 3 SQL sub-agents -> context dict (not LLM agents)
│   ├── copywriter.py    # ADK agent: 3-format draft ([TIKTOK]/[FEED]/[BROADCAST])
│   ├── reviewer.py      # ADK agent: JSON score {approved, score, feedback, revised}
│   └── pipeline.py      # orchestration + reviewer loop (<=2) + message formatting
└── delivery/telegram.py # telegram delivery; archives a copy to outputs/
```

## Setup

```bash
# 1. Install dependencies (creates .venv on Python 3.14.7)
uv sync

# 2. Create .env from the template
copy .env.example .env
#    -> fill in: OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL,
#            TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional when using --dry-run)

# 3. Start the database (Docker or Podman)
docker compose up -d        # or: podman compose up -d
```

## Usage

```bash
# Schema + dummy data
uv run python -m app.cli init-db
uv run python -m app.cli seed          # only if empty; use --force to reseed

# Generate content without sending (prints to terminal + saves to outputs/)
uv run python -m app.cli trigger --dry-run --slot morning

# Generate + send to Telegram (TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID required in .env)
uv run python -m app.cli trigger --slot evening
```

Commands: `init-db` (idempotent schema), `seed` (dummy data), `trigger`
(slots `morning|evening|night`, optional `--dry-run`).

> Automated scheduling (cron, APScheduler, etc.) is noted as an enhancement;
> the MVP is triggered manually.

## LLM Configuration Notes (9Router / OpenAI-compatible)

`app/agents/llm.py` builds `LiteLlm` with:
- `api_base` = `OPENAI_BASE_URL`
- `api_key` = `OPENAI_API_KEY`
- A model without `/` is automatically prefixed with `openai/` so litellm routes it through
  `api_base` (the bare model name is still sent to the endpoint).

If your endpoint needs special headers or params, adjust `build_llm()` in `app/agents/llm.py`.

## Example Output

See the "Example Telegram Output (Real-World Demo)" section in
`brainstorming_ai_marketing_copilot.md` for a complete example message (Linen Shirt, 45 pcs
deadstock, 30% discount, 5-star testimonial). The built-in seed reproduces that SKU with matching
numbers so the demo stays true to the document.