from __future__ import annotations

import re
from typing import Any

from app.agents.copywriter import build_copywriter_agent, generate_copy, revise_copy
from app.agents.data_subagents import build_context
from app.agents.reviewer import build_reviewer_agent, review_draft
from app.config import settings
from app.delivery.telegram import save_output, send_telegram

SEPARATOR = "\u2501" * 38
MAX_REVIEW_ROUNDS = 2
MAX_GENERATION_ATTEMPTS = 3

_SECTION_MARKER = re.compile(r"\[(TIKTOK|FEED|BROADCAST)\]")
_TIKTOK_INNER = ("[Visual", "[Hook (0-3s)]", "[Body (4-12s)]", "[CTA (13-15s)]")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _clean_tiktok(section: str) -> str:
    vis = section.rfind("[Visual")
    hook = section.rfind("[Hook")
    start = min((x for x in (vis, hook) if x != -1), default=-1)
    if start == -1:
        return section.strip()
    cta = section.rfind("[CTA")
    if cta != -1:
        end = section.find("\n", cta)
        end = len(section) if end == -1 else end
        return section[start:end].strip()
    return section[start:].strip()


def parse_drafts(raw: str) -> dict[str, str]:
    """Split a copywriter response into {tiktok, feed, broadcast}.

    Strategy: find the ordered marker triplets [TIKTOK] -> [FEED] -> [BROADCAST]
    (the model may repeat them), then pick the LAST triplet that passes the sanity
    checks (video has 4 inner markers, feed looks like a real caption, broadcast
    carries numbers or a product link).
    """
    raw_clean = _strip_fences(raw)
    matches = list(_SECTION_MARKER.finditer(raw_clean))
    if not matches:
        raise ValueError(
            "Copywriter did not emit the [TIKTOK]/[FEED]/[BROADCAST] markers. "
            "Please trigger again."
        )

    triplets: list[tuple[int, int, int]] = []
    n = len(matches)
    i = 0
    while i < n:
        if matches[i].group(1) == "TIKTOK":
            j = i + 1
            while j < n and matches[j].group(1) != "FEED":
                j += 1
            k = j + 1
            while k < n and matches[k].group(1) != "BROADCAST":
                k += 1
            if j < n and k < n:
                triplets.append((i, j, k))
                i = j + 1
                continue
        i += 1

    if not triplets:
        raise ValueError(
            "Copywriter did not emit a complete [TIKTOK] -> [FEED] -> [BROADCAST] "
            "sequence. Please trigger again."
        )

    def extract(t: tuple[int, int, int]) -> dict[str, str]:
        ti, fj, bk = t
        # A broadcast ends at the end of the text or at the [TIKTOK] marker of the
        # next pass, so that inter-pass prose is not swallowed into the section.
        end = raw_clean.find("[TIKTOK]", matches[bk].end())
        if end == -1:
            end = len(raw_clean)
        return {
            "tiktok": raw_clean[matches[ti].end() : matches[fj].start()].strip("\n").strip(),
            "feed": raw_clean[matches[fj].end() : matches[bk].start()].strip("\n").strip(),
            "broadcast": raw_clean[matches[bk].end() : end].strip("\n").strip(),
        }

    def plausible(sections: dict[str, str]) -> dict[str, str] | None:
        tiktok = _clean_tiktok(sections["tiktok"])
        feed = sections["feed"]
        broadcast = sections["broadcast"]
        if (
            all(token in tiktok for token in _TIKTOK_INNER)
            and _feed_plausible(feed)
            and (("[Product Link]" in broadcast) or any(ch.isdigit() for ch in broadcast))
        ):
            return {"tiktok": tiktok, "feed": feed, "broadcast": broadcast}
        return None

    # Prefer the LAST triplet that passes the sanity checks: the model's final pass
    # is usually the cleanest; fall back to the first passing triplet.
    for t in reversed(triplets):
        result = plausible(extract(t))
        if result is not None:
            return result
    for t in triplets:
        result = plausible(extract(t))
        if result is not None:
            return result

    raise ValueError(
        "Copywriter emitted markers but the content is invalid (video missing the 4 "
        "inner markers, or feed/broadcast have no figures). Please trigger again."
    )


def _feed_plausible(feed: str) -> bool:
    """A feed is plausible when it has a quote line (starting with a quote char)
    AND at least one digit (stock figures)."""
    has_quote = any(line.strip().startswith(("\u201c", chr(34))) for line in feed.splitlines())
    has_number = any(ch.isdigit() for ch in feed)
    return has_quote and has_number


