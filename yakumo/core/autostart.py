"""Автозапуск Yakumo вместе с Windows.

Значение в реестре HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run:
права администратора не нужны, кириллица в путях работает (реестр хранит
Unicode). Запускается Yakumo.pyw через pythonw.exe, поэтому окна консоли
нет, а браузер при автозапуске не открывается.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from yakumo.core.storage import app_dir

NAME = "Yakumo"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def supported() -> bool:
    return os.name == "nt"


def command() -> list[str]:
    python = Path(sys.executable)
    if python.with_name("pythonw.exe").exists():
        python = python.with_name("pythonw.exe")
    return [str(python), "-X", "utf8", str(app_dir() / "Yakumo.pyw"), "--no-browser"]


def is_enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if not supported():
        raise OSError("Автозапуск работает только в Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command()))
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
