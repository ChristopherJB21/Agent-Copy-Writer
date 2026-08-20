<div align="center">

# 🚀 Agent-Copy-Writer — AI Marketing Copilot (MVP)

**Turn transactional data into ready-to-publish promo content in 3 formats — delivered straight to your Telegram.**

Built with **Google ADK** · **PostgreSQL 18** · **Python 3.14** · **python-telegram-bot**

`🐍 Python 3.14` · `🤖 Google ADK (LiteLlm)` · `🐘 PostgreSQL 18` · `📨 Telegram Bot` · `🔍 Pylance-clean (0 errors)`

---

</div>

## ✨ Why This Project?

UMKM / local fashion sellers spend **2–4 hours a day** staring at sales dashboards, reading reviews,
checking deadstock, and brainstorming promo copy for TikTok, Shopee, and Instagram.

This MVP replaces that ritual with a **multi-agent AI pipeline**: it reads your operational data,
writes **click-to-copy promotional content** in three channel-specific formats, runs it through a
**strict quality reviewer**, and pushes the final result to your Telegram at prime time.

> 💡 Save hours every day, beat creative block, and never let a deadstock SKU sit forgotten again.

---

## 🎯 Features

### 1. 🔎 Intelligent Data Ingestion — 3 SQL Sub-Agents
Data layer implemented as fast, accurate SQL queries (not LLM calls), assembled into a single context dict:

| Sub-Agent | SQL Mission | Output |
|---|---|---|
| **Sales Velocity Monitor** | Best-selling SKUs in the last 24h / 7 days (orders & revenue) | FOMO-triggering products |
| **Inventory / Deadstock Monitor** | SKUs piling up (≥40 pcs stock, listed >30 days, low 7-day orders) | Clearance-sale candidates |
| **Social Proof Miner** | 3 most recent 5-star reviews + average rating for the target SKU | Authentic testimonials |

### 2. ✍️ Multi-Channel Copywriter Agent (ADK)
A single LLM call produces **all 3 formats at once**, strictly bound to the injected data:

- 🎬 **TikTok & Shopee Video Script (~15s)** — `[Visual]`, `[Hook (0-3s)]`, `[Body (4-12s)]`, `[CTA (13-15s)]`
- 📸 **Instagram & Shopee Feed Caption** — testimonial-led storytelling, emoji bullets, CTA, hashtags
- 💬 **Shopee Broadcast Chat / WhatsApp** — under 50 words, urgent, direct-to-link, no hashtags

### 3. 🛡️ Reviewer Agent — Anti-Hallucination Quality Loop
A second ADK agent audits every line against the **FACTUAL DATA** (stock, discount %, rating, order counts):

- Scores 1–100 on hook strength, **figure accuracy**, brand tone, and format compliance
- Maximum **2 review rounds** — reject → revise (by reviewer or copywriter) → re-review
- Returns strict JSON (`approved` / `score` / `feedback` / `revised`) with a tolerant JSON parser

### 4. 📣 Brand Voice as a Config File
The brand profile (tone, audience, CTA rules, hashtags, forbidden claims) lives in
`app/data/brand_profile.py` — edit one file to change the voice everywhere.

### 5. 📨 One-Command Telegram Delivery
- Sends the formatted message to your Telegram chat via bot token + chat id
- **`--dry-run`** mode prints to the terminal and skips sending — perfect for testing
- Every run is **archived** to `outputs/` (UTF-8, timestamped)

### 6. ⏰ Prime-Time Slots
Pick the message mood — `morning` ☀️ · `evening` 🌆 · `night` 🌙 — reflected in the title label
(`PRIME TIME MORNING`, etc.) and content nuance.

### 7. 🧪 Deterministic Demo Data
`seed` fills **7 fashion SKUs, 94 orders, 23 reviews** in fully English text — reproducible on every
machine, including the canonical demo SKU **Premium Linen Shirt** (45 pcs deadstock, 30% off, 5.0 ⭐).

### 8. 🔧 CLI-First, Scheduler-Ready
Manual trigger via CLI (`init-db` / `seed` / `trigger`); cron / APScheduler noted as a future
enhancement — the pipeline is a single awaitable function, easy to wire to a scheduler.

---

## 🧠 How It Works

