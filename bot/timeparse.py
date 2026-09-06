"""Простой разбор естественного времени: «завтра в 18:00», «через 2 часа», «в пн 9:30»."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

WEEKDAYS = {
    "пн": 0, "понедельник": 0, "вт": 1, "вторник": 1, "ср": 2, "среда": 2, "среду": 2,
    "чт": 3, "четверг": 3, "пт": 4, "пятница": 4, "пятницу": 4,
    "сб": 5, "суббота": 5, "субботу": 5, "вс": 6, "воскресенье": 6,
}

UNIT_SECONDS = {
    "мин": 60, "минут": 60, "минуту": 60, "минуты": 60, "м": 60,
    "час": 3600, "часа": 3600, "часов": 3600, "ч": 3600,
    "день": 86400, "дня": 86400, "дней": 86400, "д": 86400,
    "неделю": 604800, "недели": 604800, "недель": 604800,
}

RE_IN = re.compile(r"\bчерез\s+(\d+)\s*([а-яё]+)", re.IGNORECASE)
RE_TIME = re.compile(r"\b(?:в\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)\b", re.IGNORECASE)
RE_HOUR = re.compile(r"\bв\s+([01]?\d|2[0-3])\s*(?:ч|часов|часа)?\b", re.IGNORECASE)
RE_DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b")


def _now_local(tz_offset: int) -> datetime:
    """Текущее локальное время пользователя (naive)."""
    return (datetime.now(timezone.utc) + timedelta(hours=tz_offset)).replace(tzinfo=None)


def _to_utc_ts(local_dt: datetime, tz_offset: int) -> int:
    return int((local_dt - timedelta(hours=tz_offset)).replace(tzinfo=timezone.utc).timestamp())


def parse_when(text: str, tz_offset: int = 3) -> Tuple[Optional[int], str]:
    """Возвращает (utc-таймстемп или None, текст без временной части)."""
    original = text
    rest = text
    now = _now_local(tz_offset)
    target: Optional[datetime] = None

    # «через N единиц»
    m = RE_IN.search(rest)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        seconds = None
        for key, value in UNIT_SECONDS.items():
            if unit.startswith(key[:3]) or unit == key:
                seconds = value
                break
        if seconds:
            target = now + timedelta(seconds=amount * seconds)
            rest = (rest[: m.start()] + rest[m.end():]).strip()
            return _to_utc_ts(target, tz_offset), _clean(rest) or _clean(original)

    day = now.date()
    day_found = False
    lowered = rest.lower()

    for word, delta in (("послезавтра", 2), ("завтра", 1), ("сегодня", 0)):
        idx = lowered.find(word)
        if idx != -1:
            day = (now + timedelta(days=delta)).date()
            rest = rest[:idx] + rest[idx + len(word):]
            lowered = rest.lower()
            day_found = True
            break

    if not day_found:
        for word, wd in WEEKDAYS.items():
            m = re.search(r"\b(?:в\s+)?{}\b".format(word), lowered)
            if m:
                ahead = (wd - now.weekday()) % 7
                ahead = ahead or 7
                day = (now + timedelta(days=ahead)).date()
                rest = rest[: m.start()] + rest[m.end():]
                lowered = rest.lower()
                day_found = True
                break

    if not day_found:
        m = RE_DATE.search(rest)
        if m:
            d, mo = int(m.group(1)), int(m.group(2))
            y = int(m.group(3) or now.year)
            if y < 100:
                y += 2000
            try:
                day = datetime(y, mo, d).date()
                rest = rest[: m.start()] + rest[m.end():]
                day_found = True
            except ValueError:
                pass

    hour = minute = None
    m = RE_TIME.search(rest)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        rest = rest[: m.start()] + rest[m.end():]
    else:
        m = RE_HOUR.search(rest)
        if m:
            hour, minute = int(m.group(1)), 0
            rest = rest[: m.start()] + rest[m.end():]

    if hour is None and not day_found:
        return None, _clean(original)

    if hour is None:
        hour, minute = 9, 0

    target = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
    if target <= now and not day_found:
        target += timedelta(days=1)

    return _to_utc_ts(target, tz_offset), _clean(rest) or _clean(original)


def _clean(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.-—;")
    return text.strip()


def fmt_dt(ts: Optional[int], tz_offset: int = 3) -> str:
    if not ts:
        return "без срока"
    local = (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=tz_offset)).replace(tzinfo=None)
    now = _now_local(tz_offset)
    if local.date() == now.date():
        return "сегодня в {:%H:%M}".format(local)
    if local.date() == (now + timedelta(days=1)).date():
        return "завтра в {:%H:%M}".format(local)
    if local.date() == (now - timedelta(days=1)).date():
        return "вчера в {:%H:%M}".format(local)
    return "{:%d.%m в %H:%M}".format(local)
