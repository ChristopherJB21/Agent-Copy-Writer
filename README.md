# Agent-Copy-Writer — AI Marketing Copilot (MVP)

Pipeline multi-agent berbasis **Google ADK** yang mengubah data operasional (transaksi, deadstock, review)
menjadi **rekomendasi konten promosi 3 format siap pakai** (TikTok/Shopee Video, Instagram/Shopee Feed,
Broadcast Chat/WhatsApp) untuk seller UMKM fashion, lalu mengirimnya ke **Telegram** di jam *prime time*.

```
[Trigger CLI / cron (prime time)] -> [Sub-agents SQL: velocity + deadstock + social proof]
 -> [Copywriter Agent (ADK LiteLlm)] -> [Reviewer Agent (loop max 2x)]
 -> [Format pesan gaya blueprint] -> [Telegram Bot / dry-run ke outputs/]
```

## Tech Stack

- Python 3.14.7 (dikelola `uv`, ada `requirements.txt` pendamping)
- PostgreSQL 18 via Docker/Podman (`docker-compose.yml`)
- Google ADK (`LiteLlm`) ke endpoint OpenAI-compatible (mis. 9Router) via env var
- `python-telegram-bot` v21+
- Brand profile sebagai **config file** (`app/data/brand_profile.py`), bukan tabel

## Struktur

```
app/
├── config.py            # baca .env: DATABASE_URL, LLM, Telegram, slot prime time
├── cli.py               # init-db | seed [--force] | trigger --slot ... [--dry-run]
├── db/
│   ├── connection.py    # pool async psycopg
│   ├── schema.sql       # DDL idempotent: inventory, orders, reviews
│   └── seed.py          # dummy data deterministic (7 SKU fashion UMKM)
├── data/brand_profile.py# brand voice (config, bukan tabel)
├── agents/
│   ├── data_subagents.py# 3 sub-agent SQL -> context dict (bukan agent LLM)
│   ├── copywriter.py    # agent ADK: 3 format draft ([TIKTOK]/[FEED]/[BROADCAST])
│   ├── reviewer.py      # agent ADK: skor JSON {approved, score, feedback, revised}
│   └── pipeline.py      # orkestrasi + loop reviewer (<=2) + format pesan
└── delivery/telegram.py # kirim via Telegram; arsip salinan ke outputs/
```

## Setup

```bash
# 1. Install dependency (bikin .venv Python 3.14.7)
uv sync

# 2. Bikin .env dari template
copy .env.example .env
#    -> isi: OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL,
#            TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (opsional utk dry-run)

# 3. Jalankan database (Docker atau Podman)
docker compose up -d        # atau: podman compose up -d
```

## Cara Pakai

```bash
# Skema tabel + dummy data
uv run python -m app.cli init-db
uv run python -m app.cli seed          # hanya jika kosong; tambahkan --force utk isi ulang

# Generate konten tanpa kirim (cetak di terminal + simpan outputs/)
uv run python -m app.cli trigger --dry-run --slot siang

# Generate + kirim ke Telegram (wajib .env terisi TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID)
uv run python -m app.cli trigger --slot malam
```

Command: `init-db` (skema idempotent), `seed` (isi dummy), `trigger`
(slot `siang|sore|malam`, opsi `--dry-run`).

> Opsi cron/jadwal otomatis (cron job, APScheduler, dsb.) dicatat sebagai enhancement;
> untuk MVP trigger manual dulu.

## Catatan Konfigurasi LLM (9Router / OpenAI-compatible)

`app/agents/llm.py` membangun `LiteLlm` dengan:
- `api_base` = `OPENAI_BASE_URL`
- `api_key` = `OPENAI_API_KEY`
- Model tanpa `/` otomatis diberi prefix `openai/` supaya litellm me-routing ke `api_base`
  (nama model tetap dikirim polos ke endpoint).

Jika endpoint butuh header/param khusus, ubah `build_llm()` di `app/agents/llm.py`.

## Contoh Output

Lihat blueprint di `brainstorming_ai_marketing_copilot.md` (baris 83–104) untuk contoh pesan
Telegram lengkap (Kemeja Linen, deadstock 45 pcs, diskon 30%, testimoni bintang 5).
Seed bawaan mereproduksi SKU tersebut dengan angka yang sama agar demo sesuai dokumen.