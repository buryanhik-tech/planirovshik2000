"""Разовый перенос данных из локальной SQLite (data.db) в Postgres.

Запуск:  DATABASE_URL=... ./.venv/bin/python migrate_to_postgres.py
Ключи id пересоздаются, связи восстанавливаются по tg_id.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

import asyncpg

SQLITE = Path(__file__).parent / "data.db"


async def main() -> None:
    url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
    for param in ("?sslmode=require", "&sslmode=require", "?channel_binding=require",
                  "&channel_binding=require"):
        url = url.replace(param, "")
    if not url:
        sys.exit("Нужна переменная DATABASE_URL")
    if not SQLITE.exists():
        sys.exit("data.db не найден — переносить нечего")

    src = sqlite3.connect(SQLITE)
    src.row_factory = sqlite3.Row
    pg = await asyncpg.connect(url, statement_cache_size=0)

    moved = {"users": 0, "tasks": 0, "achievements": 0, "purchases": 0, "skipped": 0}
    try:
        for u in src.execute("SELECT * FROM users ORDER BY id"):
            exists = await pg.fetchval("SELECT id FROM users WHERE tg_id = $1", u["tg_id"])
            if exists:
                moved["skipped"] += 1
                new_id = exists
            else:
                new_id = await pg.fetchval(
                    """INSERT INTO users (tg_id, name, username, xp, coins, streak,
                                          best_streak, last_done_day, total_done,
                                          tz_offset, theme, created_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id""",
                    u["tg_id"], u["name"], u["username"], u["xp"], u["coins"], u["streak"],
                    u["best_streak"], u["last_done_day"], u["total_done"], u["tz_offset"],
                    u["theme"], u["created_at"])
                moved["users"] += 1

            for t in src.execute("SELECT * FROM tasks WHERE user_id = ?", (u["id"],)):
                await pg.execute(
                    """INSERT INTO tasks (user_id, title, note, emoji, category, priority,
                                          due_at, remind_at, remind_sent, "repeat", done,
                                          done_at, created_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                    new_id, t["title"], t["note"], t["emoji"], t["category"], t["priority"],
                    t["due_at"], t["remind_at"], t["remind_sent"], t["repeat"], t["done"],
                    t["done_at"], t["created_at"])
                moved["tasks"] += 1

            for a in src.execute("SELECT * FROM achievements WHERE user_id = ?", (u["id"],)):
                done = await pg.fetchval(
                    """INSERT INTO achievements (user_id, code, unlocked_at)
                       VALUES ($1,$2,$3) ON CONFLICT (user_id, code) DO NOTHING RETURNING id""",
                    new_id, a["code"], a["unlocked_at"])
                moved["achievements"] += 1 if done else 0

            for p in src.execute("SELECT * FROM purchases WHERE user_id = ?", (u["id"],)):
                await pg.execute(
                    "INSERT INTO purchases (user_id, item_code, price, created_at) VALUES ($1,$2,$3,$4)",
                    new_id, p["item_code"], p["price"], p["created_at"])
                moved["purchases"] += 1
    finally:
        await pg.close()
        src.close()

    print("Перенесено:")
    for key, value in moved.items():
        print("  {:<14} {}".format(key, value))


if __name__ == "__main__":
    asyncio.run(main())
