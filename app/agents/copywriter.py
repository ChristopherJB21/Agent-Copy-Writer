from __future__ import annotations

import json
from typing import Any

from google.adk.agents import Agent

from app.agents.llm import build_llm, run_agent
from app.config import settings
from app.data.brand_profile import BRAND_PROFILE

OUTPUT_MARKERS = ("[TIKTOK]", "[FEED]", "[BROADCAST]")


def _context_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def _marker_example() -> str:
    return """Contoh layout output (WAJIB persis; section video minimal berisi 4 baris marker):
[TIKTOK]
[Visual: deskripsi visual singkat]
[Hook (0-3s)]: kalimat hook
[Body (4-12s)]: kalimat body dengan angka dari data
[CTA (13-15s)]: kalimat call-to-action

[FEED]
"kutipan testimoni" - Ulasan pembeli.
Paragraf storytelling
Bullet info stok
Bullet info diskon
CTA + hashtag

[BROADCAST]
pesan broadcast kurang dari 50 kata""".strip()


def _anti_noise() -> str:
    return (
        "DILARANG menulis proses berpikir, verifikasi, pengecekan ulang, kata pengantar, "
        "ajakan ('mari tulis'), atau teks selain blok marker. Karakter pertama jawabanmu "
        "HARUS [TIKTOK]. Tidak boleh ada teks setelah blok [BROADCAST]."
    )


def build_copywriter_prompt(context: dict[str, Any], slot: str, extra: str = "") -> str:
    slot_label = settings.slot_label(slot)
    brand = BRAND_PROFILE
    return f"""
Kamu adalah copywriter senior e-commerce fashion Indonesia untuk brand "{brand['store_name']}".

# DATA PENGGERAK (SATU-SATUNYA sumber angka & klaim promo)
{_context_json(context)}

# PANDUAN GAYA BRAND
- Tone: {brand['tone']}
- Audience: {brand['audience']}
- CTA: {brand['cta_rules']}
- Link produk selalu ditulis sebagai: {brand['product_link_placeholder']}
- Hashtag yang boleh dipakai: {", ".join(brand['hashtags'])}
- Aturan promo: {brand['promo_rule']}
- Dilarang: {"; ".join(brand['forbidden'])}

# KONTEKS SLOT WAKTU
Ini untuk slot PRIME TIME {slot_label}. Sesuaikan rasa urgensi/bahasa dengan waktu tersebut
(contoh: "mumpung siang ini masih ada voucher", "diskon kilat malam ini").

# TUGAS
Buat 3 format konten promo SIAP PAKAI berdasarkan DATA PENGGERAK di atas.
WAJIB memakai angka persis dari data (nama produk, sisa stok, diskon %, rating, testimoni, jumlah order).
DILARANG keras menambah/mengubah/mengarang angka atau klaim yang tidak ada di data.
{_anti_noise()}
{_marker_example()}
{extra}
""".strip()


def build_revision_prompt(
    context: dict[str, Any], slot: str, previous_draft: str, feedback: str
) -> str:
    return f"""
Kamu adalah copywriter senior yang sedang REVISI draft berdasarkan masukan reviewer.

# DATA PENGGERAK (sumber angka wajib)
{_context_json(context)}

# SLOT
PRIME TIME {settings.slot_label(slot)}

# DRAFT SEBELUMNYA
{previous_draft}

# MASUKAN REVIEWER
{feedback}

# TUGAS
Tulis ulang 3 format konten dengan memperbaiki seluruh masukan reviewer.
{_anti_noise()}
Format WAJIB persis seperti contoh:
{_marker_example()}

Angka promosi tetap harus akurat dengan DATA PENGGERAK.
""".strip()


def build_copywriter_agent() -> Agent:
    return Agent(
        name="copywriter",
        model=build_llm(settings),
        instruction=(
            "Kamu adalah copywriter konten promosi UMKM fashion Indonesia. "
            "Output hanya blok [TIKTOK]/[FEED]/[BROADCAST] beserta isinya, tanpa teks lain."
        ),
    )


async def generate_copy(
    agent: Agent, context: dict[str, Any], slot: str, session_id: str, extra: str = ""
) -> str:
    return await run_agent(
        agent, build_copywriter_prompt(context, slot, extra=extra), session_id=session_id
    )


async def revise_copy(
    agent: Agent,
    context: dict[str, Any],
    slot: str,
    draft: str,
    feedback: str,
    session_id: str,
) -> str:
    prompt = build_revision_prompt(context, slot, draft, feedback)
    return await run_agent(agent, prompt, session_id=session_id)
