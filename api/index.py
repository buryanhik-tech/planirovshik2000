"""Точка входа для Vercel: весь трафик проекта приходит сюда.

Vercel ищет в этом файле ASGI-приложение с именем `app`.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402,F401
