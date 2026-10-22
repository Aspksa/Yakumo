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
        "avatar_size": tuple(range(120, 961, 8)),
        "avatar_motion": ("none", "float", "glide", "alive"),
        "avatar_glow": ("off", "soft", "bright", "pulse"),
        "avatar_speed": ("slow", "normal", "fast"),
    }

    def update(self, changes: dict) -> None:
        """Применить изменения из веб-версии; неизвестное или недопустимое отклоняется целиком."""
        for key, value in changes.items():
            allowed = self.EDITABLE.get(key)
            # bool — подкласс int, поэтому сверяем и тип.
            if allowed is None or not any(value == a and type(value) is type(a) for a in allowed):
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
        valid = {k: v for k, v in raw.items() if k in known
                 and (k not in cls.EDITABLE or any(v == a and type(v) is type(a) for a in cls.EDITABLE[k]))}
        return cls(**valid)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
