"""Пример модуля Yakumo. Скопируйте файл и переименуйте, чтобы сделать свой.

После запуска откройте /api/hello.
"""

import time

NAME = "Привет"
VERSION = "1.0"


def setup(ctx):
    started = time.time()

    def hello(request):
        return {"hello": "мир", "workspace": str(ctx.paths.workspace)}

    ctx.route("/api/hello", hello)
    ctx.status(lambda: {"uptime_sec": round(time.time() - started)})
    ctx.log.info("Модуль-пример готов")
