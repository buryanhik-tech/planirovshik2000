"""Хендлеры бота: команды, добавление задач текстом, кнопки."""
from __future__ import annotations

import html
from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from . import db, rewards
from .keyboards import created_keyboard, main_menu, shop_keyboard, tasks_keyboard, webapp_button
from .timeparse import fmt_dt, parse_when

router = Router()

EMOJI_HINTS = [
    (("куп", "магаз", "продукт", "молок", "хлеб"), "🛒"),
    (("позвон", "звон", "набер"), "📞"),
    (("встреч", "созвон", "митап", "интервью"), "🤝"),
    (("трен", "зал", "спорт", "бег", "зарядк", "йог"), "🏋️"),
    (("учи", "англ", "курс", "урок", "лекц", "чита"), "📚"),
    (("работ", "отчёт", "отчет", "задач", "проект", "дедлайн"), "💼"),
    (("врач", "аптек", "таблет", "зуб"), "🏥"),
    (("убор", "мыть", "постир", "посуд", "пылес"), "🧹"),
    (("плат", "счёт", "счет", "налог", "банк"), "💳"),
    (("подар", "днюх", "день рожд", "праздник"), "🎁"),
    (("код", "деплой", "баг", "релиз", "коммит"), "💻"),
    (("напис", "письм", "почт", "email"), "✉️"),
]


def guess_emoji(title: str) -> str:
    low = title.lower()
    for keys, emoji in EMOJI_HINTS:
        if any(k in low for k in keys):
            return emoji
    return "📌"


def guess_priority(text: str) -> int:
    low = text.lower()
    if "!!" in text or any(w in low for w in ("срочно", "важно", "горит", "asap")):
        return 2
    if "?" in text or any(w in low for w in ("когда-нибудь", "не срочно", "потом")):
        return 0
    return 1


def esc(text: str) -> str:
    return html.escape(text or "")


async def current_user(message_or_cb) -> Dict[str, Any]:
    tg = message_or_cb.from_user
    return await db.get_or_create_user(
        tg.id,
        name=(tg.full_name or "").strip(),
        username=(tg.username or ""),
    )


# --------------------------------------------------------------------- /start

