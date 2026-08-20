from __future__ import annotations

from datetime import datetime
from pathlib import Path

from telegram import Bot
from telegram.ext import Application

from app.config import settings


def save_output(text: str, slot: str) -> Path:
    """Save a copy of the final message to outputs/ (used by dry-run and as archive)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    path = settings.outputs_dir / f"{stamp}_{slot}.txt"
    path.write_text(text, encoding="utf-8")
    return path


async def send_telegram(text: str) -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()
    bot: Bot = app.bot
    try:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=settings.telegram_parse_mode or None,
        )
    finally:
        await app.shutdown()
