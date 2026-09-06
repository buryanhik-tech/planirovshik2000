"""Настройки приложения. Локально читаются из .env, на Vercel — из переменных
окружения проекта."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8080"))
DEFAULT_TZ_OFFSET: int = int(os.getenv("DEFAULT_TZ_OFFSET", "3"))
DEV_MODE: bool = os.getenv("DEV_MODE", "0") == "1"

WEBAPP_DIR: Path = BASE_DIR / "webapp"

# --- где мы запущены ---------------------------------------------------------
# Vercel выставляет VERCEL=1. На нём нет ни постоянного процесса, ни диска:
# бот работает вебхуком, напоминания рассылает cron-эндпоинт.
IS_SERVERLESS: bool = bool(os.getenv("VERCEL"))

# --- база --------------------------------------------------------------------
# Интеграция Neon в Vercel подставляет DATABASE_URL и POSTGRES_URL сама.
DATABASE_URL: str = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_PRISMA_URL")
    or ""
).strip().replace("postgres://", "postgresql://", 1)

# asyncpg не понимает эти параметры из строк Neon/Supabase
for _param in ("?sslmode=require", "&sslmode=require", "?pgbouncer=true", "&pgbouncer=true",
               "?supa=base-pooler.x", "&supa=base-pooler.x"):
    DATABASE_URL = DATABASE_URL.replace(_param, "")

# --- адрес мини-приложения ---------------------------------------------------
_ENV_WEBAPP_URL: str = os.getenv("WEBAPP_URL", "").strip().rstrip("/")

# Постоянный домен продакшена (planirovshik2000.vercel.app), а не адрес
# конкретного деплоя — иначе кнопка ломалась бы после каждого пуша.
_VERCEL_URL: str = (
    os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL") or ""
).strip().rstrip("/")
if _VERCEL_URL and not _VERCEL_URL.startswith("http"):
    _VERCEL_URL = "https://" + _VERCEL_URL

# Локально сюда start.sh пишет текущий адрес туннеля — он меняется, поэтому
# файл читается при каждом обращении, а не один раз при старте.
RUNTIME_URL_FILE: Path = BASE_DIR / ".webapp_url"

WEBAPP_URL: str = _ENV_WEBAPP_URL or _VERCEL_URL


def webapp_url() -> str:
    """Текущий публичный адрес мини-приложения ('' — если его нет)."""
    if _ENV_WEBAPP_URL:
        return _ENV_WEBAPP_URL
    try:
        url = RUNTIME_URL_FILE.read_text().strip()
        if url:
            return url.rstrip("/")
    except OSError:
        pass
    return _VERCEL_URL


# --- секреты -----------------------------------------------------------------
def _derive(purpose: str) -> str:
    """Стабильный секрет из токена бота: одинаковый локально и на сервере,
    отдельно задавать не нужно."""
    if not BOT_TOKEN:
        return purpose
    return hashlib.sha256((purpose + ":" + BOT_TOKEN).encode()).hexdigest()[:32]


# Путь вебхука не должен угадываться: иначе кто угодно пришлёт боту фейковый апдейт
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "").strip() or _derive("webhook")
WEBHOOK_PATH: str = "/webhook/" + WEBHOOK_SECRET
# Telegram вернёт его в заголовке X-Telegram-Bot-Api-Secret-Token
WEBHOOK_TOKEN: str = _derive("header")
# Ключ для эндпоинта рассылки напоминаний
CRON_SECRET: str = os.getenv("CRON_SECRET", "").strip() or _derive("cron")

# Как часто локальный планировщик проверяет напоминания (секунды)
REMINDER_TICK = 20
