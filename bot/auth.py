"""Проверка подписи Telegram WebApp initData."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from .config import BOT_TOKEN, DEV_MODE

MAX_AGE = 24 * 3600  # сутки


def verify_init_data(init_data: str, max_age: int = MAX_AGE) -> Optional[Dict[str, Any]]:
    """Возвращает разобранные данные, если подпись верна, иначе None."""
    if not init_data or not BOT_TOKEN:
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join("{}={}".format(k, pairs[k]) for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        return None

    auth_date = int(pairs.get("auth_date", "0") or 0)
    if max_age and auth_date and time.time() - auth_date > max_age:
        return None

    user_raw = pairs.get("user")
    if user_raw:
        try:
            pairs["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            return None
    return pairs


DEV_USER = {"id": 1, "first_name": "Dev", "last_name": "Режим", "username": "dev"}


def resolve_user_payload(init_data: str) -> Optional[Dict[str, Any]]:
    """Данные пользователя из initData; в DEV_MODE — заглушка."""
    data = verify_init_data(init_data)
    if data and isinstance(data.get("user"), dict):
        return data["user"]
    if DEV_MODE:
        return DEV_USER
    return None
