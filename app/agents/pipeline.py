from __future__ import annotations

import re
from typing import Any

from app.agents.copywriter import (
    build_copywriter_agent,
    generate_copy,
    revise_copy,
)
from app.agents.data_subagents import build_context
from app.agents.reviewer import build_reviewer_agent, review_draft
from app.config import settings
from app.delivery.telegram import save_output, send_telegram

SEPARATOR = "\u2501" * 38
MAX_REVIEW_ROUNDS = 2

_SECTION_MARKER = re.compile(r"\[(TIKTOK|FEED|BROADCAST)\]")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_drafts(raw: str) -> dict[str, str]:
    """Pisahkan output copywriter menjadi {tiktok, feed, broadcast}."""
    raw_clean = _strip_fences(raw)
    matches = list(_SECTION_MARKER.finditer(raw_clean))
    if not matches:
        raise ValueError(
            "Copywriter tidak mengeluarkan marker [TIKTOK]/[FEED]/[BROADCAST]. "
            "Coba trigger ulang."
        )
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        section = match.group(1).lower()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_clean)
        sections[section] = raw_clean[start:end].strip("\n")
    missing = [m for m in ("tiktok", "feed", "broadcast") if m not in sections]
    if missing:
        raise ValueError(f"Copywriter tidak menghasilkan section {missing}. Coba trigger ulang.")
    return sections


def _fmt(value: Any) -> str:
    return str(value)


def _trigger_line(context: dict[str, Any]) -> str:
    primary = context["primary"]
    name = primary["product_name"]
    metric = f"Stok {name} tersisa {primary['stock_qty']} pcs (Deadstock)"
    if "orders_24h" in primary:
        metric = (
            f"{name} laku {primary['orders_24h']} order dalam 24 jam "
            f"(stok tersisa {primary['stock_qty']} pcs)"
        )
    rating = context.get("rating") or {}
    avg = rating.get("avg_rating")
    reviews = context.get("reviews") or []
    if avg is not None and reviews:
        quote = reviews[0]["review_text"]
        return f"{metric} + Review Rating {avg} \u2b50 (\u201c{quote}\u201d)"
    if avg is not None:
        return f"{metric} + Review Rating {avg} \u2b50"
    return metric


def format_final_message(context: dict[str, Any], drafts: dict[str, str], slot: str) -> str:
    label = settings.slot_label(slot)
    return (
        f"\U0001f514 REKOMENDASI KONTEN SIAP PAKAI (PRIME TIME {label})\n"
        f"\U0001f4ca Trigger Data: {_trigger_line(context)}\n"
        f"{SEPARATOR}\n\n"
        f"\U0001f3ac 1. SKRIP TIKTOK & SHOPEE VIDEO (~15 Detik)\n"
        f"{drafts['tiktok'].strip()}\n\n"
        f"\U0001f4f8 2. CAPTION INSTAGRAM & SHOPEE FEED\n"
        f"{drafts['feed'].strip()}\n\n"
        f"\U0001f4ac 3. SHOPEE BROADCAST CHAT / WHATSAPP\n"
        f"{drafts['broadcast'].strip()}"
    )


async def _generate_draft(copywriter: Any, context: dict[str, Any], slot: str) -> dict[str, str]:
    raw = await generate_copy(copywriter, context, slot, session_id="copy")
    return parse_drafts(raw)


async def run_pipeline(slot: str = "siang", dry_run: bool = False) -> dict[str, Any]:
    """Orkestrasi penuh: ingest -> copywriter -> reviewer loop (<=2) -> format -> deliver."""
    context = await build_context()

    primary = context["primary"]
    print(
        f"\U0001f9ed Target promo: {primary['product_name']} "
        f"(stok {primary['stock_qty']} pcs, diskon {primary.get('discount_pct', 0)}%)"
    )

    copywriter = build_copywriter_agent()
    reviewer = build_reviewer_agent()

    drafts = await _generate_draft(copywriter, context, slot)
    revision_iterations = 0
    final_draft = drafts

    for round_no in range(1, MAX_REVIEW_ROUNDS + 1):
        joined = "\n\n".join(final_draft[k].strip() for k in ("tiktok", "feed", "broadcast"))
        review = await review_draft(reviewer, joined, context, session_id=f"review-{round_no}")
        approved = bool(review.get("approved"))
        print(
            f"\U0001f50d Review {round_no}/{MAX_REVIEW_ROUNDS}: "
            f"score={review.get('score')} approved={approved}"
            + (f" -- {review.get('feedback')}" if review.get("feedback") else "")
        )
        if approved:
            break

        revised_text = (review.get("revised") or "").strip()
        if round_no < MAX_REVIEW_ROUNDS:
            if revised_text:
                final_draft = parse_drafts(revised_text)
            else:
                feedback = review.get("feedback") or "perbaiki kualitas draft"
                revision_iterations += 1
                raw = await revise_copy(
                    copywriter,
                    context,
                    slot,
                    joined,
                    feedback,
                    session_id=f"copy-revise-{revision_iterations}",
                )
                final_draft = parse_drafts(raw)
            continue

        if revised_text:
            final_draft = parse_drafts(revised_text)

    message = format_final_message(context, final_draft, slot)
    output_path = save_output(message, slot)

    if dry_run:
        return {
            "context": context,
            "drafts": final_draft,
            "approved": approved,
            "review_rounds": round_no,
            "message": message,
            "delivered_to": "dry-run",
            "output_path": output_path,
        }

    if not settings.telegram_configured:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID kosong. "
            "Isi .env (atau jalankan dengan --dry-run untuk melihat hasil di terminal)."
        )

    await send_telegram(message)
    return {
        "context": context,
        "drafts": final_draft,
        "approved": approved,
        "review_rounds": round_no,
        "message": message,
        "delivered_to": "telegram",
        "output_path": output_path,
    }
