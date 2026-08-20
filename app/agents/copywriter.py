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
    return """Example layout (use it EXACTLY; the video section must have the 4 marker lines):
[TIKTOK]
[Visual: brief visual description]
[Hook (0-3s)]: hook sentence
[Body (4-12s)]: body sentences with figures from the data
[CTA (13-15s)]: call-to-action sentence

[FEED]
"customer testimonial" - Buyer review.
Storytelling paragraph
Stock info bullet
Discount info bullet
CTA + hashtags

[BROADCAST]
broadcast message under 50 words, without hashtags""".strip()


def _anti_noise() -> str:
    return (
        "FORBIDDEN to write any chain-of-thought, self-verification, preamble, or texts like "
        "('let me write'). The first character of your answer MUST be [TIKTOK]. "
        "There must be no text after the [BROADCAST] block."
    )


def build_copywriter_prompt(context: dict[str, Any], slot: str, extra: str = "") -> str:
    slot_label = settings.slot_label(slot)
    brand = BRAND_PROFILE
    return f"""
You are a senior e-commerce fashion copywriter for the brand "{brand['store_name']}".

# DRIVING DATA (the ONLY source of figures & promo claims)
{_context_json(context)}

# BRAND STYLE GUIDE
- Tone: {brand['tone']}
- Audience: {brand['audience']}
- CTA: {brand['cta_rules']}
- The product link is always written as: {brand['product_link_placeholder']}
- Allowed hashtags: {", ".join(brand['hashtags'])}
- Promo rule: {brand['promo_rule']}
- Forbidden: {"; ".join(brand['forbidden'])}

# TIME SLOT CONTEXT
This is for the PRIME TIME {slot_label} slot. Match the wording to that time of day
(e.g. "grab one this morning", "before tonight"), but DO NOT invent offer mechanics
(vouchers, coupons, deadlines, specific flash windows) that are not present in the data.

# TASK
Write 3 ready-to-use promotional content formats based on the DRIVING DATA above.
MUST use the exact figures from the data (product name, remaining stock, discount %,
rating, testimonial, order counts). STRICTLY FORBIDDEN to add, change, or invent figures or
claims that are not present in the data.
{_anti_noise()}
{_marker_example()}
{extra}
""".strip()


def build_revision_prompt(
    context: dict[str, Any], slot: str, previous_draft: str, feedback: str
) -> str:
    return f"""
You are a senior copywriter revising a draft based on the reviewer's feedback.

# DRIVING DATA (mandatory source of figures)
{_context_json(context)}

# SLOT
PRIME TIME {settings.slot_label(slot)}

# PREVIOUS DRAFT
{previous_draft}

# REVIEWER FEEDBACK
{feedback}

# TASK
Rewrite the 3 content formats and address every point in the feedback.
{_anti_noise()}
Use EXACTLY this format:
{_marker_example()}

Promo figures must still match the DRIVING DATA.
""".strip()


def build_copywriter_agent() -> Agent:
    return Agent(
        name="copywriter",
        model=build_llm(settings),
        instruction=(
            "You are a copywriter for UMKM fashion promotional content. "
            "Output only the [TIKTOK]/[FEED]/[BROADCAST] blocks with their content, nothing else."
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
