"""Слой доступа к SQLite. Все времена хранятся как UTC epoch-секунды."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import aiosqlite

from .config import DB_PATH, DEFAULT_TZ_OFFSET

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id        INTEGER UNIQUE NOT NULL,
    name         TEXT    NOT NULL DEFAULT '',
    username     TEXT    NOT NULL DEFAULT '',
    xp           INTEGER NOT NULL DEFAULT 0,
    coins        INTEGER NOT NULL DEFAULT 0,
    streak       INTEGER NOT NULL DEFAULT 0,
    best_streak  INTEGER NOT NULL DEFAULT 0,
    last_done_day TEXT   NOT NULL DEFAULT '',
    total_done   INTEGER NOT NULL DEFAULT 0,
    tz_offset    INTEGER NOT NULL DEFAULT 3,
    theme        TEXT    NOT NULL DEFAULT 'aurora',
    created_at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    title        TEXT    NOT NULL,
    note         TEXT    NOT NULL DEFAULT '',
    emoji        TEXT    NOT NULL DEFAULT '📌',
    category     TEXT    NOT NULL DEFAULT 'personal',
    priority     INTEGER NOT NULL DEFAULT 1,   -- 0 низкий, 1 средний, 2 высокий
    due_at       INTEGER,                       -- срок (epoch, UTC)
    remind_at    INTEGER,                       -- когда напомнить (epoch, UTC)
    remind_sent  INTEGER NOT NULL DEFAULT 0,
    repeat       TEXT    NOT NULL DEFAULT 'none', -- none|daily|weekly|weekdays
    done         INTEGER NOT NULL DEFAULT 0,
    done_at      INTEGER,
    created_at   INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS achievements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    code        TEXT    NOT NULL,
    unlocked_at INTEGER NOT NULL,
    UNIQUE (user_id, code)
);

CREATE TABLE IF NOT EXISTS purchases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    item_code  TEXT    NOT NULL,
    price      INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_user   ON tasks(user_id, done);
CREATE INDEX IF NOT EXISTS idx_tasks_remind ON tasks(remind_at, remind_sent, done);
"""


def now_ts() -> int:
    return int(time.time())


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def init() -> None:
    conn = await connect()
    try:
        await conn.executescript(SCHEMA)
        await conn.commit()
    finally:
        await conn.close()


