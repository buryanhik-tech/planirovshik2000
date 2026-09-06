"""Настройки приложения — читаются из .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8080"))
DEFAULT_TZ_OFFSET: int = int(os.getenv("DEFAULT_TZ_OFFSET", "3"))
DEV_MODE: bool = os.getenv("DEV_MODE", "0") == "1"

DB_PATH: Path = BASE_DIR / "data.db"
WEBAPP_DIR: Path = BASE_DIR / "webapp"

# Сюда start.sh пишет актуальный адрес туннеля. Адрес меняется при каждом
# переподключении, поэтому читаем файл при каждом обращении, а не один раз.
RUNTIME_URL_FILE: Path = BASE_DIR / ".webapp_url"


def webapp_url() -> str:
    """Текущий публичный адрес мини-приложения ('' — если его нет)."""
    try:
        url = RUNTIME_URL_FILE.read_text().strip()
        if url:
            return url.rstrip("/")
    except OSError:
        pass
    return WEBAPP_URL

# Как часто планировщик проверяет напоминания (секунды)
REMINDER_TICK = 20
