from __future__ import annotations

import json
import re
from typing import Any

from google.adk.agents import Agent

from app.agents.llm import build_llm, run_agent
from app.config import settings
from app.data.brand_profile import BRAND_PROFILE


def _context_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def build_review_prompt(draft: str, context: dict[str, Any]) -> str:
    brand = BRAND_PROFILE
    return f"""
Kamu adalah reviewer kualitas konten pemasaran yang TELITI dan anti-halusinasi.

# DATA FAKTUAL (satu-satunya acuan kebenaran angka)
{_context_json(context)}

# GAYA BRAND
- Tone: {brand['tone']}
- Aturan klaim: {brand['promo_rule']}

# DRAFT KANDIDAT YANG DINILAI
{draft}

# KRITERIA PENILAIAN (skor 1-100)
1. Hook strength (apakah hook 3 detik cukup kuat & relevan dengan data)
2. Akurasi angka: SEMUA klaim stok, diskon, rating, jumlah order harus persis sama dengan
   DATA FAKTUAL. TEMUAN angka yang tidak sesuai data = hallucination -> WAJIB ditolak.
3. Brand tone: bahasa Indonesia natural, gaya casual tapi sopan, CTA sesuai channel.
4. Kesesuaian format: ada [Visual]/[Hook]/[Body]/[CTA], kutipan testimoni, bullet 📦 🏷️, hashtag,
   broadcast < 50 kata.

# OUTPUT
Balas HANYA satu objek JSON dengan skema berikut (tanpa teks lain, tanpa markdown fence):

{{"approved": <true|false>, "score": <int 1-100>, "feedback": "<ringkasan perbaikan konkret>", "revised": "<draft revisi penuh jika perlu perbaikan, atau null jika approved>"}}
""".strip()


def build_reviewer_agent() -> Agent:
    return Agent(
        name="reviewer",
        model=build_llm(settings),
        instruction=(
            "Kamu adalah reviewer ketat konten marketing. Evaluasi akurasi angka terhadap data "
            "dan kualitas hook/tone/format. Balas selalu JSON: approved, score, feedback, revised."
        ),
    )


def parse_review_json(text: str) -> dict[str, Any]:
    """Ekstrak JSON dari jawaban reviewer dengan toleransi markdown fence / teks lain."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Reviewer tidak membalas JSON yang valid: {text[:300]!r}")
    payload = json.loads(cleaned[start : end + 1])
    payload.setdefault("approved", False)
    payload.setdefault("score", 0)
    payload.setdefault("feedback", "")
    payload.setdefault("revised", None)
    return payload


async def review_draft(
    agent: Agent, draft: str, context: dict[str, Any], session_id: str
) -> dict[str, Any]:
    raw = await run_agent(agent, build_review_prompt(draft, context), session_id=session_id)
    return parse_review_json(raw)
