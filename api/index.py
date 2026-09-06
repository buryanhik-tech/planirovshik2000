"""Точка входа для Vercel: весь трафик проекта приходит сюда.

Vercel ищет в этом файле ASGI-приложение с именем `app`.

Если импорт падает, платформа отдаёт безликую 500 без подробностей, поэтому
на этот случай подставляется заглушка, показывающая настоящую причину.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from main import app  # noqa: F401
except Exception:  # pragma: no cover - только для диагностики деплоя
    import traceback

    _REPORT = "Приложение не запустилось.\n\n{}\n\nsys.path:\n{}\n\nФайлы рядом:\n{}".format(
        traceback.format_exc(),
        "\n".join(sys.path),
        "\n".join(sorted(p.name for p in ROOT.iterdir())),
    )

    async def app(scope, receive, send):  # type: ignore[misc]
        if scope["type"] != "http":
            return
        body = _REPORT.encode()
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        })
        await send({"type": "http.response.body", "body": body})