WELCOME = (
    "<b>Привет, {name}! 👋</b>\n\n"
    "Я твой то-ду бот с наградами 🎮\n\n"
    "✍️ Просто напиши задачу — я её сохраню.\n"
    "⏰ Можно с временем: <i>«завтра в 18:00 позвонить маме»</i> или <i>«через 2 часа отчёт»</i>.\n"
    "🏆 За выполнение — опыт, монеты, уровни и достижения.\n"
    "🔥 Не пропускай дни — серия даёт множитель наград.\n\n"
    "Команды: /list /today /stats /shop /help"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = await current_user(message)
    await message.answer(
        WELCOME.format(name=esc(user["name"] or "друг")),
        reply_markup=main_menu(),
    )
    kb = webapp_button("🚀 Открыть To-Do приложение")
    if kb:
        await message.answer("Красивый интерфейс — здесь 👇", reply_markup=kb)
    else:
        await message.answer(
            "ℹ️ Мини-приложение пока не подключено: задай <code>WEBAPP_URL</code> "
            "(https) в .env и укажи его в @BotFather → Menu Button."
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Как пользоваться 📖</b>\n\n"
        "• Любой текст → новая задача\n"
        "• <code>завтра в 9:00 к врачу</code> → задача с напоминанием\n"
        "• <code>через 40 минут вынести мусор</code>\n"
        "• <code>купить кофе !!</code> → высокий приоритет 🔴\n\n"
        "<b>Команды</b>\n"
        "/list — активные задачи\n"
        "/today — что на сегодня\n"
        "/stats — уровень, монеты, серия\n"
        "/shop — магазин наград\n"
        "/clear — убрать выполненные\n",
        reply_markup=main_menu(),
    )


# --------------------------------------------------------------- список задач

def render_task(task: Dict[str, Any], tz: int) -> str:
    prio_emoji, _ = rewards.PRIORITY_LABEL.get(int(task["priority"]), ("🟡", ""))
    line = "{} {} <b>{}</b>".format(prio_emoji, task["emoji"], esc(task["title"]))
    extras: List[str] = []
    if task["remind_at"]:
        extras.append("⏰ {}".format(fmt_dt(task["remind_at"], tz)))
    elif task["due_at"]:
        extras.append("📅 {}".format(fmt_dt(task["due_at"], tz)))
    if task["repeat"] != "none":
        extras.append({"daily": "🔁 каждый день", "weekly": "🔁 каждую неделю",
                       "weekdays": "🔁 по будням"}.get(task["repeat"], "🔁"))
    if extras:
        line += "\n   <i>{}</i>".format(" · ".join(extras))
    return line


async def send_task_list(message: Message, only_today: bool = False) -> None:
    user = await current_user(message)
    tasks = [t for t in await db.list_tasks(user["id"], include_done=False)]

    if only_today:
        today = rewards.local_day(db.now_ts(), user["tz_offset"])
        tasks = [
            t for t in tasks
            if (t["remind_at"] and rewards.local_day(t["remind_at"], user["tz_offset"]) <= today)
            or (t["due_at"] and rewards.local_day(t["due_at"], user["tz_offset"]) <= today)
        ]

    if not tasks:
        text = "🎉 На сегодня всё чисто!" if only_today else "📭 Активных задач нет.\nНапиши что-нибудь — и я добавлю."
        await message.answer(text, reply_markup=main_menu())
        return

    header = "📅 <b>На сегодня — {}</b>".format(len(tasks)) if only_today else "📋 <b>Активные задачи — {}</b>".format(len(tasks))
    body = "\n\n".join(render_task(t, user["tz_offset"]) for t in tasks[:20])
    await message.answer("{}\n\n{}".format(header, body), reply_markup=tasks_keyboard(tasks))


@router.message(Command("list"))
@router.message(F.text == "📋 Мои задачи")
async def cmd_list(message: Message) -> None:
    await send_task_list(message, only_today=False)


@router.message(Command("today"))
@router.message(F.text == "📅 На сегодня")
async def cmd_today(message: Message) -> None:
    await send_task_list(message, only_today=True)


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    user = await current_user(message)
    removed = await db.clear_done(user["id"])
    await message.answer("🧹 Убрано выполненных: <b>{}</b>".format(removed))


# ------------------------------------------------------------------- профиль

@router.message(Command("stats"))
@router.message(F.text == "🏆 Профиль")
async def cmd_stats(message: Message) -> None:
    user = await current_user(message)
    info = rewards.level_info(user["xp"])
    counters = await db.stats_counters(user["id"])
    unlocked = await db.list_achievements(user["id"])

    filled = int(info["progress"] * 10)
    bar = "🟩" * filled + "⬜️" * (10 - filled)

    text = (
        "{} <b>{}</b> · уровень {}\n"
        "{}\n"
        "<b>{}</b> / {} XP  (до следующего — {})\n\n"
        "🪙 Монеты: <b>{}</b>\n"
        "🔥 Серия: <b>{}</b> дн. (рекорд {})\n"
        "✅ Выполнено всего: <b>{}</b>\n"
        "📋 Активных: <b>{}</b>\n"
        "🏅 Достижений: <b>{}</b> из {}"
    ).format(
        info["emoji"], esc(user["name"] or "Герой"), info["level"], bar,
        info["xp"], info["xp_next_level"], info["xp_to_next"],
        user["coins"], user["streak"], user["best_streak"],
        user["total_done"], counters["active"],
        len(unlocked), len(rewards.ACHIEVEMENTS),
    )

    if unlocked:
        codes = [a["code"] for a in unlocked][-8:]
        badges = " ".join(rewards.ACHIEVEMENT_BY_CODE[c]["emoji"] for c in codes if c in rewards.ACHIEVEMENT_BY_CODE)
        text += "\n\n{}".format(badges)

    await message.answer(text, reply_markup=webapp_button("📊 Подробная статистика") or main_menu())


# ------------------------------------------------------------------- магазин

@router.message(Command("shop"))
@router.message(F.text == "🛍 Магазин")
async def cmd_shop(message: Message) -> None:
    user = await current_user(message)
    owned = {p["item_code"] for p in await db.list_purchases(user["id"])}
    await message.answer(
        "🛍 <b>Магазин наград</b>\nУ тебя <b>{}</b> 🪙\n\n"
        "Покупай темы оформления и честно заслуженные радости.".format(user["coins"]),
        reply_markup=shop_keyboard(rewards.SHOP_ITEMS, owned),
    )


# --------------------------------------------------------- добавление задачи

@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Напиши так: <code>/add завтра в 18:00 купить цветы</code>")
        return
    await create_from_text(message, text)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    await create_from_text(message, (message.text or "").strip())


async def create_from_text(message: Message, raw: str) -> None:
    if not raw:
        return
    user = await current_user(message)
    ts, title = parse_when(raw, user["tz_offset"])
    title = title.strip(" !") or raw.strip()

    repeat = "none"
    low = raw.lower()
    if "каждый день" in low or "ежедневно" in low:
        repeat = "daily"
        title = title.replace("каждый день", "").replace("ежедневно", "").strip()
    elif "каждую неделю" in low or "еженедельно" in low:
        repeat = "weekly"
        title = title.replace("каждую неделю", "").replace("еженедельно", "").strip()
    elif "по будням" in low:
        repeat = "weekdays"
        title = title.replace("по будням", "").strip()

    task = await db.create_task(
        user["id"],
        title=title[:200] or "Задача",
        emoji=guess_emoji(title),
        priority=guess_priority(raw),
        due_at=ts,
        remind_at=ts,
        repeat=repeat,
    )

    prio_emoji, prio_name = rewards.PRIORITY_LABEL[int(task["priority"])]
    lines = ["✨ <b>Задача добавлена</b>", "", "{} <b>{}</b>".format(task["emoji"], esc(task["title"]))]
    if ts:
        lines.append("⏰ Напомню {}".format(fmt_dt(ts, user["tz_offset"])))
    lines.append("{} Приоритет: {}".format(prio_emoji, prio_name))
    if repeat != "none":
        lines.append("🔁 Повтор: {}".format({"daily": "каждый день", "weekly": "каждую неделю",
                                             "weekdays": "по будням"}[repeat]))
    lines.append("")
    lines.append("💰 Награда за выполнение: ~{} XP".format(
        int((rewards.BASE_XP + rewards.PRIORITY_XP[int(task["priority"])]) * rewards.streak_multiplier(user["streak"]))
    ))

    await message.answer("\n".join(lines), reply_markup=created_keyboard(task["id"]))


# ------------------------------------------------------------------- колбэки

def render_reward(result: Dict[str, Any]) -> str:
    lines = [
        "🎉 <b>Готово!</b> {}".format(esc(result["title"])),
        "",
        "＋<b>{}</b> XP   ＋<b>{}</b> 🪙".format(result["xp"], result["coins"]),
    ]
    for bonus in result["bonuses"]:
        lines.append("   {}".format(bonus))
    if result["streak_grew"]:
        lines.append("🔥 Серия: <b>{}</b> дн.".format(result["streak"]))
    if result["level_up"]:
        info = rewards.level_info(result["totals"]["xp"])
        lines.append("")
        lines.append("🆙 <b>Новый уровень {} — {} {}</b>".format(info["level"], info["emoji"], info["title"]))
    for ach in result["achievements"]:
        lines.append("")
        lines.append("🏅 <b>Достижение: {} {}</b>\n   <i>{}</i>  ＋{} 🪙".format(
            ach["emoji"], ach["title"], ach["desc"], ach["coins"]))
    if result.get("next_task"):
        lines.append("")
        lines.append("🔁 Следующий повтор уже в списке.")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("done:"))
