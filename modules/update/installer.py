"""Самостоятельный установщик. Его копия запускается вне обновляемой папки."""

from __future__ import annotations

import hashlib
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path, PurePosixPath

MARKER = ".yakumo-update.json"
PROTECTED = {".git", ".venv", "python", "yakumodata", "yakumodisk", "config", "logs", "cache",
             "temp", "workspace", "updates", "disk", "dist", "node_modules", MARKER}
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class UpdateError(ValueError):
    def __init__(self, code, message, action, retry_at=None):
        super().__init__(message)
        self.code, self.action, self.retry_at = code, action, retry_at


def error_info(exc: Exception) -> dict:
    """Сообщения для интерфейса без traceback, заголовков и сетевых секретов."""
    if isinstance(exc, UpdateError):
        return {"code": exc.code, "message": str(exc), "action": exc.action, "retry_at": exc.retry_at}
    if (isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (5, 32, 33)
            or isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS, errno.EBUSY, errno.ETXTBSY)):
        return {"code": "file_access", "message": "Не удалось получить доступ к файлу программы.",
                "action": "Закройте редакторы и другие копии Yakumo. Проверьте право записи в папку программы и повторите операцию."}
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return {"code": "disk_full", "message": "На диске закончилось свободное место.",
                "action": "Освободите место на дисках программы и данных, затем повторите подготовку обновления."}
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return {"code": "network", "message": "Соединение прервано или истекло время ожидания.",
                "action": "Проверьте интернет и повторите операцию. Незавершённый архив будет загружен заново."}
    if isinstance(exc, SyntaxError):
        return {"code": "syntax", "message": "В новой версии обнаружена ошибка синтаксиса Python.",
                "action": "Выберите другой выпуск или дождитесь исправления в репозитории. Подготовленные файлы не устанавливайте."}
    if isinstance(exc, zipfile.BadZipFile):
        return {"code": "integrity", "message": "Архив обновления повреждён или загружен не полностью.",
                "action": "Повторите загрузку. Если ошибка повторяется, проверьте подключение и выберите другой выпуск."}
    if isinstance(exc, FileNotFoundError):
        return {"code": "missing_file", "message": "Не найден файл, необходимый для операции.",
                "action": "Повторите проверку и подготовку. Если нужна резервная копия, проверьте, что её папка не была удалена."}
    if isinstance(exc, ValueError):
        message = str(exc)[:600]
        if any(word in message.lower() for word in ("контрольн", "поврежд", "сумма", "архив", "каталог")):
            action = "Повторите проверку и загрузку. Если ошибка повторяется, выберите другой выпуск и сохраните код ошибки."
            code = "integrity"
        elif any(word in message.lower() for word in ("запуск", "модули", "закрылась")):
            action = "Проверьте результат восстановления и журнал запуска. При необходимости перезапустите Yakumo вручную."
            code = "startup"
        elif "места" in message.lower():
            action = "Освободите место на дисках программы и данных и повторите операцию."
            code = "disk_full"
        else:
            action = "Выполните указанное действие и повторите операцию. Если ошибка остаётся, заново проверьте обновления."
            code = "update_request"
        return {"code": code, "message": message, "action": action}
    return {"code": "unexpected", "message": "Не удалось завершить операцию обновления.",
            "action": "Перезапустите Yakumo и повторите операцию. При повторной ошибке сохраните код ошибки и журнал установщика."}


