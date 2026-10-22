"""Закрытые глаза для моргания аватара в режиме «Живая».

Запуск: python tools/avatar_blink.py
Берёт yakumo/web/static/avatar-1254.webp (исходник без потерь) и пишет рядом
avatar-blink.webp: маленький кусок лица с сомкнутыми ресницами, который на
мгновение кладётся поверх целой картинки. Нужен Pillow.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

STATIC = Path(__file__).resolve().parents[1] / "yakumo" / "web" / "static"

# Глаза: где открытый глаз, откуда взять кожу (сдвиг вниз) и линия сомкнутых ресниц.
EYES = [
    dict(poly=[(585, 292), (597, 287), (612, 288), (627, 294), (637, 305), (635, 317), (620, 316), (604, 312), (591, 304)],
         shift=26, a=(587, 299), b=(637, 309), sag=6),
    dict(poly=[(664, 333), (677, 327), (694, 328), (709, 333), (719, 343), (713, 350), (698, 351), (683, 347), (670, 341)],
         shift=24, a=(666, 336), b=(718, 344), sag=5),
]
BLINK_BOX = (575, 275, 730, 365)  # этот же прямоугольник задан в app.css (.av-blink)


def polygon_mask(size, points, blur=0.0) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return m


def blink(src: Image.Image) -> Image.Image:
    out = src.copy()
    mask = Image.new("L", src.size, 0)
    for e in EYES:
        m = polygon_mask(src.size, e["poly"], blur=2.2)
        skin = src.transform(src.size, Image.AFFINE, (1, 0, 0, 0, 1, e["shift"]), resample=Image.BICUBIC)
        out = Image.composite(skin.filter(ImageFilter.GaussianBlur(1.2)), out, m)
        mask = ImageChops.lighter(mask, m)
        (ax, ay), (bx, by) = e["a"], e["b"]
        lid = [(ax + (bx - ax) * t, ay + (by - ay) * t + e["sag"] * 4 * t * (1 - t)) for t in (i / 24 for i in range(25))]
        shadow = Image.new("RGBA", src.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).line([(x, y - 3) for x, y in lid], fill=(170, 95, 70, 70), width=8, joint="curve")
        out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(2)))
        # Ресницы рисуем в 4 раза крупнее и уменьшаем, чтобы линия была гладкой.
        k, (x0, y0) = 4, (560, 260)
        lash = Image.new("RGBA", (200 * k, 130 * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(lash)
        pts = lambda ps: [((x - x0) * k, (y - y0) * k) for x, y in ps]  # noqa: E731
        col = (62, 32, 22, 255)
        d.line(pts(lid), fill=col, width=int(1.8 * k), joint="curve")
        d.line(pts(lid[9:]), fill=col, width=int(2.8 * k), joint="curve")  # к внешнему углу толще
        ex, ey = lid[-1]
        d.line(pts([(ex - 5, ey - .5), (ex + 1.5, ey + 4.5)]), fill=col, width=int(1.6 * k))
        d.line(pts([(ex - 11, ey - 1), (ex - 7, ey + 4)]), fill=(62, 32, 22, 210), width=int(1.4 * k))
        layer = Image.new("RGBA", src.size, (0, 0, 0, 0))
        layer.paste(lash.resize((200, 130), Image.LANCZOS), (x0, y0))
        out.alpha_composite(layer)
        ImageDraw.Draw(mask).line(lid, fill=255, width=6)
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    patch = out.crop(BLINK_BOX)
    patch.putalpha(ImageChops.multiply(mask.crop(BLINK_BOX), src.crop(BLINK_BOX).getchannel("A")))
    return patch


def main() -> None:
    src = Image.open(STATIC / "avatar-1254.webp").convert("RGBA")
    blink(src).save(STATIC / "avatar-blink.webp", lossless=True, method=6)


if __name__ == "__main__":
    main()