async def cb_done(callback: CallbackQuery) -> None:
    user = await current_user(callback)
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id, user["id"])
    if task is None:
        await callback.answer("Задача не найдена 🤷", show_alert=True)
        return
    if task["done"]:
        await callback.answer("Уже выполнена ✅")
        return

    result = await rewards.complete_task(user, task)
    await callback.answer("＋{} XP  ＋{} 🪙".format(result["xp"], result["coins"]))
    await callback.message.answer(render_reward(result))


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(callback: CallbackQuery) -> None:
    user = await current_user(callback)
    task_id = int(callback.data.split(":")[1])
    ok = await db.delete_task(task_id, user["id"])
    await callback.answer("🗑 Удалено" if ok else "Не найдено")
    if ok and callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


@router.callback_query(F.data == "refresh:list")
async def cb_refresh(callback: CallbackQuery) -> None:
    user = await current_user(callback)
    tasks = await db.list_tasks(user["id"], include_done=False)
    await callback.answer("Обновлено 🔄")
    if not callback.message:
        return
    if not tasks:
        await callback.message.edit_text("📭 Активных задач нет.")
        return
    body = "\n\n".join(render_task(t, user["tz_offset"]) for t in tasks[:20])
    try:
        await callback.message.edit_text(
            "📋 <b>Активные задачи — {}</b>\n\n{}".format(len(tasks), body),
            reply_markup=tasks_keyboard(tasks),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery) -> None:
    user = await current_user(callback)
    code = callback.data.split(":", 1)[1]
    result = await rewards.buy_item(user, code)
    if not result["ok"]:
        await callback.answer(result["error"], show_alert=True)
        return

    item = result["item"]
    if result.get("applied"):
        await callback.answer("{} Тема применена!".format(item["emoji"]))
    else:
        await callback.answer("{} Куплено!".format(item["emoji"]))
    await callback.message.answer(
        "🛍 <b>{} {}</b>\n<i>{}</i>\n\nОстаток: <b>{}</b> 🪙".format(
            item["emoji"], esc(item["title"]), esc(item["desc"]), result["coins"])
    )


@router.callback_query(F.data.startswith("snooze:"))
async def cb_snooze(callback: CallbackQuery) -> None:
    user = await current_user(callback)
    _, raw_id, raw_minutes = callback.data.split(":")
    task_id, minutes = int(raw_id), int(raw_minutes)
    task = await db.get_task(task_id, user["id"])
    if task is None:
        await callback.answer("Задача не найдена 🤷", show_alert=True)
        return

    new_ts = db.now_ts() + minutes * 60
    await db.update_task(task_id, user["id"], remind_at=new_ts, remind_sent=0)
    await callback.answer("⏱ Отложено")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.message.answer(
        "😴 Напомню снова {} — {} <b>{}</b>".format(
            fmt_dt(new_ts, user["tz_offset"]), task["emoji"], esc(task["title"]))
    )
