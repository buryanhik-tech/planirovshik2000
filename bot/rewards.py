"""Игровая механика: опыт, уровни, монеты, серии, достижения и магазин."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import db

# --------------------------------------------------------------------- уровни

LEVEL_TITLES = [
    ("Новичок", "🌱"), ("Ученик", "🍀"), ("Деятель", "⚡"), ("Мастер списка", "🎯"),
    ("Профи", "🔥"), ("Ниндзя дел", "🥷"), ("Гуру порядка", "🧘"), ("Легенда", "👑"),
    ("Титан продуктивности", "🚀"), ("Бог тайм-менеджмента", "🌌"),
]


def xp_for_level(level: int) -> int:
    """Сколько всего опыта нужно, чтобы достичь уровня `level` (1-й = 0)."""
    return 50 * level * (level - 1)


def level_from_xp(xp: int) -> int:
    # решаем 50*n*(n-1) <= xp
    return max(1, int((1 + math.sqrt(1 + 4 * xp / 50)) / 2))


def level_info(xp: int) -> Dict[str, Any]:
    level = level_from_xp(xp)
    current = xp_for_level(level)
    nxt = xp_for_level(level + 1)
    title, emoji = LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)]
    span = max(1, nxt - current)
    return {
        "level": level,
        "title": title,
        "emoji": emoji,
        "xp": xp,
        "xp_level_start": current,
        "xp_next_level": nxt,
        "xp_into_level": xp - current,
        "xp_to_next": max(0, nxt - xp),
        "progress": round(min(1.0, (xp - current) / span), 4),
    }


# ---------------------------------------------------------------- достижения

ACHIEVEMENTS: List[Dict[str, Any]] = [
    {"code": "first_task",  "emoji": "🐣", "title": "Первый шаг",       "desc": "Выполни первую задачу",           "coins": 10},
    {"code": "done_10",     "emoji": "🔟", "title": "Разогрев",         "desc": "Выполни 10 задач",                "coins": 25},
    {"code": "done_50",     "emoji": "💪", "title": "На потоке",        "desc": "Выполни 50 задач",                "coins": 60},
    {"code": "done_100",    "emoji": "🏆", "title": "Сотка",            "desc": "Выполни 100 задач",               "coins": 150},
    {"code": "done_365",    "emoji": "🌟", "title": "Год продуктивности","desc": "Выполни 365 задач",              "coins": 500},
    {"code": "streak_3",    "emoji": "🔥", "title": "Три дня подряд",   "desc": "Серия из 3 дней",                 "coins": 20},
    {"code": "streak_7",    "emoji": "🚀", "title": "Неделя силы",      "desc": "Серия из 7 дней",                 "coins": 70},
    {"code": "streak_30",   "emoji": "💎", "title": "Железная воля",    "desc": "Серия из 30 дней",                "coins": 300},
    {"code": "early_bird",  "emoji": "🌅", "title": "Ранняя пташка",    "desc": "Задача выполнена до 8:00",        "coins": 30},
    {"code": "night_owl",   "emoji": "🦉", "title": "Полуночник",       "desc": "Задача выполнена после 23:00",    "coins": 30},
    {"code": "clean_day",   "emoji": "🧹", "title": "Чистый день",      "desc": "Закрой все задачи дня",           "coins": 40},
    {"code": "hard_5",      "emoji": "⚔️", "title": "Тяжеловес",        "desc": "Закрой 5 важных задач",           "coins": 50},
    {"code": "rich_500",    "emoji": "🪙", "title": "Копилка",          "desc": "Накопи 500 монет",                "coins": 50},
    {"code": "shopper",     "emoji": "🛍️", "title": "Первая покупка",   "desc": "Купи что-нибудь в магазине",      "coins": 15},
]

ACHIEVEMENT_BY_CODE = {a["code"]: a for a in ACHIEVEMENTS}


# ------------------------------------------------------------------- магазин

SHOP_ITEMS: List[Dict[str, Any]] = [
    {"code": "theme_aurora",  "emoji": "🌈", "title": "Тема «Аврора»",    "desc": "Неоново-фиолетовый градиент",     "price": 0,    "type": "theme"},
    {"code": "theme_sunset",  "emoji": "🌇", "title": "Тема «Закат»",     "desc": "Тёплый оранжево-розовый",         "price": 120,  "type": "theme"},
    {"code": "theme_ocean",   "emoji": "🌊", "title": "Тема «Океан»",     "desc": "Глубокая бирюза и синева",        "price": 120,  "type": "theme"},
    {"code": "theme_forest",  "emoji": "🌿", "title": "Тема «Лес»",       "desc": "Изумрудная свежесть",             "price": 180,  "type": "theme"},
    {"code": "theme_candy",   "emoji": "🍬", "title": "Тема «Карамель»",  "desc": "Сладкие пастельные тона",         "price": 180,  "type": "theme"},
    {"code": "theme_galaxy",  "emoji": "🌌", "title": "Тема «Галактика»", "desc": "Космос и звёздная пыль",          "price": 300,  "type": "theme"},
    {"code": "reward_coffee", "emoji": "☕", "title": "Кофе-брейк",       "desc": "Законный перерыв без чувства вины","price": 60,  "type": "reward"},
    {"code": "reward_series", "emoji": "🍿", "title": "Серия сериала",    "desc": "Одна серия — заслуженно",         "price": 100,  "type": "reward"},
    {"code": "reward_dayoff", "emoji": "🏖️", "title": "Выходной",         "desc": "День без задач, серия не сгорает","price": 400,  "type": "reward"},
    {"code": "reward_gift",   "emoji": "🎁", "title": "Подарок себе",     "desc": "Купи то, что давно хотел",        "price": 800,  "type": "reward"},
]

SHOP_BY_CODE = {i["code"]: i for i in SHOP_ITEMS}


# ------------------------------------------------------------ расчёт награды

BASE_XP = 10
PRIORITY_XP = {0: 0, 1: 5, 2: 15}
PRIORITY_LABEL = {0: ("🟢", "Спокойно"), 1: ("🟡", "Средне"), 2: ("🔴", "Важно")}


def local_day(ts: int, tz_offset: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=tz_offset)
    return dt.strftime("%Y-%m-%d")


def local_hour(ts: int, tz_offset: int) -> int:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=tz_offset)
    return dt.hour


def streak_multiplier(streak: int) -> float:
    return min(2.0, 1.0 + 0.1 * max(0, streak - 1))


async def complete_task(user: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    """Отмечает задачу выполненной и начисляет награды. Возвращает сводку."""
    now = db.now_ts()
    tz = user["tz_offset"]
    today = local_day(now, tz)
    yesterday = local_day(now - 86400, tz)

    # ---- серия
    streak = user["streak"]
    streak_grew = False
    if user["last_done_day"] == today:
        pass  # уже отмечались сегодня
    elif user["last_done_day"] == yesterday:
        streak += 1
        streak_grew = True
    else:
        streak = 1
        streak_grew = True
    best_streak = max(user["best_streak"], streak)

    # ---- опыт и монеты
    priority = int(task.get("priority", 1))
    xp = BASE_XP + PRIORITY_XP.get(priority, 5)

    bonuses: List[str] = []
    due = task.get("due_at")
    if due and now <= due:
        xp += 5
        bonuses.append("⏱ вовремя +5 XP")
    mult = streak_multiplier(streak)
    if mult > 1.0:
        bonuses.append("🔥 серия ×{:.1f}".format(mult))
    xp = int(round(xp * mult))
    coins = max(1, xp // 2)

    new_total_done = user["total_done"] + 1
    new_xp = user["xp"] + xp
    new_coins = user["coins"] + coins

    old_level = level_from_xp(user["xp"])
    new_level = level_from_xp(new_xp)
    level_up = new_level > old_level
    if level_up:
        level_bonus = 25 * new_level
        new_coins += level_bonus
        bonuses.append("🎉 новый уровень +{} 🪙".format(level_bonus))

    await db.update_task(
        task["id"], user["id"], done=1, done_at=now, remind_sent=1
    )
    await db.update_user(
        user["id"],
        xp=new_xp,
        coins=new_coins,
        streak=streak,
        best_streak=best_streak,
        last_done_day=today,
        total_done=new_total_done,
    )

    # ---- повторяющиеся задачи: создаём следующий экземпляр
    next_task = await _spawn_repeat(user, task)

    # ---- достижения
    fresh = dict(user)
    fresh.update({"xp": new_xp, "coins": new_coins, "streak": streak,
                  "total_done": new_total_done, "best_streak": best_streak})
    unlocked = await check_achievements(fresh, last_task=task, now=now)

    bonus_coins = sum(ACHIEVEMENT_BY_CODE[c]["coins"] for c in unlocked)
    if bonus_coins:
        new_coins += bonus_coins
        await db.update_user(user["id"], coins=new_coins)

    return {
        "task_id": task["id"],
        "title": task["title"],
        "xp": xp,
        "coins": coins + bonus_coins,
        "bonuses": bonuses,
        "level_up": level_up,
        "level": new_level,
        "streak": streak,
        "streak_grew": streak_grew,
        "achievements": [ACHIEVEMENT_BY_CODE[c] for c in unlocked],
        "next_task": next_task,
        "totals": {"xp": new_xp, "coins": new_coins, "total_done": new_total_done},
    }


async def uncomplete_task(user: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    """Снимает отметку. Забирает примерную награду обратно, чтобы не читерить."""
    priority = int(task.get("priority", 1))
    xp = BASE_XP + PRIORITY_XP.get(priority, 5)
    coins = max(1, xp // 2)
    new_xp = max(0, user["xp"] - xp)
    new_coins = max(0, user["coins"] - coins)
    await db.update_task(task["id"], user["id"], done=0, done_at=None, remind_sent=0)
    await db.update_user(
        user["id"], xp=new_xp, coins=new_coins,
        total_done=max(0, user["total_done"] - 1),
    )
    return {"xp": -xp, "coins": -coins, "totals": {"xp": new_xp, "coins": new_coins}}


async def _spawn_repeat(user: Dict[str, Any], task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    repeat = task.get("repeat", "none")
    if repeat in (None, "", "none"):
        return None

    def shift(ts: Optional[int]) -> Optional[int]:
        if not ts:
            return None
        base = datetime.fromtimestamp(ts, tz=timezone.utc)
        if repeat == "daily":
            base += timedelta(days=1)
        elif repeat == "weekly":
            base += timedelta(days=7)
        elif repeat == "weekdays":
            base += timedelta(days=1)
            local = base + timedelta(hours=user["tz_offset"])
            while local.weekday() >= 5:  # сб/вс
                base += timedelta(days=1)
                local = base + timedelta(hours=user["tz_offset"])
        return int(base.timestamp())

    due_at = shift(task.get("due_at"))
    remind_at = shift(task.get("remind_at"))
    if due_at is None and remind_at is None:
        due_at = db.now_ts() + 86400

    return await db.create_task(
        user["id"],
        title=task["title"],
        note=task.get("note", ""),
        emoji=task.get("emoji", "📌"),
        category=task.get("category", "personal"),
        priority=task.get("priority", 1),
        due_at=due_at,
        remind_at=remind_at,
        repeat=repeat,
    )


async def check_achievements(user: Dict[str, Any], last_task: Optional[Dict[str, Any]] = None,
                             now: Optional[int] = None) -> List[str]:
    """Выдаёт новые достижения, возвращает список кодов."""
    now = now or db.now_ts()
    tz = user["tz_offset"]
    earned: List[str] = []

    async def give(code: str) -> None:
        if await db.unlock_achievement(user["id"], code):
            earned.append(code)

    done = user["total_done"]
    if done >= 1:
        await give("first_task")
    if done >= 10:
        await give("done_10")
    if done >= 50:
        await give("done_50")
    if done >= 100:
        await give("done_100")
    if done >= 365:
        await give("done_365")

    if user["streak"] >= 3:
        await give("streak_3")
    if user["streak"] >= 7:
        await give("streak_7")
    if user["streak"] >= 30:
        await give("streak_30")

    if user["coins"] >= 500:
        await give("rich_500")

    if last_task is not None:
        hour = local_hour(now, tz)
        if hour < 8:
            await give("early_bird")
        if hour >= 23:
            await give("night_owl")

        counters = await db.stats_counters(user["id"])
        if counters["active"] == 0 and counters["done"] > 0:
            await give("clean_day")

        if int(last_task.get("priority", 1)) == 2:
            tasks = await db.list_tasks(user["id"])
            hard_done = sum(1 for t in tasks if t["done"] and t["priority"] == 2)
            if hard_done >= 5:
                await give("hard_5")

    return earned


async def buy_item(user: Dict[str, Any], code: str) -> Dict[str, Any]:
    item = SHOP_BY_CODE.get(code)
    if item is None:
        return {"ok": False, "error": "Такого товара нет 🤷"}

    owned = {p["item_code"] for p in await db.list_purchases(user["id"])}
    is_theme = item["type"] == "theme"

    if is_theme and (code in owned or item["price"] == 0):
        await db.update_user(user["id"], theme=code.replace("theme_", ""))
        return {"ok": True, "applied": True, "item": item, "coins": user["coins"]}

    if user["coins"] < item["price"]:
        return {"ok": False, "error": "Не хватает {} 🪙".format(item["price"] - user["coins"])}

    new_coins = user["coins"] - item["price"]
    await db.add_purchase(user["id"], code, item["price"])
    fields: Dict[str, Any] = {"coins": new_coins}
    if is_theme:
        fields["theme"] = code.replace("theme_", "")
    await db.update_user(user["id"], **fields)

    fresh = dict(user)
    fresh["coins"] = new_coins
    unlocked = await check_achievements(fresh)
    if await db.unlock_achievement(user["id"], "shopper"):
        unlocked.append("shopper")
    bonus = sum(ACHIEVEMENT_BY_CODE[c]["coins"] for c in unlocked if c in ACHIEVEMENT_BY_CODE)
    if bonus:
        new_coins += bonus
        await db.update_user(user["id"], coins=new_coins)

    return {
        "ok": True,
        "applied": is_theme,
        "item": item,
        "coins": new_coins,
        "achievements": [ACHIEVEMENT_BY_CODE[c] for c in unlocked if c in ACHIEVEMENT_BY_CODE],
    }
