"""Слой доступа к Postgres (asyncpg). Все времена — UTC epoch-секунды.

Postgres вместо SQLite, потому что на serverless-хостинге файловая система
только для чтения, а её содержимое не переживает перезапуск функции.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import asyncpg

from .config import DATABASE_URL, DEFAULT_TZ_OFFSET

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    tg_id         BIGINT  UNIQUE NOT NULL,
    name          TEXT    NOT NULL DEFAULT '',
    username      TEXT    NOT NULL DEFAULT '',
    xp            INTEGER NOT NULL DEFAULT 0,
    coins         INTEGER NOT NULL DEFAULT 0,
    streak        INTEGER NOT NULL DEFAULT 0,
    best_streak   INTEGER NOT NULL DEFAULT 0,
    last_done_day TEXT    NOT NULL DEFAULT '',
    total_done    INTEGER NOT NULL DEFAULT 0,
    tz_offset     INTEGER NOT NULL DEFAULT 3,
    theme         TEXT    NOT NULL DEFAULT 'aurora',
    created_at    BIGINT  NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    note        TEXT    NOT NULL DEFAULT '',
    emoji       TEXT    NOT NULL DEFAULT '📌',
    category    TEXT    NOT NULL DEFAULT 'personal',
    priority    INTEGER NOT NULL DEFAULT 1,
    due_at      BIGINT,
    remind_at   BIGINT,
    remind_sent INTEGER NOT NULL DEFAULT 0,
    "repeat"    TEXT    NOT NULL DEFAULT 'none',
    done        INTEGER NOT NULL DEFAULT 0,
    done_at     BIGINT,
    created_at  BIGINT  NOT NULL
);

CREATE TABLE IF NOT EXISTS achievements (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code        TEXT    NOT NULL,
    unlocked_at BIGINT  NOT NULL,
    UNIQUE (user_id, code)
);

CREATE TABLE IF NOT EXISTS purchases (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_code  TEXT    NOT NULL,
    price      INTEGER NOT NULL,
    created_at BIGINT  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_user   ON tasks(user_id, done);
CREATE INDEX IF NOT EXISTS idx_tasks_remind ON tasks(remind_at, remind_sent, done);
"""

# Поля задачи, которые разрешено менять снаружи
TASK_FIELDS = ("title", "note", "emoji", "category", "priority", "due_at",
               "remind_at", "remind_sent", "repeat", "done", "done_at")
USER_FIELDS = ("xp", "coins", "streak", "best_streak", "last_done_day",
               "total_done", "tz_offset", "theme", "name")

_pool: Optional[asyncpg.Pool] = None
_pool_loop: Optional[asyncio.AbstractEventLoop] = None


def now_ts() -> int:
    return int(time.time())


def _q(name: str) -> str:
    """repeat — имя функции в Postgres, поэтому колонку всегда цитируем."""
    return '"repeat"' if name == "repeat" else name


async def pool() -> asyncpg.Pool:
    """Пул на процесс. В serverless процесс переживает несколько запросов,
    поэтому пул экономит по 50-100 мс на каждом обращении."""
    global _pool, _pool_loop
    loop = asyncio.get_event_loop()
    if _pool is not None and _pool_loop is not loop:
        _pool = None                      # функцию подняли в новом цикле событий
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "Не задан DATABASE_URL — подключи базу (Vercel → Storage → Neon) "
                "или пропиши строку подключения в .env"
            )
        _pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=0, max_size=4, command_timeout=20,
            statement_cache_size=0,       # нужно для пулера Neon/Supabase
        )
        _pool_loop = loop
    return _pool


async def init() -> None:
    p = await pool()
    async with p.acquire() as conn:
        await conn.execute(SCHEMA)


def row_to_dict(row: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- пользователи

async def get_or_create_user(tg_id: int, name: str = "", username: str = "") -> Dict[str, Any]:
    p = await pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE tg_id = $1", tg_id)
        if row is None:
            row = await conn.fetchrow(
                """INSERT INTO users (tg_id, name, username, tz_offset, created_at)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (tg_id) DO UPDATE SET name = EXCLUDED.name
                   RETURNING *""",
                tg_id, name, username, DEFAULT_TZ_OFFSET, now_ts(),
            )
        elif name and row["name"] != name:
            row = await conn.fetchrow(
                "UPDATE users SET name = $1, username = $2 WHERE tg_id = $3 RETURNING *",
                name, username, tg_id,
            )
        return dict(row)


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    p = await pool()
    async with p.acquire() as conn:
        return row_to_dict(await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id))


