"""Клавиатуры бота."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    ReplyKeyboardMarkup, WebAppInfo,
)

from .config import webapp_url


def webapp_button(text: str = "🚀 Открыть приложение") -> Optional[InlineKeyboardMarkup]:
    url = webapp_url()
    if not url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    ]])


def main_menu() -> ReplyKeyboardMarkup:
    rows: List[List[KeyboardButton]] = []
    url = webapp_url()
    if url.startswith("https://"):
        rows.append([KeyboardButton(text="🚀 Открыть To-Do", web_app=WebAppInfo(url=url))])
    rows.append([KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="📅 На сегодня")])
    rows.append([KeyboardButton(text="🏆 Профиль"), KeyboardButton(text="🛍 Магазин")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Напиши задачу…")


def task_row(task: Dict[str, Any]) -> List[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="✅ {}".format(_short(task["title"])), callback_data="done:{}".format(task["id"])),
        InlineKeyboardButton(text="🗑", callback_data="del:{}".format(task["id"])),
    ]


def tasks_keyboard(tasks: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [task_row(t) for t in tasks[:20]]
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh:list")])
    wa = webapp_button("🚀 Открыть приложение")
    if wa:
        rows.extend(wa.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def created_keyboard(task_id: int) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="✅ Выполнено", callback_data="done:{}".format(task_id)),
        InlineKeyboardButton(text="🗑 Удалить", callback_data="del:{}".format(task_id)),
    ]]
    wa = webapp_button()
    if wa:
        rows.extend(wa.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_keyboard(items: List[Dict[str, Any]], owned: set) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        mark = "✔️" if item["code"] in owned else "{} 🪙".format(item["price"])
        rows.append([InlineKeyboardButton(
            text="{} {} — {}".format(item["emoji"], item["title"], mark),
            callback_data="buy:{}".format(item["code"]),
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _short(text: str, limit: int = 28) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
