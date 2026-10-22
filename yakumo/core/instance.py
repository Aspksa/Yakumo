"""Один экземпляр: повторный запуск не поднимает второй сервер.

Блокировка привязана к папке программы и лежит во временной папке системы,
поэтому не зависит от того, какой носитель выбран для данных. Пока процесс
работает, файл заблокирован средствами ОС; после падения блокировка
снимается сама, и «зависших» блокировок не остаётся.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from yakumo.core.storage import app_dir

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def _lock_base(base: Path | None = None) -> Path:
    key = hashlib.sha1(str((base or app_dir()).resolve()).lower().encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"yakumo-{key}"


class InstanceLock:
    """Блокировка экземпляра. Сведения о запущенном (url, pid) лежат рядом в .json."""

    def __init__(self, base: Path | None = None):
        stem = _lock_base(base)
        self.lock_path = stem.with_suffix(".lock")
        self.info_path = stem.with_suffix(".json")
        self._fh = None

    def acquire(self) -> bool:
        """True, если это первый экземпляр."""
        fh = open(self.lock_path, "a+")
        try:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def publish(self, url: str) -> None:
        self.info_path.write_text(json.dumps({"pid": os.getpid(), "url": url}), encoding="utf-8")

    def running_url(self) -> str | None:
        try:
            return json.loads(self.info_path.read_text(encoding="utf-8")).get("url")
        except (OSError, ValueError):
            return None

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self.info_path.unlink(missing_ok=True)
            if os.name == "nt":
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self._fh.close()
        self._fh = None

    def __enter__(self) -> "InstanceLock":
        return self

    def __exit__(self, *exc) -> None:
        self.release()
