from __future__ import annotations

import json
import re
from typing import Any

from google.adk.agents import Agent

from app.agents.llm import build_llm, run_agent
from app.config import settings
from app.data.brand_profile import BRAND_PROFILE

JSON_SCHEMA_HINT = (
    '{"approved": false, "score": 70, "feedback": "Perbaiki CTA dan pastikan '
    'angka stok/diskon persis sama dengan data", "revised": null}'
)


def _context_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def build_review_prompt(draft: str, context: dict[str, Any]) -> str:
    brand = BRAND_PROFILE
    return f"""
Kamu adalah REVIEWER yang output-nya HANYA satu objek JSON. DILARANG menulis kalimat
pengantar, proses berpikir, analisis, penjelasan, atau markdown fence. Tidak ada pengecualian.
Jangan menyalin contoh JSON di bawah ke dalam pikiranmu - langsung balas penilaian asli.

# DATA FAKTUAL (satu-satunya acuan kebenaran angka)
{_context_json(context)}

# GAYA BRAND
- Tone: {brand['tone']}
- Aturan klaim: {brand['promo_rule']}

# DRAFT KANDIDAT YANG DINILAI
{draft}

# KRITERIA PENILAIAN (skor 1-100)
1. Hook strength (apakah hook 3 detik cukup kuat & relevan dengan data)
2. Akurasi angka: SEMUA klaim stok, diskon, rating, jumlah order harus persis sama
   dengan DATA FAKTUAL. TEMUAN angka yang tidak sesuai data = hallucination -> false.
3. Brand tone: bahasa Indonesia natural, gaya casual tapi sopan, CTA sesuai channel.
4. Kesesuaian format: ada [Visual]/[Hook]/[Body]/[CTA], kutipan testimoni, bullet
   dengan emoji, hashtag, broadcast < 50 kata.

# OUTPUT (WAJIB: satu objek JSON murni BERPOLA seperti contoh, TANPA teks lain)
{JSON_SCHEMA_HINT}

Catatan value:
- "approved": true hanya jika SEMUA kriteria lolos TANPA hallucination angka.
- "score": int 1-100.
- "feedback": 1-3 kalimat konkret bahasa Indonesia, apa yang perlu diperbaiki.
- "revised": draft revisi LENGKAP 3 format (marker [TIKTOK]/[FEED]/[BROADCAST]) bila
  perlu perbaikan; jika "approved": true, isi null.
""".strip()


def build_retry_review_prompt(draft: str, context: dict[str, Any], previous_raw: str) -> str:
    return f"""
Jawaban reviewer sebelumnya TIDAK VALID karena bukan objek JSON murni.
Jawaban lama (abaikan, jangan diulang): {previous_raw[:400]}

# TUGAS SEKARANG
Balas HANYA satu objek JSON berpola seperti ini, TANPA apa pun di luarnya:
{JSON_SCHEMA_HINT}

# DRAFT YANG DINILAI
{draft}

# DATA FAKTUAL
{_context_json(context)}

# JANGAN TULIS TEKS APA PUN, BAHKAN PROSES BERPIKIR, SELAIN OBJEK JSON.
""".strip()


def build_reviewer_agent() -> Agent:
    return Agent(
        name="reviewer",
        model=build_llm(settings),
        instruction=(
            "Kamu adalah reviewer ketat konten marketing. Output mu HANYA satu objek JSON: "
            '{"approved": bool, "score": int, "feedback": str, "revised": str|null}. '
            "Evaluasi akurasi angka terhadap data dan kualitas hook/tone/format."
        ),
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """Ambil objek JSON terakhir yang valid dalam teks.

    Toleran terhadap proses berpikir/teks lain: mencoba setiap kemunculan '{'
    dengan json.JSONDecoder.raw_decode dan memakai hasil valid TERAKHIR.
    """
    decoder = json.JSONDecoder()
    valid_objects: list[dict[str, Any]] = []
    start = 0
    while True:
        idx = text.find("{", start)
        if idx == -1:
            break
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                valid_objects.append(obj)
        except json.JSONDecodeError:
            pass
        start = idx + 1
    if not valid_objects:
        raise ValueError(f"Reviewer tidak membalas JSON yang valid: {text[:300]!r}")
    return valid_objects[-1]


def parse_review_json(text: str) -> dict[str, Any]:
    """Normalisasi jawaban reviewer menjadi dict dengan key baku."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    payload = extract_json_object(cleaned)
    payload.setdefault("approved", False)
    payload.setdefault("score", 0)
    payload.setdefault("feedback", "")
    payload.setdefault("revised", None)
    # Koersi agar "approved" bertipe bool walaupun model mengirim string ("true"/"yes").
    raw_approved = payload["approved"]
    payload["approved"] = str(raw_approved).strip().lower() in ("true", "1", "yes", "ya")
    return payload


async def review_draft(
    agent: Agent, draft: str, context: dict[str, Any], session_id: str
) -> dict[str, Any]:
    """Minta penilaian reviewer; bila jawaban bukan JSON, minta ulang 1x."""
    raw = await run_agent(agent, build_review_prompt(draft, context), session_id=session_id)
    try:
        return parse_review_json(raw)
    except ValueError:
        retried = await run_agent(
            agent,
            build_retry_review_prompt(draft, context, raw),
            session_id=f"{session_id}-retry",
        )
        return parse_review_json(retried)