```text
[ CLI trigger --slot morning|evening|night ]
                   │
                   ▼
[ Data Sub-Agents (PostgreSQL 18) ]
   ├─ 1. Sales Velocity Monitor ──────┐
   ├─ 2. Deadstock Monitor ───────────┼──▶ Context dict (numbers + 3 five-star quotes)
   └─ 3. Social Proof Miner ──────────┘
                   │
                   ▼
[ Copywriter Agent (ADK LiteLlm) ]
   └── [TIKTOK] + [FEED] + [BROADCAST] draft (retries ≤ 3 if markers are invalid)
                   │
                   ▼
[ Reviewer Agent ──── (loop, max 2 rounds) ]
   ├── not approved?  ▶ revise (reviewer or copywriter) ▶ re-review
   └── approved ✔      ▶ format blueprint message
                   │
                   ▼
[ Delivery ]
   ├── Telegram bot (real chat)      ✅
   └── dry-run → terminal + outputs/ ✅
```

**Agent strategy in one sentence:** SQL sub-agents give *accurate numbers*, the copywriter adds
*creative structure*, the reviewer *blocks hallucinated claims*, Telegram delivers *fast action*.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.14.7 (managed with **uv** + companion `requirements.txt`) |
| Agent Framework | **Google ADK** — `LiteLlm` agent backed by any OpenAI-compatible endpoint (e.g., 9Router) |
| LLM Router | **litellm** (`api_base` + `api_key` from `.env`) |
| Database | **PostgreSQL 18** via Docker Compose (`postgres:18-alpine`), async **psycopg** pool |
| Bot | **python-telegram-bot** v21+ |
| Config | `python-dotenv` (`.env`), brand profile as a config file |
| Quality | **ruff** (lint) · **black** (format, line-length 100) · **pyright** (type-check, 0 errors) |

---

## 📁 Project Structure

```text
Agent-Copy-Writer/
├── app/
│   ├── config.py             # reads .env: DB, LLM, Telegram, prime-time slot labels
│   ├── cli.py                # init-db | seed [--force] | trigger --slot ... [--dry-run]
│   ├── db/
│   │   ├── connection.py     # async psycopg connection pool
│   │   ├── schema.sql        # idempotent DDL: inventory, orders, reviews
│   │   └── seed.py           # deterministic dummy data (7 SKUs · 94 orders · 23 reviews)
│   ├── data/
│   │   └── brand_profile.py  # Brand Voice Guide (config file, not a table)
│   ├── agents/
│   │   ├── data_subagents.py # 3 SQL sub-agents → context dict (no LLM involved)
│   │   ├── copywriter.py     # ADK agent: 3-format draft → [TIKTOK]/[FEED]/[BROADCAST]
│   │   ├── reviewer.py       # ADK agent: strict JSON verdict (approved/score/feedback/revised)
│   │   ├── llm.py            # LiteLlm builder + ADK runner helper
│   │   └── pipeline.py       # orchestration, reviewer loop (≤2), message formatter
│   └── delivery/
│       └── telegram.py       # Telegram send + outputs/ archive
├── outputs/                  # archived messages (gitignored)
├── docker-compose.yml        # PostgreSQL 18 service
├── .env.example              # environment template
├── pyproject.toml            # deps + ruff/black config
├── pyrightconfig.json        # Pylance/pyright (points at .venv)
└── README.md
```

---

## ⚡ Quick Start

### Prerequisites

- **uv** (Python package manager) — or Python 3.13–3.14 + pip with `requirements.txt`
- **Docker** or **Podman** (for PostgreSQL 18)
- An **OpenAI-compatible LLM endpoint** (e.g., 9Router) with an API key
- A **Telegram bot** token + your chat ID (optional — `--dry-run` works without it)

### 1. Install

```bash
uv sync                       # creates .venv on Python 3.14.7
```

> Prefer pip? `pip install -r requirements.txt`

### 2. Configure

```bash
copy .env.example .env        # then fill in the values
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL DSN (default: `postgresql://postgres:postgres@127.0.0.1:5432/marketing_copilot`) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Your OpenAI-compatible LLM credentials (URL ends in `/v1`) |
| `LLM_MODEL` | Model id, e.g. `my-free-deepseek-v4-flash` |
| `LLM_MAX_TOKENS` | Max tokens per response (4096 recommended) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Optional — leave empty for `--dry-run` only |
| `TELEGRAM_PARSE_MODE` | Empty (plain text) · `HTML` · `MarkdownV2` |
| `PRIME_TIME_MORNING/EVENING/NIGHT` | Custom title labels per slot |

### 3. Start the database

```bash
docker compose up -d          # or: podman compose up -d
docker ps                     # wait until "healthy"
```

### 4. Create the schema & seed demo data

```bash
uv run python -m app.cli init-db     # idempotent — safe to re-run
uv run python -m app.cli seed        # only fills when empty
```

---

## 🕹️ Everyday Usage

```bash
# Preview content without sending anything (prints to terminal + saves to outputs/)
uv run python -m app.cli trigger --dry-run --slot morning

# Generate + deliver to Telegram
uv run python -m app.cli trigger --slot evening
```

