"""Восстановление прерванной установки до импорта обновляемого ядра."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _same_app(a, b) -> bool:
    tail = lambda p: os.path.normcase(os.path.splitdrive(os.path.abspath(str(p)))[1]).rstrip("\\/")
    return tail(a) == tail(b)


def recover_pending(app: Path | None = None) -> None:
    root = (app or Path(__file__).resolve().parents[1]).resolve()
    marker = root / ".yakumo-update.json"
    if not marker.exists():
        return
    try:
        pointer = json.loads(marker.read_text(encoding="utf-8"))
        job_path, worker = Path(pointer["job"]), Path(pointer["worker"])
        if not job_path.exists() and root.drive:
            # Переносной диск мог получить другую букву после прерванной установки.
            job_path, worker = (Path(root.drive + os.path.splitdrive(str(p))[1]) for p in (job_path, worker))
        job = json.loads(job_path.read_text(encoding="utf-8"))
        if (not _same_app(job["app"], root) or worker.name != "worker.py"
                or worker.parent != job_path.parent or not worker.is_file()):
            raise ValueError("неверный путь установщика")
        result = subprocess.run([sys.executable, "-X", "utf8", str(worker), str(job_path), "--recover-if-needed",
                                 "--app", str(root)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise ValueError(result.stderr.strip() or "установщик не смог восстановить файлы")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Не удалось завершить восстановление Yakumo: {exc}") from exc


def main(argv=None):
    recover_pending()
    from yakumo.app import main as run
    return run(argv)
