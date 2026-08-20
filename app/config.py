from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

VALID_SLOTS = ("morning", "evening", "night")

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/marketing_copilot"


def _env(key: str, default: str = "") -> str:
    value = os.getenv(key)
    return value if value is not None else default


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_model: str
    llm_max_tokens: int
    llm_api_key: str
    llm_base_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_parse_mode: str
    slot_labels: dict[str, str]
    outputs_dir: Path = field(default_factory=lambda: OUTPUTS_DIR)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def slot_label(self, slot: str) -> str:
        return self.slot_labels.get(slot, slot.upper())


def load_settings() -> Settings:
    return Settings(
        database_url=_env("DATABASE_URL", DEFAULT_DATABASE_URL),
        llm_model=_env("LLM_MODEL", "my-free-deepseek-v4-flash"),
        llm_max_tokens=int(_env("LLM_MAX_TOKENS", "2048")),
        llm_api_key=_env("OPENAI_API_KEY"),
        llm_base_url=_env("OPENAI_BASE_URL"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
        telegram_parse_mode=_env("TELEGRAM_PARSE_MODE"),
        slot_labels={
            "morning": _env("PRIME_TIME_MORNING", "MORNING"),
            "evening": _env("PRIME_TIME_EVENING", "EVENING"),
            "night": _env("PRIME_TIME_NIGHT", "NIGHT"),
        },
        outputs_dir=OUTPUTS_DIR,
    )


settings = load_settings()
