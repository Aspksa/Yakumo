"""Картинки образов аватара для веб-версии.

Запуск: python tools/avatar_images.py ПАПКА
В папке лежат исходники <образ>.png с прозрачным фоном (сейчас 2508×2508: увеличены
нейросетью Real-ESRGAN anime ×4 и уменьшены вдвое, края почищены). Скрипт пишет в
yakumo/web/static/avatars/ уменьшенные копии <образ>-<ширина>.webp для srcset и
миниатюру <образ>-thumb.webp для настроек. Нужен Pillow.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "yakumo" / "web" / "static" / "avatars"
WIDTHS = (400, 600, 900, 1254, 1800, 2508)  # те же, что AVATAR_WIDTHS в app.js
THUMB = 192


def save(im: Image.Image, path: Path, width: int) -> None:
    small = im if im.width == width else im.resize((width, width), Image.LANCZOS)
    # Сжатие почти без видимых потерь, прозрачность без потерь.
    small.save(path, quality=93, alpha_quality=100, method=4)


def main(src: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for png in sorted(src.glob("*.png")):
        im = Image.open(png).convert("RGBA")
        for w in WIDTHS:
            if w <= im.width:
                save(im, OUT / f"{png.stem}-{w}.webp", w)
        im.resize((THUMB, THUMB), Image.LANCZOS).save(OUT / f"{png.stem}-thumb.webp", quality=90, alpha_quality=100, method=4)
        print(png.stem)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
