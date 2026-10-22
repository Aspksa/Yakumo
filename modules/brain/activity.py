"""Контекст компьютера: какая программа сейчас на экране (только Windows и только по согласию).

Раз в минуту Yakumo смотрит на активное окно. Название окна живёт только в
памяти программы (чтобы ответить «что у меня открыто»), а на диск попадают
лишь минуты по программам за день и поздняя работа после полуночи.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

CURRENT_FOR = 180  # секунд: столько считаем снимок окна «текущим»
LATE_UNTIL = 5     # работа с 0:00 до 5:00 — «поздно»
NAMES = {"chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "yandex": "Яндекс Браузер",
         "browser": "Яндекс Браузер", "opera": "Opera", "code": "VS Code", "photoshop": "Photoshop",
         "winword": "Word", "excel": "Excel", "powerpnt": "PowerPoint", "telegram": "Telegram",
         "discord": "Discord", "explorer": "Проводник", "steam": "Steam", "obs64": "OBS", "blender": "Blender",
         "illustrator": "Illustrator", "figma": "Figma", "notepad": "Блокнот", "spotify": "Spotify",
         "acad": "AutoCAD", "pycharm64": "PyCharm", "devenv": "Visual Studio"}


def foreground_window() -> tuple[str, str] | None:
    """(программа, заголовок окна) активного окна Windows или None."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = ""
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        try:
            size = wintypes.DWORD(1024)
            path = ctypes.create_unicode_buffer(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                exe = path.value
        finally:
            kernel32.CloseHandle(handle)
    stem = Path(exe).stem.lower() if exe else ""
    if not stem and not buf.value:
        return None
    return NAMES.get(stem, Path(exe).stem if exe else "?"), buf.value


class Activity:
    def __init__(self, memory, sampler=foreground_window):
        self.memory = memory
        self.sampler = sampler
        self.current: dict | None = None  # {"app", "title", "at"} — не сохраняется на диск

    @staticmethod
    def available() -> bool:
        return sys.platform == "win32"

    def tick(self) -> None:
        if not self.memory.on("activity"):
            self.current = None
            return
        seen = self.sampler()
        if not seen:
            return
        app, title = seen
        now = time.localtime()
        self.current = {"app": app, "title": " ".join(title.split())[:120], "at": time.time()}
        if app == "Yakumo" or "Yakumo" in title:
            return  # разговор с самой Yakumo не считаем
        with self.memory.lock:
            day = self.memory.day()
            apps = day.setdefault("apps", {})
            apps[app] = apps.get(app, 0) + 1
            if now.tm_hour < LATE_UNTIL:
                day["late"] = day.get("late", 0) + 1
                day["late_until"] = time.strftime("%H:%M", now)
            self.memory.save()

    def now(self) -> dict | None:
        if self.current and time.time() - self.current["at"] < CURRENT_FOR:
            return self.current
        return None

    def today(self, top: int = 4) -> list[tuple[str, int]]:
        apps = self.memory.data["days"].get(time.strftime("%Y-%m-%d"), {}).get("apps", {})
        return sorted(apps.items(), key=lambda x: -x[1])[:top]