### Command reference

| Command | Description |
|---|---|
| `init-db` | Apply the schema (idempotent) |
| `seed` | Fill deterministic dummy data (skips if data exists) |
| `seed --force` | Wipe existing data, then reseed |
| `trigger --slot <slot>` | Run the full pipeline and send to Telegram |
| `trigger --slot <slot> --dry-run` | Run the pipeline without sending; show message in the terminal |

**Slots:** `morning` ☀️ · `evening` 🌆 · `night` 🌙

**Typical pipeline output:**

```text
🧭 Target promo: Premium Linen Shirt (stock 45 pcs, discount 30.0%)
🔍 Review 1/2: score=78 approved=False -- feed needs emoji bullets and a stronger CTA
🔍 Review 2/2: score=96 approved=True
[OK] Approved=True | rounds=2
[OK] Delivered: telegram | archive: outputs\20260821_013643_morning.txt
```

---

## 📤 Example Output (real Telegram delivery)

Exactly what the seller receives — copy-paste ready, in the blueprint's format:

```text
🔔 READY-TO-USE CONTENT RECOMMENDATION (PRIME TIME EVENING)
📊 Trigger Data: Stock of Premium Linen Shirt: 45 pcs left (Deadstock) + Review Rating 5.0 ⭐ ("Breathable and doesn't wrinkle easily - it stays neat all day")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎬 1. TIKTOK & SHOPEE VIDEO SCRIPT (~15 Seconds)
[Visual: Golden-hour shot of someone wearing the Premium Linen Shirt, then a quick close-up of the breathable fabric and the 30% off tag]
[Hook (0-3s)]: Your evening outfit just got better—30% off!
[Body (4-12s)]: Meet the Premium Linen Shirt: breathable, comfy, and it stays neat all day. Sari, Budi, and Rina all gave it 5 stars—a perfect 5.0 rating. With 45 pieces in stock, this is your sign to grab one for tonight.
[CTA (13-15s)]: Tap the yellow cart and make it yours!

📸 2. INSTAGRAM & SHOPEE FEED CAPTION
"Breathable and doesn't wrinkle easily - it stays neat all day" — Sari A. ★★★★★

After a long day, the last thing you want is a stiff, stuffy shirt. The Premium Linen Shirt keeps you cool and looking sharp—whether you're heading to an evening hangout or just unwinding in style. Our buyers agree: it's comfortable, breathable, and the colors are lovely.

• 45 pieces in stock
• 30% off

Tap the link in bio to grab yours!

#OOTD #Fashion #LocalBrand #LinenShirt #ClearanceSale

💬 3. SHOPEE BROADCAST CHAT / WHATSAPP
Evening plans? The Premium Linen Shirt is 30% off and rated 5.0 by our buyers. Breathable, comfy, and stays neat all day—perfect for work or hanging out. 45 pieces left. Click the link in chat to grab yours! [Product Link]
```

---

## 🧪 Quality Gates

```bash
uv run black --check app          # formatting — clean
uv run ruff check app             # linting — 0 errors
npx -y pyright                    # type-check (same engine as Pylance) — 0 errors / 0 warnings
uv run python -m app.cli --help   # CLI sanity
```

The repo ships with `pyrightconfig.json` (venv-aware) so **VS Code Pylance** resolves all imports
and reports **zero errors**.

---

## 📈 Roadmap (Future Enhancements)

- ⏰ **Automated scheduling** — cron / APScheduler for hands-off prime-time runs
- 🔍 **Vector RAG (pgvector)** — semantic search over thousands of reviews (blueprint's preferred upgrade path)
- 🖼️ **Image / video asset suggestions** — attach visual references to the script
- 📊 **Analytics on delivered posts** — track which promos convert
- 🛠️ **Structured JSON output contract** — call the LLM endpoint with `output_schema` to make parsing bulletproof
- 🤳 **Multi-brand profiles** — switch brand voice per store via config selection

---

## 📚 References & Docs

- 📜 **Blueprint:** [`brainstorming_ai_marketing_copilot.md`](brainstorming_ai_marketing_copilot.md) —
  the single source of truth: problem statement, architecture, RAG-vs-SQL analysis, and the exact
  Telegram output format this repo reproduces.
- 📐 **Plan:** `.kilo/plans/1787241693065-ai-marketing-copilot-mvp.md` — original implementation plan.

## 🙌 Acknowledgements

Built as an MVP demo of the *Multi-Agent AI Content-Writing Marketing Copilot* concept — as an
autonomous content engine for e-commerce sellers on **Shopee**, **TikTok Shop**, and
**Instagram Business**.