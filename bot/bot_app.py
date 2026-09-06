"""Создание бота, планировщик напоминаний."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.token import TokenValidationError

from . import db
from .config import BOT_TOKEN, REMINDER_TICK
from .handlers import esc, router
from .timeparse import fmt_dt

log = logging.getLogger("todo.bot")

_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None


_token_broken = False


def get_bot() -> Optional[Bot]:
    global _bot, _token_broken
    if _bot is None and BOT_TOKEN and not _token_broken:
        try:
            _bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        except TokenValidationError:
            _token_broken = True
            log.error("BOT_TOKEN выглядит некорректно — проверь значение в .env")
    return _bot


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        _dp = Dispatcher()
        _dp.include_router(router)
    return _dp


COMMANDS = [
    BotCommand(command="start", description="🚀 Запустить"),
    BotCommand(command="list", description="📋 Активные задачи"),
    BotCommand(command="today", description="📅 Задачи на сегодня"),
    BotCommand(command="add", description="➕ Добавить задачу"),
    BotCommand(command="stats", description="🏆 Профиль и награды"),
    BotCommand(command="shop", description="🛍 Магазин наград"),
    BotCommand(command="clear", description="🧹 Убрать выполненные"),
    BotCommand(command="help", description="📖 Помощь"),
]


def reminder_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data="done:{}".format(task_id))],
        [
            InlineKeyboardButton(text="⏱ +10 мин", callback_data="snooze:{}:10".format(task_id)),
            InlineKeyboardButton(text="🕐 +1 час", callback_data="snooze:{}:60".format(task_id)),
            InlineKeyboardButton(text="🌙 Завтра", callback_data="snooze:{}:1440".format(task_id)),
        ],
    ])


async def reminder_loop() -> None:
    """Раз в REMINDER_TICK секунд шлёт напоминания по наступившим задачам."""
    bot = get_bot()
    if bot is None:
        log.warning("BOT_TOKEN не задан — напоминания отключены")
        return

    log.info("Планировщик напоминаний запущен")
    while True:
        try:
            pending = await db.due_reminders(db.now_ts())
            for task in pending:
                user = await db.get_user_by_id(task["user_id"])
                tz = user["tz_offset"] if user else 3
                text = (
                    "⏰ <b>Напоминание!</b>\n\n"
                    "{} <b>{}</b>\n"
                    "<i>{}</i>"
                ).format(task["emoji"], esc(task["title"]), fmt_dt(task["remind_at"], tz))
                if task["note"]:
                    text += "\n\n📝 {}".format(esc(task["note"]))
                try:
                    await bot.send_message(task["tg_id"], text, reply_markup=reminder_keyboard(task["id"]))
                except Exception as exc:  # пользователь мог заблокировать бота
                    log.warning("Не удалось отправить напоминание %s: %s", task["id"], exc)
                await db.mark_reminded(task["id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка в планировщике напоминаний")
        await asyncio.sleep(REMINDER_TICK)


async def start_polling() -> None:
    bot = get_bot()
    if bot is None:
        log.warning("Бот не запущен (нет корректного BOT_TOKEN) — работает только мини-приложение")
        return
    try:
        dp = get_dispatcher()
        await bot.set_my_commands(COMMANDS)
        me = await bot.get_me()
        log.info("Бот @%s запущен", me.username)
        await dp.start_polling(bot, handle_signals=False)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Бот остановлен из-за ошибки — мини-приложение продолжает работать")