def _trigger_line(context: dict[str, Any]) -> str:
    primary = context["primary"]
    name = primary["product_name"]
    metric = f"Stock of {name}: {primary['stock_qty']} pcs left (Deadstock)"
    if "orders_24h" in primary:
        metric = (
            f"{name}: {primary['orders_24h']} orders in the last 24 hours "
            f"({primary['stock_qty']} pcs left)"
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
        f"\U0001f514 READY-TO-USE CONTENT RECOMMENDATION (PRIME TIME {label})\n"
        f"\U0001f4ca Trigger Data: {_trigger_line(context)}\n"
        f"{SEPARATOR}\n\n"
        f"\U0001f3ac 1. TIKTOK & SHOPEE VIDEO SCRIPT (~15 Seconds)\n"
        f"{drafts['tiktok'].strip()}\n\n"
        f"\U0001f4f8 2. INSTAGRAM & SHOPEE FEED CAPTION\n"
        f"{drafts['feed'].strip()}\n\n"
        f"\U0001f4ac 3. SHOPEE BROADCAST CHAT / WHATSAPP\n"
        f"{drafts['broadcast'].strip()}"
    )


async def _generate_draft(copywriter: Any, context: dict[str, Any], slot: str) -> dict[str, str]:
    """Generate the copywriter draft, retrying because the model may not obey markers."""
    note = ""
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        raw = await generate_copy(
            copywriter, context, slot, session_id=f"copy-{attempt}", extra=note
        )
        try:
            return parse_drafts(raw)
        except ValueError as exc:
            note = (
                "Your previous answer was INVALID: no complete [TIKTOK]/[FEED]/[BROADCAST] "
                "block could be parsed. Try ONCE MORE and write the final block directly - "
                "no chain-of-thought, no echoing the instructions."
            )
            if attempt == MAX_GENERATION_ATTEMPTS:
                raise ValueError(
                    f"Copywriter failed to produce a valid block after "
                    f"{MAX_GENERATION_ATTEMPTS} attempts: {exc}"
                ) from exc
    raise RuntimeError("unreachable")


async def run_pipeline(slot: str = "morning", dry_run: bool = False) -> dict[str, Any]:
    """Full orchestration: ingest -> copywriter -> reviewer loop (<=2) -> format -> deliver."""
    context = await build_context()

    primary = context["primary"]
    print(
        f"\U0001f9ed Target promo: {primary['product_name']} "
        f"(stock {primary['stock_qty']} pcs, discount {primary.get('discount_pct', 0)}%)"
    )

    copywriter = build_copywriter_agent()
    reviewer = build_reviewer_agent()

    drafts = await _generate_draft(copywriter, context, slot)
    revision_attempts = 0
    final_draft = drafts
    approved = False
    round_no = 0

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

        if round_no >= MAX_REVIEW_ROUNDS:
            break

        # Prefer the reviewer's own revision when usable; otherwise ask the copywriter
        # to revise using the reviewer's feedback (never stay stuck on the same draft).
        updated: dict[str, str] | None = None
        revised_text = (review.get("revised") or "").strip()
        if revised_text:
            try:
                updated = parse_drafts(revised_text)
            except ValueError as exc:
                print(f"  [i] Reviewer revision unparsable, asking the copywriter: {exc}")
        if updated is None:
            revision_attempts += 1
            try:
                raw = await revise_copy(
                    copywriter,
                    context,
                    slot,
                    joined,
                    review.get("feedback") or "improve the draft quality",
                    session_id=f"copy-revise-{revision_attempts}",
                )
                updated = parse_drafts(raw)
            except ValueError as exc:
                print(f"  [i] Copywriter revision invalid, keeping the previous draft: {exc}")
        if updated is not None:
            final_draft = updated

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
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are empty. "
            "Fill in .env (or run with --dry-run to see the result in the terminal)."
        )

    try:
        await send_telegram(message)
    except Exception as exc:
        raise RuntimeError(
            "Telegram delivery failed. Make sure: (1) you opened a chat with the bot and "
            "pressed /start, (2) TELEGRAM_CHAT_ID matches that chat (check via @userinfobot), "
            "(3) the bot token is still valid. Details: "
            f"{exc}"
        ) from exc
    return {
        "context": context,
        "drafts": final_draft,
        "approved": approved,
        "review_rounds": round_no,
        "message": message,
        "delivered_to": "telegram",
        "output_path": output_path,
    }
