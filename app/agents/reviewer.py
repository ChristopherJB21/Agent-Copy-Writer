from __future__ import annotations

import json
import re
from typing import Any

from google.adk.agents import Agent

from app.agents.llm import build_llm, run_agent
from app.config import settings
from app.data.brand_profile import BRAND_PROFILE

JSON_SCHEMA_HINT = (
    '{"approved": false, "score": 70, "feedback": "Fix the CTA and make sure the '
    'stock/discount figures match the data exactly", "revised": null}'
)


def _context_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def build_review_prompt(draft: str, context: dict[str, Any]) -> str:
    brand = BRAND_PROFILE
    return f"""
You are a REVIEWER whose output is ONLY a single JSON object. Never write an intro,
chain-of-thought, analysis, explanation, or markdown fences. No exceptions.
Do not echo the example JSON below - reply directly with your actual assessment.

# FACTUAL DATA (the only reference for correct figures)
{_context_json(context)}

# BRAND STYLE
- Tone: {brand['tone']}
- Claim rule: {brand['promo_rule']}

# DRAFT CANDIDATE TO REVIEW
{draft}

# SCORING CRITERIA (score 1-100)
1. Hook strength (is the 3-second hook strong and relevant to the data?)
2. Figure accuracy: EVERY stock, discount, rating, and order-count claim must exactly match
   the FACTUAL DATA. Any figure that does not match = hallucination -> must be rejected.
3. Brand tone: natural English, casual yet polite, channel-appropriate CTA.
4. Format compliance: [Visual]/[Hook]/[Body]/[CTA] present, testimonial quote, bullet
   with emoji, hashtags, and a broadcast under 50 words.

# OUTPUT (REQUIRED: a single pure JSON object modeled on the example, with no other text)
{JSON_SCHEMA_HINT}

Value notes:
- "approved": true only if ALL criteria pass with NO figure hallucination. Otherwise false.
- "score": int 1-100.
- "feedback": 1-3 concrete sentences in English describing what to fix.
- "revised": the FULL revised draft with all 3 formats (markers [TIKTOK]/[FEED]/[BROADCAST])
  when fixes are needed; set to null when "approved" is true.
""".strip()


def build_retry_review_prompt(draft: str, context: dict[str, Any], previous_raw: str) -> str:
    return f"""
The previous reviewer response was INVALID because it was not a pure JSON object.
Previous response (ignore it, do not repeat): {previous_raw[:400]}

# TASK NOW
Reply with ONLY a single JSON object modeled on this example, with nothing else:
{JSON_SCHEMA_HINT}

# DRAFT TO REVIEW
{draft}

# FACTUAL DATA
{_context_json(context)}

# DO NOT WRITE ANYTHING OTHER THAN THE JSON OBJECT - NOT EVEN CHAIN-OF-THOUGHT.
""".strip()


def build_reviewer_agent() -> Agent:
    return Agent(
        name="reviewer",
        model=build_llm(settings),
        instruction=(
            "You are a strict marketing content reviewer. Your output is ONLY a JSON object: "
            '{"approved": bool, "score": int, "feedback": str, "revised": str|null}. '
            "Evaluate figure accuracy against the data and hook/tone/format quality."
        ),
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the LAST valid JSON object from a text.

    Tolerant of chain-of-thought / surrounding text: tries every "{" occurrence with
    json.JSONDecoder.raw_decode and keeps the last valid result.
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
        raise ValueError(f"Reviewer did not return valid JSON: {text[:300]!r}")
    return valid_objects[-1]


def parse_review_json(text: str) -> dict[str, Any]:
    """Normalize a reviewer response into a dict with canonical keys."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    payload = extract_json_object(cleaned)
    payload.setdefault("approved", False)
    payload.setdefault("score", 0)
    payload.setdefault("feedback", "")
    payload.setdefault("revised", None)
    # Coerce so that "approved" is a bool even if the model sends a string ("true"/"yes").
    raw_approved = payload["approved"]
    payload["approved"] = str(raw_approved).strip().lower() in ("true", "1", "yes", "ya")
    return payload


async def review_draft(
    agent: Agent, draft: str, context: dict[str, Any], session_id: str
) -> dict[str, Any]:
    """Request a review; when the response is not JSON, ask once more (1 retry)."""
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
