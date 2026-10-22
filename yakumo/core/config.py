"""Настройки Yakumo в JSON-файле на выбранном носителе."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import ClassVar
from pathlib import Path


@dataclass
class Config:
    host: str | None = None          # None: выбрать автоматически
    port: int | None = None          # None: порт по умолчанию или следующий свободный
    lan: bool = False                # открыть доступ из локальной сети
    open_browser: bool = True        # открыть браузер после запуска
    workspace: str | None = None     # папка, которая открывается по умолчанию
    tray: bool = True                # значок в трее, если установлены pystray и Pillow
    disabled_modules: list[str] = field(default_factory=list)  # модули, которые не загружать
    language: str = "ru"             # язык интерфейса: ru или en
    font_scale: int = 100            # размер шрифта веб-версии, %
    compact: bool = False            # компактный режим веб-версии
    avatar_show: bool = True         # аватар на страницах веб-версии
    avatar_size: int = 232           # размер аватара, точек
    avatar_motion: str = "float"     # движение аватара
    avatar_glow: str = "soft"        # сияние за аватаром
    avatar_speed: str = "normal"     # скорость анимации
    avatar_effects: list[str] = field(default_factory=lambda: ["sparkles"])  # эффекты вокруг аватара
    avatar_fx_power: str = "normal"  # сила эффектов
    cloud_model: str | None = None   # модель Cloud.ru для чата; ключ хранится в secrets.json
    cloud_url: str = "https://foundation-models.api.cloud.ru/v1"  # адрес API Cloud.ru

    # Что можно менять из веб-версии, и допустимые значения.
    EDITABLE: ClassVar[dict[str, tuple]] = {
        "open_browser": (True, False),
        "tray": (True, False),
        "language": ("ru", "en"),
        "font_scale": (90, 100, 115, 130),
        "compact": (True, False),
        "avatar_show": (True, False),
        "avatar_size": tuple(range(120, 2001, 8)),
        "avatar_motion": ("none", "float", "glide", "alive"),
        "avatar_glow": ("off", "soft", "bright", "pulse"),
        "avatar_speed": ("slow", "normal", "fast"),
        "avatar_fx_power": ("low", "normal", "high"),
    }
    # Настройки-списки: можно выбрать несколько значений сразу (или ни одного).
    MULTI: ClassVar[dict[str, tuple]] = {
        "avatar_effects": ("sparkles", "foxfire", "petals", "dust", "fireflies", "leaves", "snow",
                           "rays", "circle", "shine", "aura", "butterflies", "lanterns", "mist",
                           "meteors", "hearts", "moon", "runes"),
    }

    @classmethod
    def valid(cls, key: str, value) -> bool:
        if key in cls.MULTI:
            return (type(value) is list and len(set(value)) == len(value)
                    and all(isinstance(v, str) and v in cls.MULTI[key] for v in value))
        allowed = cls.EDITABLE.get(key)
        # bool — подкласс int, поэтому сверяем и тип.
        return allowed is not None and any(value == a and type(value) is type(a) for a in allowed)

    def update(self, changes: dict) -> None:
        """Применить изменения из веб-версии; неизвестное или недопустимое отклоняется целиком."""
        for key, value in changes.items():
            if not self.valid(key, value):
                raise ValueError(f"Недопустимое значение: {key}={value!r}")
        for key, value in changes.items():
            setattr(self, key, value)

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            return cls()
        try:
            # utf-8-sig: Блокнот Windows сохраняет UTF-8 с BOM.
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        # Значение, которого больше нет среди допустимых (например, убранный вариант), сбрасываем.
        editable = cls.EDITABLE.keys() | cls.MULTI.keys()
        return cls(**{k: v for k, v in raw.items() if k in known and (k not in editable or cls.valid(k, v))})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
