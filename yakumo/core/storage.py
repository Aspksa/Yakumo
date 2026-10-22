"""Автоматический выбор носителя (диска/тома) для данных Yakumo.

Порядок выбора:
1. Явно заданный путь (аргумент --data-dir или переменная YAKUMO_HOME).
2. Портативный режим: носитель, с которого запущено приложение, если рядом
   с программой лежит файл-маркер ``portable`` или папка ``YakumoData``,
   либо если сам носитель съёмный (флешка). Носитель должен быть доступен
   для записи и иметь достаточно свободного места.
3. Лучший локальный носитель: доступный для записи, не системный в приоритете,
   с наибольшим объёмом свободного места.
4. Папка пользователя (``%LOCALAPPDATA%`` на Windows, ``~/.local/share`` и т.п.).
"""

from __future__ import annotations

import os
import shutil
import string
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DATA_DIR_NAME = "YakumoData"
PORTABLE_MARKER = "portable"
MIN_FREE_BYTES = 512 * 1024 * 1024  # 512 МБ

IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class Medium:
    """Носитель: корень тома и его характеристики."""

    root: Path
    free: int
    total: int
    removable: bool = False
    system: bool = False

    @property
    def free_gb(self) -> float:
        return round(self.free / 1024**3, 2)


@dataclass(frozen=True)
class StorageChoice:
    """Результат выбора: где хранить данные и почему."""

    data_root: Path
    medium: Medium | None
    reason: str


def app_dir() -> Path:
    """Папка, откуда запущено приложение (корень репозитория или папка exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _windows_drive_type(root: str) -> int:
    import ctypes

    return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))


def _list_roots() -> list[tuple[Path, bool]]:
    """Список корней томов и признак «съёмный»."""
    roots: list[tuple[Path, bool]] = []
    if IS_WINDOWS:
        drive_removable, drive_fixed = 2, 3
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if not os.path.exists(root):
                continue
            kind = _windows_drive_type(root)
            if kind in (drive_removable, drive_fixed):
                roots.append((Path(root), kind == drive_removable))
        return roots

    roots.append((Path("/"), False))
    for base in ("/media", "/run/media", "/mnt", "/Volumes"):
        base_path = Path(base)
        if not base_path.is_dir():
            continue
        try:
            entries = list(base_path.iterdir())
        except OSError:
            continue
        for entry in entries:
            # /media/<user>/<volume> и /run/media/<user>/<volume>
            candidates = [entry]
            if entry.is_dir() and not os.path.ismount(entry):
                try:
                    candidates = [p for p in entry.iterdir() if p.is_dir()]
                except OSError:
                    candidates = []
            for cand in candidates:
                if os.path.ismount(cand):
                    roots.append((cand, base != "/mnt"))
    return roots


def _system_root() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("SystemDrive", "C:") + "\\")
    return Path("/")


def mount_root(path: Path) -> Path:
    """Корень тома, на котором лежит путь."""
    path = path.resolve()
    if IS_WINDOWS:
        return Path(path.anchor)
    while not os.path.ismount(path) and path != path.parent:
        path = path.parent
    return path


def is_writable(path: Path) -> bool:
    """Проверяет запись реальной попыткой создать временный файл."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".yakumo-", delete=True):
            pass
        return True
    except OSError:
        return False


def describe(root: Path, removable: bool = False) -> Medium | None:
    try:
        usage = shutil.disk_usage(root)
    except OSError:
        return None
    system = mount_root(root) == mount_root(_system_root())
    return Medium(root, usage.free, usage.total, removable, system)


def list_media() -> list[Medium]:
    """Все доступные носители, отсортированные от лучшего к худшему."""
    media = [m for root, rem in _list_roots() if (m := describe(root, rem))]
    # Сначала несистемные, затем по свободному месту.
    return sorted(media, key=lambda m: (m.system, -m.free))


def user_data_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        return Path(base) / "Yakumo"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Yakumo"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "yakumo"


def _portable_requested(base: Path) -> bool:
    return (base / PORTABLE_MARKER).exists() or (base / DATA_DIR_NAME).is_dir()


def choose_storage(
    explicit: str | os.PathLike | None = None,
    base: Path | None = None,
    min_free: int = MIN_FREE_BYTES,
    media: list[Medium] | None = None,
) -> StorageChoice:
    """Выбирает папку для данных. Параметры base/media нужны для тестов."""
    explicit = explicit or os.environ.get("YAKUMO_HOME")
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not is_writable(root):
            raise PermissionError(f"Нет доступа на запись: {root}")
        return StorageChoice(root, describe(mount_root(root)), "задан явно")

    base = (base or app_dir()).resolve()
    home_medium = describe(mount_root(base))
    media = list_media() if media is None else media
    home_removable = any(
        m.removable and mount_root(base) == mount_root(m.root) for m in media
    )

    if _portable_requested(base) or home_removable:
        target = base / DATA_DIR_NAME
        if home_medium and home_medium.free >= min_free and is_writable(target):
            why = "портативный режим" if _portable_requested(base) else "съёмный носитель"
            return StorageChoice(target, home_medium, why)

    for medium in media:
        if medium.free < min_free:
            continue
        if medium.system:
            # На системном диске храним в профиле пользователя, а не в корне.
            target = user_data_dir()
        else:
            target = medium.root / DATA_DIR_NAME
        if is_writable(target):
            return StorageChoice(target, medium, f"носитель с наибольшим свободным местом ({medium.free_gb} ГБ)")

    fallback = user_data_dir()
    if not is_writable(fallback):
        fallback = Path(tempfile.gettempdir()) / "Yakumo"
        fallback.mkdir(parents=True, exist_ok=True)
    return StorageChoice(fallback, describe(mount_root(fallback)), "резервный вариант")
