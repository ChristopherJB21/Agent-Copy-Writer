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

_SECTION_MARKER = re.compile(r"\[(TIKTOK|FEED|BROADCAST)\]")
_TIKTOK_INNER = ("[Visual", "[Hook (0-3s)]", "[Body (4-12s)]", "[CTA (13-15s)]")
_EMOJI_BULLET = ("\U0001f4e6", "\u2022", "\U0001f3f7\ufe0f", "\u26fd")


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
    """Pisahkan output copywriter menjadi {tiktok, feed, broadcast}.

    Strategi: cari TRIPLET marker pertama yang berurutan [TIKTOK] -> [FEED] -> [BROADCAST]
    (bisa diulang berkali-kali oleh model) dan pilih triplet pertama yang lolos sanity
    (video punya [CTA], feed ada bullet, broadcast tidak kosong).
    """
    raw_clean = _strip_fences(raw)
    matches = list(_SECTION_MARKER.finditer(raw_clean))
    if not matches:
        raise ValueError(
            "Copywriter tidak mengeluarkan marker [TIKTOK]/[FEED]/[BROADCAST]. "
            "Coba trigger ulang."
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
            "Copywriter tidak mengeluarkan urutan marker [TIKTOK] -> [FEED] -> [BROADCAST] "
            "yang lengkap. Coba trigger ulang."
        )

    def extract(t: tuple[int, int, int]) -> dict[str, str]:
        ti, fj, bk = t
        # Broadcast berakhir di akhir teks atau di marker [TIKTOK] pass berikutnya
        # (supaya prosa antar-pass tidak ikut terserap).
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
            and (("[Link Produk]" in broadcast) or any(ch.isdigit() for ch in broadcast))
        ):
            return {"tiktok": tiktok, "feed": feed, "broadcast": broadcast}
        return None

    # Prefer triplet TERAKHIR yang lolos sanity: blok final model (pass kedua) umumnya
    # paling bersih dan lengkap; fallback ke triplet pertama yang lolos.
    for t in reversed(triplets):
        result = plausible(extract(t))
        if result is not None:
            return result
    for t in triplets:
        result = plausible(extract(t))
        if result is not None:
            return result

    raise ValueError(
        "Copywriter mengeluarkan marker namun isi tidak valid (video tanpa 4 marker "
        "dalam, feed/broadcast tanpa angka). Coba trigger ulang."
    )


def _feed_plausible(feed: str) -> bool:
    """Feed dianggap valid bila ada kutipan (baris diawali ") DAN minimal satu angka."""
    has_quote = any(line.strip().startswith(("\u201c", chr(34))) for line in feed.splitlines())
    has_number = any(ch.isdigit() for ch in feed)
    return has_quote and has_number


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


MAX_GENERATION_ATTEMPTS = 3


async def _generate_draft(copywriter: Any, context: dict[str, Any], slot: str) -> dict[str, str]:
    """Generate copywriter dengan retry (model kadang tidak mematuhi marker blok)."""
    note = ""
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        raw = await generate_copy(
            copywriter, context, slot, session_id=f"copy-{attempt}", extra=note
        )
        try:
            return parse_drafts(raw)
        except ValueError as exc:
            note = (
                "Jawabanmu sebelumnya TIDAK VALID: tidak ada blok [TIKTOK]/[FEED]/[BROADCAST] "
                "lengkap yang bisa diparsing. ULANGI SEKALI LAGI, langsung tulis blok final "
                "tanpa proses berpikir, tanpa menyalin instruksi."
            )
            if attempt == MAX_GENERATION_ATTEMPTS:
                raise ValueError(
                    f"Copywriter gagal menghasilkan blok valid setelah "
                    f"{MAX_GENERATION_ATTEMPTS} percobaan: {exc}"
                ) from exc
    raise RuntimeError("unreachable")


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
    revision_attempts = 0
    final_draft = drafts
    approved = False

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
        if round_no < MAX_REVIEW_ROUNDS and revised_text:
            try:
                final_draft = parse_drafts(revised_text)
            except ValueError as exc:
                print(f"  [i] Koreksi reviewer tidak valid, dipakai draft lama: {exc}")
            continue

        if round_no < MAX_REVIEW_ROUNDS:
            revision_attempts += 1
            try:
                raw = await revise_copy(
                    copywriter,
                    context,
                    slot,
                    joined,
                    review.get("feedback") or "perbaiki kualitas draft",
                    session_id=f"copy-revise-{revision_attempts}",
                )
                final_draft = parse_drafts(raw)
            except ValueError as exc:
                print(f"  [i] Revisi copywriter tidak valid, dipakai draft lama: {exc}")

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

    try:
        await send_telegram(message)
    except Exception as exc:
        raise RuntimeError(
            "Kirim Telegram gagal. Pastikan: (1) kamu sudah membuka chat bot dan menekan "
            "/start, (2) TELEGRAM_CHAT_ID adalah chat yang sama (cek via @userinfobot), "
            "(3) token bot masih valid. Detail: "
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