def safe_rel(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise ValueError("Недопустимый путь обновления")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or str(path) != value or any(p in (".", "..") for p in path.parts):
        raise ValueError("Недопустимый путь обновления")
    for p in path.parts:
        if (len(p) > 255 or p.endswith((".", " ")) or any(c in p for c in '<>:"|?*')
                or p.split(".")[0].upper() in RESERVED):
            raise ValueError("Имя файла не поддерживается в Windows")
    if path.parts[0].lower() in PROTECTED or value == "portable":
        raise ValueError("Обновление не может менять пользовательские данные или Python")
    return value


def safe_target(root: Path, rel: str, protected: list[str] | None = None) -> Path:
    rel = safe_rel(rel)
    if any(rel.casefold() == p.casefold() or rel.casefold().startswith(p.casefold() + "/")
           for p in (protected or [])):
        raise ValueError("Путь занят пользовательскими данными")
    root = root.resolve()
    target = root / rel
    for p in (target, *target.parents):
        if p == root:
            break
        # Junction в Windows также проверяется через realpath/commonpath ниже.
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise ValueError("Обновление через ссылку или точку соединения запрещено")
        try:
            if getattr(p.lstat(), "st_reparse_tag", 0) in (0xA0000003, 0xA000000C):
                raise ValueError("Обновление через точку соединения запрещено")
        except FileNotFoundError:
            pass
    base = os.path.normcase(str(root))
    if os.path.commonpath([os.path.normcase(os.path.realpath(target)), base]) != base:
        raise ValueError("Файл выходит за пределы программы")
    real = os.path.normcase(os.path.realpath(target))
    for prefix in protected or []:
        protected_real = os.path.normcase(os.path.realpath(root / prefix))
        if real == protected_real or real.startswith(protected_real + os.sep):
            raise ValueError("Путь занят пользовательскими данными")
    return target


def same_app(a, b) -> bool:
    """Одна и та же папка, даже если переносной диск получил другую букву."""
    if not a or not b:
        return False
    tail = lambda p: os.path.normcase(os.path.splitdrive(os.path.abspath(str(p)))[1]).rstrip("\\/")
    return tail(a) == tail(b)


def relocate(job: dict, job_path: Path, app: Path | None = None) -> dict:
    """Пути задания после смены буквы диска: данные рядом с заданием, программа — где запущена."""
    job_path = job_path.resolve()
    if job_path.parent.parent.name == "jobs":
        job["root"] = str(job_path.parents[2])
    if app is not None and same_app(job.get("app"), app):
        job["app"] = str(Path(app).resolve())
    return job


def read_json(path: Path, default=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else ({} if default is None else default)
    except (OSError, ValueError):
        return {} if default is None else default


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".yakumo-", suffix=".tmp", delete=False) as f:
            name = Path(f.name)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_copy(src: Path, dst: Path, mode: int | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=dst.parent, prefix=".yakumo-", suffix=".tmp", delete=False) as f:
            name = Path(f.name)
            with src.open("rb") as source:
                shutil.copyfileobj(source, f, 1024 * 1024)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(name, mode)
        os.replace(name, dst)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


class FileLock:
    def __init__(self, path: Path):
        self.path, self.file = path, None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = self.path.open("a+b")
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            raise ValueError("Другая установка обновления ещё не завершена") from None
        self.file = f
        return self

    def __exit__(self, *_args):
        if self.file:
            self.file.close()  # ОС освобождает блокировку


def pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # отказ в доступе не означает завершение
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists() and stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def wait_parent(pid: int, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while pid_alive(pid):
        if time.monotonic() >= deadline:
            raise ValueError("Yakumo не закрылась. Файлы не изменены; попробуйте ещё раз")
        time.sleep(.2)


def validate_plan(job: dict, journal: Path | None = None) -> tuple[Path, Path]:
    app, root = Path(job["app"]).resolve(), Path(job["root"]).resolve()
    if not re.fullmatch(r"[a-f0-9]{32}", job.get("id", "")):
        raise ValueError("Повреждён план обновления")
    stage = root / "stages" / job["stage"]
    if not re.fullmatch(r"[a-f0-9]{32}", job.get("stage", "")):
        raise ValueError("Повреждён путь подготовки")
    seen = set()
    if not isinstance(job.get("files"), dict) or not isinstance(job.get("remove"), list):
        raise ValueError("Повреждён список файлов обновления")
    for rel, info in job["files"].items():
        safe_target(app, rel, job.get("protected"))
        source = safe_target(stage, rel)
        if rel.casefold() in seen or not source.is_file() or digest(source) != info["sha256"]:
            raise ValueError(f"Подготовленный файл повреждён: {rel}")
        seen.add(rel.casefold())
        report_file(job, journal, len(seen), len(job["files"]) + len(job["remove"]), rel)
    for rel in job["remove"]:
        safe_target(app, rel, job.get("protected"))
        if rel.casefold() in seen:
            raise ValueError("Файл одновременно устанавливается и удаляется")
        seen.add(rel.casefold())
        report_file(job, journal, len(seen), len(job["files"]) + len(job["remove"]), rel)
    return app, root


def report_file(job: dict, journal: Path | None, done: int, total: int, rel: str) -> None:
    job.update(done=done, total=total, unit="files", current_file=rel)
    if journal:
        atomic_json(journal, job)


def make_backup(job: dict, app: Path, root: Path, journal: Path | None = None) -> dict:
    folder = root / "backups" / job["id"]
    folder.mkdir(parents=True, exist_ok=False)
    entries = {}
    paths = sorted(set(job["files"]) | set(job["remove"]))
    for number, rel in enumerate(paths, 1):
        target = safe_target(app, rel, job.get("protected"))
        if target.exists() and not target.is_file():
            raise ValueError(f"На месте файла находится папка: {rel}")
        record = {"exists": target.is_file()}
        if record["exists"]:
            mode = target.stat().st_mode & 0o777
            atomic_copy(target, safe_target(folder / "files", rel), mode)
            record.update(sha256=digest(safe_target(folder / "files", rel)), mode=mode)
        entries[rel] = record
        report_file(job, journal, number, len(paths), rel)
    backup = {"id": job["id"], "app": str(app), "created": time.time(), "files": entries,
              "installed": read_json(root / "installed.json"), "protected": job.get("protected", [])}
    atomic_json(folder / "backup.json", backup)
    return backup


def restore_backup(backup: dict, root: Path, app: Path, selected: set[str] | None = None) -> None:
    if not same_app(backup.get("app"), app) or not re.fullmatch(r"[a-f0-9]{32}", backup.get("id", "")):
        raise ValueError("Резервная копия относится к другой папке программы")
    folder = root / "backups" / backup["id"] / "files"
    # Проверяем все копии до первого изменения программы.
    for rel, info in backup["files"].items():
        safe_target(app, rel, backup.get("protected"))
        if info["exists"] and digest(safe_target(folder, rel)) != info["sha256"]:
            raise ValueError(f"Резервная копия повреждена: {rel}")
    for rel, info in reversed(list(backup["files"].items())):
        if selected is not None and rel not in selected:
            continue
        target = safe_target(app, rel, backup.get("protected"))
        if info["exists"]:
            if target.is_file() and digest(target) == info["sha256"]:
                continue
            atomic_copy(safe_target(folder, rel), target, info["mode"])
        else:
            target.unlink(missing_ok=True)
    atomic_json(root / "installed.json", backup["installed"])


def apply_files(job: dict, app: Path, root: Path, journal: Path | None = None) -> None:
    stage = root / "stages" / job["stage"]
    job["applied"] = []
    for rel in [*job["files"], *job["remove"]]:
        job["pending"] = rel
        if journal:
            atomic_json(journal, job)
        try:
            if rel in job["files"]:
                info = job["files"][rel]
                atomic_copy(safe_target(stage, rel), safe_target(app, rel, job.get("protected")), info.get("mode", 0o644))
            else:
                safe_target(app, rel, job.get("protected")).unlink(missing_ok=True)
        except Exception:
            job["pending"] = None  # атомарная операция не изменила этот файл
            if journal:
                atomic_json(journal, job)
            raise
        job["applied"].append(rel)
        job["pending"] = None
        report_file(job, journal, len(job["applied"]), len(job["files"]) + len(job["remove"]), rel)
    installed = dict(job["installed"])
    if installed:
        installed["installed_at"] = time.time()
    atomic_json(root / "installed.json", installed)


def launch(job: dict):
    flags = (subprocess.CREATE_NEW_CONSOLE if job.get("show_console") else subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    # Ошибки импорта происходят ещё до настройки основного журнала Yakumo.
    error_log = Path(job["root"]) / "jobs" / job["id"] / "restart-errors.log"
    with error_log.open("ab") as output:
        return subprocess.Popen(job["command"], cwd=job["app"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=output,
                                creationflags=flags, start_new_session=os.name != "nt")


def healthy(process, job: dict, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("Новая версия завершилась до проверки запуска")
        info = read_json(Path(job["instance_info"]))
        if info.get("pid") == process.pid and isinstance(info.get("url"), str):
            try:
                with opener.open(info["url"].rstrip("/") + "/api/status", timeout=2) as response:
                    status = json.load(response)
            except (OSError, ValueError):
                pass
            else:
                if status.get("app") == "Yakumo":
                    errors = [m["name"] for m in status.get("modules", [])
                              if m.get("error") and m["name"] not in job.get("allowed_errors", [])]
                    if errors:
                        raise ValueError("Не загрузились модули новой версии: " + ", ".join(errors))
                    job["running_url"] = info["url"]
                    return
        time.sleep(.3)
    raise ValueError("Новая версия не прошла проверку запуска")


def stop_child(process) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run(job_path: Path, recover: bool = False, app_override: Path | None = None) -> int:
    job = read_json(job_path)
    if recover:
        relocate(job, job_path, app_override)
    app, root = Path(job["app"]).resolve(), Path(job["root"]).resolve()
    marker = app / MARKER
    with FileLock(root / "install.lock"):
        def state(phase, message="", **extra):
            job.update(phase=phase, message=message, worker_pid=os.getpid(),
                       done=0, total=0, unit="steps", current_file="", speed=0, phase_started=time.time())
            job.update(extra)
            atomic_json(job_path, job)

        if recover:
            backup = read_json(root / "backups" / job["id"] / "backup.json")
            if backup:
                selected = set(job["applied"]) | ({job["pending"]} if job.get("pending") else set()) if "applied" in job else None
                restore_backup(backup, root, app, selected)
            state("rolled_back", "Восстановлена предыдущая версия после прерванной установки", finished=time.time())
            marker.unlink(missing_ok=True)
            return 0

        process, backup = None, None
        try:
            state("waiting", "Ожидание закрытия Yakumo")
            wait_parent(job["parent_pid"])
            state("validating", "Повторная проверка подготовленных файлов")
            validate_plan(job, job_path)
            state("backing_up", "Сохранение резервной копии")
            backup = make_backup(job, app, root, job_path)
            atomic_json(marker, {"job": str(job_path), "worker": str(job_path.parent / "worker.py"), "pid": os.getpid()})
            state("installing", "Замена файлов программы")
            apply_files(job, app, root, job_path)
            state("verifying", "Проверка запуска")
            process = launch(job)
            healthy(process, job)
            state("done", "Предыдущая версия восстановлена" if job.get("kind") == "rollback" else "Обновление установлено",
                  finished=time.time(), done=1, total=1)
            atomic_json(root / "last-backup.json", {"id": backup["id"]})
            marker.unlink(missing_ok=True)
            if job.get("open_browser_on_change") and job.get("running_url") != job.get("previous_url"):
                webbrowser.open(job["running_url"].rstrip("/") + "/#/update")
            shutil.rmtree(root / "stages" / job["stage"], ignore_errors=True)
            return 0
        except Exception as exc:
            detail = error_info(exc)
            stop_child(process)
            try:
                if backup:
                    state("restoring", "Восстановление предыдущей версии")
                    selected = set(job["applied"]) | ({job["pending"]} if job.get("pending") else set()) if "applied" in job else None
                    restore_backup(backup, root, app, selected)
                # Не запускать второй экземпляр, если старый процесс ещё работает.
                if not pid_alive(job["parent_pid"]):
                    state("verifying", "Запуск предыдущей версии")
                    process = launch(job)
                    healthy(process, job)
                state("rolled_back" if backup else "failed", detail["message"], error_detail=detail, finished=time.time())
                marker.unlink(missing_ok=True)
                if job.get("open_browser_on_change") and job.get("running_url") != job.get("previous_url"):
                    webbrowser.open(job["running_url"].rstrip("/") + "/#/update")
            except Exception as restore_error:
                recovery = error_info(restore_error)
                state("recovery_failed", detail["message"] + " Восстановление: " + recovery["message"],
                      error_detail=recovery, finished=time.time())
            return 1


def recover_if_needed(job_path: Path, app: Path | None = None) -> int:
    deadline = time.monotonic() + 60
    while True:
        job = relocate(read_json(job_path), job_path, app)
        phase = job.get("phase")
        if phase in ("done", "rolled_back", "failed"):
            (Path(job["app"]) / MARKER).unlink(missing_ok=True)
            return 0
        if not pid_alive(job.get("worker_pid", 0)):
            return run(job_path, recover=True, app_override=app)
        if phase == "verifying":
            return 0  # установщик уже заменил все файлы и запускает именно этот процесс
        if time.monotonic() >= deadline:
            raise ValueError("Установщик ещё работает. Повторите запуск после завершения")
        time.sleep(.2)


if __name__ == "__main__":
    try:
        path, flags = Path(sys.argv[1]), sys.argv[2:]
        app = Path(flags[flags.index("--app") + 1]) if "--app" in flags[:-1] else None
        raise SystemExit(recover_if_needed(path, app) if "--recover-if-needed" in flags else
                         run(path, "--recover" in flags, app))
    except Exception as exc:
        print(f"Yakumo update: {exc}", file=sys.stderr)
        raise SystemExit(1)
