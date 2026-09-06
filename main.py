"""Точка входа: FastAPI (мини-приложение + API) и бот в одном процессе."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot import db
from bot.api import api
from bot.bot_app import reminder_loop, start_polling
from bot.config import BOT_TOKEN, HOST, PORT, WEBAPP_DIR, webapp_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("todo")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.init()
    log.info("База готова")

    tasks = [
        asyncio.create_task(start_polling(), name="bot-polling"),
        asyncio.create_task(reminder_loop(), name="reminders"),
    ]
    log.info("Мини-приложение: http://%s:%s  (публичный URL: %s)", HOST, PORT, webapp_url() or "не задан")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Остановлено")


app = FastAPI(title="To-Do Rewards", lifespan=lifespan, docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEBAPP_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


def run() -> None:
    if not BOT_TOKEN:
        log.warning("BOT_TOKEN пуст — бот не запустится. Заполни .env")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    run()