def row_to_dict(row: Optional[aiosqlite.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- пользователи

async def get_or_create_user(tg_id: int, name: str = "", username: str = "") -> Dict[str, Any]:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        if row is None:
            await conn.execute(
                "INSERT INTO users (tg_id, name, username, tz_offset, created_at) VALUES (?, ?, ?, ?, ?)",
                (tg_id, name, username, DEFAULT_TZ_OFFSET, now_ts()),
            )
            await conn.commit()
            cur = await conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
        elif name and row["name"] != name:
            await conn.execute("UPDATE users SET name = ?, username = ? WHERE tg_id = ?", (name, username, tg_id))
            await conn.commit()
            cur = await conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
        return dict(row)
    finally:
        await conn.close()


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return row_to_dict(await cur.fetchone())
    finally:
        await conn.close()


async def update_user(user_id: int, **fields: Any) -> None:
    if not fields:
        return
    allowed = {"xp", "coins", "streak", "best_streak", "last_done_day", "total_done", "tz_offset", "theme", "name"}
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("{} = ?".format(key))
            values.append(value)
    if not sets:
        return
    values.append(user_id)
    conn = await connect()
    try:
        await conn.execute("UPDATE users SET {} WHERE id = ?".format(", ".join(sets)), values)
        await conn.commit()
    finally:
        await conn.close()


# --------------------------------------------------------------------- задачи

async def list_tasks(user_id: int, include_done: bool = True, limit: int = 500) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tasks WHERE user_id = ?"
    if not include_done:
        query += " AND done = 0"
    query += " ORDER BY done ASC, COALESCE(due_at, 9999999999) ASC, priority DESC, id DESC LIMIT ?"
    conn = await connect()
    try:
        cur = await conn.execute(query, (user_id, limit))
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        return row_to_dict(await cur.fetchone())
    finally:
        await conn.close()


async def create_task(user_id: int, **data: Any) -> Dict[str, Any]:
    conn = await connect()
    try:
        cur = await conn.execute(
            """INSERT INTO tasks (user_id, title, note, emoji, category, priority, due_at, remind_at, repeat, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
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
            ),
        )
        await conn.commit()
        task_id = cur.lastrowid
        cur = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return dict(await cur.fetchone())
    finally:
        await conn.close()


async def update_task(task_id: int, user_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
    allowed = {
        "title", "note", "emoji", "category", "priority", "due_at",
        "remind_at", "remind_sent", "repeat", "done", "done_at",
    }
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("{} = ?".format(key))
            values.append(value)
    if not sets:
        return await get_task(task_id, user_id)
    values.extend([task_id, user_id])
    conn = await connect()
    try:
        await conn.execute(
            "UPDATE tasks SET {} WHERE id = ? AND user_id = ?".format(", ".join(sets)), values
        )
        await conn.commit()
        cur = await conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        return row_to_dict(await cur.fetchone())
    finally:
        await conn.close()


async def delete_task(task_id: int, user_id: int) -> bool:
    conn = await connect()
    try:
        cur = await conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        await conn.commit()
        return cur.rowcount > 0
    finally:
        await conn.close()


async def clear_done(user_id: int) -> int:
    conn = await connect()
    try:
        cur = await conn.execute("DELETE FROM tasks WHERE user_id = ? AND done = 1", (user_id,))
        await conn.commit()
        return cur.rowcount
    finally:
        await conn.close()


async def due_reminders(upto: int) -> List[Dict[str, Any]]:
    """Задачи, по которым пора отправить напоминание."""
    conn = await connect()
    try:
        cur = await conn.execute(
            """SELECT t.*, u.tg_id AS tg_id
               FROM tasks t JOIN users u ON u.id = t.user_id
               WHERE t.done = 0 AND t.remind_sent = 0
                 AND t.remind_at IS NOT NULL AND t.remind_at <= ?""",
            (upto,),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()


async def mark_reminded(task_id: int) -> None:
    conn = await connect()
    try:
        await conn.execute("UPDATE tasks SET remind_sent = 1 WHERE id = ?", (task_id,))
        await conn.commit()
    finally:
        await conn.close()


# --------------------------------------------------------------- достижения

async def list_achievements(user_id: int) -> List[Dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute(
            "SELECT code, unlocked_at FROM achievements WHERE user_id = ? ORDER BY unlocked_at", (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()


async def unlock_achievement(user_id: int, code: str) -> bool:
    """True, если достижение выдано впервые."""
    conn = await connect()
    try:
        try:
            await conn.execute(
                "INSERT INTO achievements (user_id, code, unlocked_at) VALUES (?, ?, ?)",
                (user_id, code, now_ts()),
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False
    finally:
        await conn.close()


# ------------------------------------------------------------------- магазин

async def list_purchases(user_id: int) -> List[Dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute(
            "SELECT item_code, price, created_at FROM purchases WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()


async def add_purchase(user_id: int, item_code: str, price: int) -> None:
    conn = await connect()
    try:
        await conn.execute(
            "INSERT INTO purchases (user_id, item_code, price, created_at) VALUES (?, ?, ?, ?)",
            (user_id, item_code, price, now_ts()),
        )
        await conn.commit()
    finally:
        await conn.close()


async def stats_counters(user_id: int) -> Dict[str, int]:
    conn = await connect()
    try:
        cur = await conn.execute(
            """SELECT
                 SUM(CASE WHEN done = 0 THEN 1 ELSE 0 END) AS active,
                 SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS done
               FROM tasks WHERE user_id = ?""",
            (user_id,),
        )
        row = await cur.fetchone()
        return {"active": row["active"] or 0, "done": row["done"] or 0}
    finally:
        await conn.close()
