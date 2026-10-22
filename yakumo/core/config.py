"""Настройки Yakumo в JSON-файле на выбранном носителе."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
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

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
