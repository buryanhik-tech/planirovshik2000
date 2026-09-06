"""Настройки приложения. Локально читаются из .env, на Vercel — из переменных
окружения проекта."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def env(name: str, default: str = "") -> str:
    """Значение переменной окружения.

    os.getenv отдаёт значение по умолчанию, только когда переменной нет вовсе.
    Vercel же объявляет часть переменных пустыми (например PORT=""), поэтому
    пустое значение здесь тоже считается отсутствующим.
    """
    return (os.getenv(name) or "").strip() or default


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


BOT_TOKEN: str = env("BOT_TOKEN")
HOST: str = env("HOST", "0.0.0.0")
PORT: int = env_int("PORT", 8080)
DEFAULT_TZ_OFFSET: int = env_int("DEFAULT_TZ_OFFSET", 3)
DEV_MODE: bool = env("DEV_MODE", "0") == "1"

WEBAPP_DIR: Path = BASE_DIR / "webapp"

# --- где мы запущены ---------------------------------------------------------
# Vercel выставляет VERCEL=1. На нём нет ни постоянного процесса, ни диска:
# бот работает вебхуком, напоминания рассылает cron-эндпоинт.
IS_SERVERLESS: bool = bool(env("VERCEL"))

# --- база --------------------------------------------------------------------
# Интеграция Neon в Vercel подставляет DATABASE_URL и POSTGRES_URL сама.
DATABASE_URL: str = (
    env("DATABASE_URL") or env("POSTGRES_URL") or env("POSTGRES_PRISMA_URL")
).replace("postgres://", "postgresql://", 1)

# asyncpg не понимает эти параметры из строк Neon/Supabase
for _param in ("?sslmode=require", "&sslmode=require", "?pgbouncer=true", "&pgbouncer=true",
               "?supa=base-pooler.x", "&supa=base-pooler.x"):
    DATABASE_URL = DATABASE_URL.replace(_param, "")

# --- адрес мини-приложения ---------------------------------------------------
_ENV_WEBAPP_URL: str = env("WEBAPP_URL").rstrip("/")

# Постоянный домен продакшена (planirovshik2000.vercel.app), а не адрес
# конкретного деплоя — иначе кнопка ломалась бы после каждого пуша.
_VERCEL_URL: str = (
    env("VERCEL_PROJECT_PRODUCTION_URL") or env("VERCEL_URL")
).rstrip("/")
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
WEBHOOK_SECRET: str = env("WEBHOOK_SECRET") or _derive("webhook")
WEBHOOK_PATH: str = "/webhook/" + WEBHOOK_SECRET
# Telegram вернёт его в заголовке X-Telegram-Bot-Api-Secret-Token
WEBHOOK_TOKEN: str = _derive("header")
# Ключ для эндпоинта рассылки напоминаний
CRON_SECRET: str = env("CRON_SECRET") or _derive("cron")

# Как часто локальный планировщик проверяет напоминания (секунды)
REMINDER_TICK = 20
