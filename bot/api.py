"""REST API для мини-приложения."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from . import db, rewards
from .auth import resolve_user_payload
from .timeparse import parse_when

api = APIRouter(prefix="/api")


async def auth_user(init_data: Optional[str]) -> Dict[str, Any]:
    payload = resolve_user_payload(init_data or "")
    if payload is None:
        raise HTTPException(status_code=401, detail="Открой приложение через Telegram 🙃")
    name = " ".join(filter(None, [payload.get("first_name"), payload.get("last_name")])).strip()
    return await db.get_or_create_user(
        int(payload["id"]), name=name, username=payload.get("username") or ""
    )


class TaskIn(BaseModel):
    title: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=1000)
    emoji: str = Field(default="📌", max_length=8)
    category: str = Field(default="personal", max_length=32)
    priority: int = Field(default=1, ge=0, le=2)
    due_at: Optional[int] = None
    remind_at: Optional[int] = None
    repeat: str = Field(default="none")
    smart: bool = False  # разобрать время прямо из title


class TaskPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)
    emoji: Optional[str] = Field(default=None, max_length=8)
    category: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=2)
    due_at: Optional[int] = None
    remind_at: Optional[int] = None
    repeat: Optional[str] = None
    done: Optional[bool] = None


class BuyIn(BaseModel):
    code: str


class SettingsIn(BaseModel):
    tz_offset: Optional[int] = Field(default=None, ge=-12, le=14)
    theme: Optional[str] = None


def serialize_user(user: Dict[str, Any], counters: Dict[str, int],
                   unlocked: List[Dict[str, Any]]) -> Dict[str, Any]:
    info = rewards.level_info(user["xp"])
    return {
        "id": user["id"],
        "name": user["name"],
        "username": user["username"],
        "coins": user["coins"],
        "streak": user["streak"],
        "best_streak": user["best_streak"],
        "total_done": user["total_done"],
        "tz_offset": user["tz_offset"],
        "theme": user["theme"],
        "active": counters["active"],
        "done": counters["done"],
        "level": info,
        "achievements_unlocked": len(unlocked),
        "achievements_total": len(rewards.ACHIEVEMENTS),
    }


async def build_state(user: Dict[str, Any]) -> Dict[str, Any]:
    tasks = await db.list_tasks(user["id"])
    counters = await db.stats_counters(user["id"])
    unlocked = await db.list_achievements(user["id"])
    unlocked_map = {a["code"]: a["unlocked_at"] for a in unlocked}
    owned = {p["item_code"] for p in await db.list_purchases(user["id"])}

    return {
        "user": serialize_user(user, counters, unlocked),
        "tasks": tasks,
        "achievements": [
            dict(a, unlocked=a["code"] in unlocked_map, unlocked_at=unlocked_map.get(a["code"]))
            for a in rewards.ACHIEVEMENTS
        ],
        "shop": [
            dict(i, owned=i["code"] in owned or i["price"] == 0,
                 active=i["type"] == "theme" and i["code"].replace("theme_", "") == user["theme"])
            for i in rewards.SHOP_ITEMS
        ],
        "server_time": db.now_ts(),
    }


@api.get("/state")
async def get_state(x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    return await build_state(user)


@api.post("/tasks")
async def create_task(payload: TaskIn,
                      x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Пустая задача 🙃")

    due_at, remind_at = payload.due_at, payload.remind_at
    if payload.smart:
        ts, cleaned = parse_when(title, user["tz_offset"])
        if ts:
            title = cleaned or title
            due_at = due_at or ts
            remind_at = remind_at or ts

    task = await db.create_task(
        user["id"],
        title=title[:200],
        note=payload.note,
        emoji=payload.emoji or "📌",
        category=payload.category,
        priority=payload.priority,
        due_at=due_at,
        remind_at=remind_at,
        repeat=payload.repeat,
    )
    return {"task": task, "state": await build_state(await db.get_user_by_id(user["id"]))}


@api.patch("/tasks/{task_id}")
async def patch_task(task_id: int, payload: TaskPatch,
                     x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    task = await db.get_task(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    reward: Optional[Dict[str, Any]] = None
    fields = payload.model_dump(exclude_none=True)
    done = fields.pop("done", None)

    if fields:
        if "remind_at" in fields:
            fields["remind_sent"] = 0
        task = await db.update_task(task_id, user["id"], **fields)

    if done is True and not task["done"]:
        reward = await rewards.complete_task(user, task)
    elif done is False and task["done"]:
        reward = await rewards.uncomplete_task(user, task)

    fresh_user = await db.get_user_by_id(user["id"])
    return {
        "task": await db.get_task(task_id, user["id"]),
        "reward": reward,
        "state": await build_state(fresh_user),
    }


@api.delete("/tasks/{task_id}")
async def remove_task(task_id: int,
                      x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    ok = await db.delete_task(task_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"ok": True, "state": await build_state(await db.get_user_by_id(user["id"]))}


@api.post("/tasks/clear-done")
async def clear_done(x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    removed = await db.clear_done(user["id"])
    return {"removed": removed, "state": await build_state(await db.get_user_by_id(user["id"]))}


@api.post("/shop/buy")
async def buy(payload: BuyIn,
              x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    result = await rewards.buy_item(user, payload.code)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"result": result, "state": await build_state(await db.get_user_by_id(user["id"]))}


@api.post("/settings")
async def update_settings(payload: SettingsIn,
                          x_telegram_init_data: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await auth_user(x_telegram_init_data)
    fields = payload.model_dump(exclude_none=True)
    if fields:
        await db.update_user(user["id"], **fields)
    return {"state": await build_state(await db.get_user_by_id(user["id"]))}


@api.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "time": db.now_ts()}
