"""Настройки для веб-версии: чтение, проверка, сохранение и автозапуск."""

from __future__ import annotations

import logging
from pathlib import Path

from yakumo.core import autostart
from yakumo.core.config import Config

log = logging.getLogger(__name__)


class SettingsService:
    def __init__(self, config: Config, config_path: Path, tray_running: bool, tray_available: bool):
        self.config = config
        self.config_path = config_path
        self.tray_available = tray_available
        # С какими значениями программа запущена: от них зависит, нужен ли перезапуск.
        self.started = {"tray": tray_running, "language": config.language}

    def restart_needed(self) -> list[str]:
        needed = []
        if self.tray_available and self.config.tray != self.started["tray"]:
            needed.append("tray")
        if self.started["tray"] and self.config.language != self.started["language"]:
            needed.append("language")  # подписи меню в трее
        return needed

    def get(self, _request=None) -> dict:
        values = {key: getattr(self.config, key) for key in Config.EDITABLE}
        values["autostart"] = autostart.supported() and autostart.is_enabled()
        return {
            "values": values,
            "options": {key: list(allowed) for key, allowed in Config.EDITABLE.items()},
            "autostart_supported": autostart.supported(),
            "tray_available": self.tray_available,
            "restart_needed": self.restart_needed(),
        }

    def post(self, request) -> dict:
        changes = request.read_json()
        if not isinstance(changes, dict):
            raise ValueError("Ожидается объект с настройками")
        changes = dict(changes)
        want_autostart = changes.pop("autostart", None)
        if want_autostart is not None and type(want_autostart) is not bool:
            raise ValueError("Недопустимое значение: autostart")

        self.config.update(changes)  # проверка до любых изменений
        if want_autostart is not None:
            try:
                autostart.set_enabled(want_autostart)
            except OSError as exc:
                raise ValueError(f"Автозапуск: {exc}") from exc
        if changes:
            self.config.save(self.config_path)
        log.info("Настройки изменены: %s", {**changes, **({"autostart": want_autostart}
                                                          if want_autostart is not None else {})})
        return self.get()

    def routes(self) -> dict:
        return {"/api/settings": self.get, "POST /api/settings": self.post}
