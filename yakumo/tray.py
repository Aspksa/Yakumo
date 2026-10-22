"""Значок в системном трее (нужны pystray и Pillow; без них ядро работает в консоли)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable

from yakumo import APP_NAME

log = logging.getLogger(__name__)


def available() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
    except Exception:  # noqa: BLE001  (на Linux без дисплея pystray падает не только ImportError)
        return False
    return True


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def make_image(size: int = 64):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2), fill=(88, 70, 160, 255))
    # Буква Y из трёх линий, чтобы не зависеть от шрифтов.
    w, c = max(size // 10, 2), size // 2
    draw.line((size * 0.3, size * 0.25, c, c), fill="white", width=w)
    draw.line((size * 0.7, size * 0.25, c, c), fill="white", width=w)
    draw.line((c, c, c, size * 0.78), fill="white", width=w)
    return img


LABELS = {
    "ru": {"open": "Открыть", "data": "Папка данных", "workspace": "Рабочая папка",
           "modules": "Модули", "exit": "Выход"},
    "en": {"open": "Open", "data": "Data folder", "workspace": "Workspace",
           "modules": "Modules", "exit": "Exit"},
}


def run(url: str, folders: dict[str, Path], on_exit: Callable[[], None], language: str = "ru") -> None:
    """Показать значок и ждать «Выход». Блокирует вызывающий поток.

    folders: ключ подписи из LABELS -> папка.
    """
    import pystray

    t = LABELS.get(language, LABELS["ru"])

    def quit_app(icon, _item):
        icon.stop()
        on_exit()

    items = [pystray.MenuItem(t["open"], lambda *_: webbrowser.open(url), default=True)]
    for key, path in folders.items():
        items.append(pystray.MenuItem(t.get(key, key), lambda *_, p=path: open_folder(p)))
    items += [pystray.Menu.SEPARATOR, pystray.MenuItem(t["exit"], quit_app)]

    icon = pystray.Icon("yakumo", make_image(), f"{APP_NAME}: {url}", pystray.Menu(*items))
    log.info("Значок в трее запущен")
    icon.run()
