"""Точка входа.

Локально — FastAPI + бот на polling + фоновый планировщик в одном процессе.
На Vercel постоянного процесса нет, поэтому там: апдейты приходят вебхуком,
а напоминания рассылает cron-эндпоинт, который дёргают извне.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot import db
from bot.api import api
from bot.bot_app import (
    get_bot, get_dispatcher, reminder_loop, send_due_reminders, setup_webhook, start_polling,
)
from bot.config import (
    BOT_TOKEN, CRON_SECRET, HOST, IS_SERVERLESS, PORT, WEBAPP_DIR, WEBHOOK_PATH,
    WEBHOOK_TOKEN, webapp_url,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("todo")

_db_ready = False


async def ensure_db() -> None:
    """Схема создаётся один раз на процесс (на Vercel — на холодный старт)."""
    global _db_ready
    if not _db_ready:
        await db.init()
        _db_ready = True


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await ensure_db()
    log.info("База готова")

    if IS_SERVERLESS:
        log.info("Serverless-режим: бот на вебхуке, напоминания через cron")
        yield
        return

    tasks = [
        asyncio.create_task(start_polling(), name="bot-polling"),
        asyncio.create_task(reminder_loop(), name="reminders"),
    ]
    log.info("Мини-приложение: http://%s:%s  (публичный URL: %s)",
             HOST, PORT, webapp_url() or "не задан")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Остановлено")


app = FastAPI(title="To-Do Rewards", lifespan=lifespan, docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api)


# ------------------------------------------------------------------- вебхук

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Dict[str, bool]:
    """Сюда Telegram присылает апдейты, когда бот работает вебхуком."""
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_TOKEN:
        raise HTTPException(status_code=403, detail="bad secret token")

    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=503, detail="BOT_TOKEN не задан")

    await ensure_db()

    from aiogram.types import Update
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await get_dispatcher().feed_update(bot, update)
    return {"ok": True}


# ---------------------------------------------------------- служебные ручки

@app.get("/api/cron/reminders")
async def cron_reminders(
    key: str = "",
    authorization: str = Header(default=""),
) -> Dict[str, Any]:
    """Рассылка наступивших напоминаний. Дёргается по расписанию извне
    (Vercel Cron шлёт секрет в заголовке Authorization, внешние сервисы — в ?key=)."""
    supplied = key or authorization.replace("Bearer ", "").strip()
    if supplied != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Неверный ключ")
    await ensure_db()
    sent = await send_due_reminders()
    return {"ok": True, "sent": sent}


@app.get("/api/setup")
async def setup(request: Request, key: str = "") -> Dict[str, Any]:
    """Одноразовая настройка: переключает бота на вебхук по текущему домену."""
    if key != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Неверный ключ")
    base = webapp_url() or str(request.base_url).rstrip("/")
    url = await setup_webhook(base)
    bot = get_bot()
    me = await bot.get_me()
    return {
        "ok": True,
        "bot": "@" + (me.username or ""),
        "webhook": url,
        "webapp": base,
        "cron": base + "/api/cron/reminders?key=" + CRON_SECRET,
    }


@app.get("/api/status")
async def status() -> Dict[str, Any]:
    bot = get_bot()
    info: Dict[str, Any] = {
        "serverless": IS_SERVERLESS,
        "token": bool(BOT_TOKEN),
        "database": bool(db.DATABASE_URL),
        "webapp_url": webapp_url(),
    }
    if bot is not None:
        hook = await bot.get_webhook_info()
        info["webhook"] = hook.url or None
        info["pending_updates"] = hook.pending_update_count
        info["last_error"] = hook.last_error_message
    return info


# ------------------------------------------------------------------ статика

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEBAPP_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


def run() -> None:
    import uvicorn
    if not BOT_TOKEN:
        log.warning("BOT_TOKEN пуст — бот не запустится. Заполни .env")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    run()