async def update_user(user_id: int, **fields: Any) -> None:
    sets, values = [], []
    for key, value in fields.items():
        if key in USER_FIELDS:
            values.append(value)
            sets.append("{} = ${}".format(key, len(values)))
    if not sets:
        return
    values.append(user_id)
    p = await pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET {} WHERE id = ${}".format(", ".join(sets), len(values)), *values
        )


# --------------------------------------------------------------------- задачи

async def list_tasks(user_id: int, include_done: bool = True, limit: int = 500) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tasks WHERE user_id = $1"
    if not include_done:
        query += " AND done = 0"
    query += " ORDER BY done ASC, COALESCE(due_at, 9999999999) ASC, priority DESC, id DESC LIMIT $2"
    p = await pool()
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(query, user_id, limit)]


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    p = await pool()
    async with p.acquire() as conn:
        return row_to_dict(await conn.fetchrow(
            "SELECT * FROM tasks WHERE id = $1 AND user_id = $2", task_id, user_id))


async def create_task(user_id: int, **data: Any) -> Dict[str, Any]:
    p = await pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tasks (user_id, title, note, emoji, category, priority,
                                  due_at, remind_at, "repeat", created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *""",
            user_id,
            data.get("title", "Без названия"),
            data.get("note", ""),
            data.get("emoji", "📌"),
            data.get("category", "personal"),
            int(data.get("priority", 1)),
            data.get("due_at"),
            data.get("remind_at"),
            data.get("repeat", "none"),
            now_ts(),
        )
        return dict(row)


async def update_task(task_id: int, user_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
    sets, values = [], []
    for key, value in fields.items():
        if key in TASK_FIELDS:
            values.append(value)
            sets.append("{} = ${}".format(_q(key), len(values)))
    if not sets:
        return await get_task(task_id, user_id)
    values.extend([task_id, user_id])
    p = await pool()
    async with p.acquire() as conn:
        return row_to_dict(await conn.fetchrow(
            "UPDATE tasks SET {} WHERE id = ${} AND user_id = ${} RETURNING *".format(
                ", ".join(sets), len(values) - 1, len(values)),
            *values))


async def delete_task(task_id: int, user_id: int) -> bool:
    p = await pool()
    async with p.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM tasks WHERE id = $1 AND user_id = $2", task_id, user_id)
        return result.rsplit(" ", 1)[-1] != "0"


async def clear_done(user_id: int) -> int:
    p = await pool()
    async with p.acquire() as conn:
        result = await conn.execute("DELETE FROM tasks WHERE user_id = $1 AND done = 1", user_id)
        return int(result.rsplit(" ", 1)[-1])


async def due_reminders(upto: int) -> List[Dict[str, Any]]:
    """Задачи, по которым пора отправить напоминание."""
    p = await pool()
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(
            """SELECT t.*, u.tg_id AS tg_id
               FROM tasks t JOIN users u ON u.id = t.user_id
               WHERE t.done = 0 AND t.remind_sent = 0
                 AND t.remind_at IS NOT NULL AND t.remind_at <= $1
               ORDER BY t.remind_at LIMIT 100""", upto)]


async def mark_reminded(task_id: int) -> None:
    p = await pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE tasks SET remind_sent = 1 WHERE id = $1", task_id)


# --------------------------------------------------------------- достижения

async def list_achievements(user_id: int) -> List[Dict[str, Any]]:
    p = await pool()
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(
            "SELECT code, unlocked_at FROM achievements WHERE user_id = $1 ORDER BY unlocked_at",
            user_id)]


async def unlock_achievement(user_id: int, code: str) -> bool:
    """True, если достижение выдано впервые."""
    p = await pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO achievements (user_id, code, unlocked_at) VALUES ($1, $2, $3)
               ON CONFLICT (user_id, code) DO NOTHING RETURNING id""",
            user_id, code, now_ts())
        return row is not None


# ------------------------------------------------------------------- магазин

async def list_purchases(user_id: int) -> List[Dict[str, Any]]:
    p = await pool()
    async with p.acquire() as conn:
        return [dict(r) for r in await conn.fetch(
            "SELECT item_code, price, created_at FROM purchases WHERE user_id = $1 ORDER BY created_at DESC",
            user_id)]


async def add_purchase(user_id: int, item_code: str, price: int) -> None:
    p = await pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO purchases (user_id, item_code, price, created_at) VALUES ($1, $2, $3, $4)",
            user_id, item_code, price, now_ts())


async def stats_counters(user_id: int) -> Dict[str, int]:
    p = await pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT COALESCE(SUM(CASE WHEN done = 0 THEN 1 ELSE 0 END), 0) AS active,
                      COALESCE(SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END), 0) AS done
               FROM tasks WHERE user_id = $1""", user_id)
        return {"active": int(row["active"]), "done": int(row["done"])}
