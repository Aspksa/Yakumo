"""Обновление проекта из Aspksa/Yakumo с подготовкой, копией и откатом."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from yakumo.core.access import AccessResponse

from .installer import atomic_json, digest, pid_alive, read_json, safe_target, same_app
from .source import GitHub, REPOSITORY, matches, unpack

NAME = "Обновление проекта"
VERSION = "1.0"
log = logging.getLogger("yakumo.modules.update")
ACTIVE = {"queued", "waiting", "backing_up", "installing", "verifying", "restoring"}
INTERVALS = {"off": 0, "hourly": 3600, "daily": 86400}


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) is not None


class Updater:
    def __init__(self, ctx, client_factory=GitHub):
        self.ctx = ctx
        self.app = Path(ctx.paths.app).resolve()
        # Ключ без буквы диска: переносной диск может подключиться под другой буквой.
        tail = os.path.normcase(os.path.splitdrive(str(self.app))[1])
        key = hashlib.sha256(tail.encode("utf-8")).hexdigest()[:16]
        updates = Path(ctx.paths.data).resolve() / "updates"
        self.root = updates / key
        legacy = updates / hashlib.sha256(str(self.app).encode("utf-8")).hexdigest()[:16]
        if legacy != self.root and legacy.is_dir() and not self.root.exists():
            try:
                legacy.rename(self.root)
            except OSError:
                pass
        self.root.mkdir(parents=True, exist_ok=True)
        self.client_factory = client_factory
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.thread = None
        self.scheduler = None
        self.action_started = 0
        self.progress = {"phase": "idle", "message": "Готово к проверке", "error": ""}
        self.protected = []
        for name in ("data", "workspace"):
            path = getattr(ctx.paths, name, None)
            if path is not None:
                try:
                    rel = Path(path).resolve().relative_to(self.app).as_posix()
                    if rel != ".":
                        self.protected.append(rel)
                except ValueError:
                    pass

    def settings(self) -> dict:
        saved = read_json(self.root / "settings.json")
        channel, schedule = saved.get("channel"), saved.get("schedule")
        return {"channel": channel if channel in ("main", "release") else "main",
                "schedule": schedule if isinstance(schedule, str) and schedule in INTERVALS else "off"}

    def token(self) -> str:
        value = read_json(self.root / "secrets.json").get("github_token", "")
        return value if isinstance(value, str) and not any(c.isspace() for c in value) else ""

    def _installed(self) -> dict:
        installed = read_json(self.root / "installed.json")
        return installed if same_app(installed.get("app"), self.app) and isinstance(installed.get("files"), dict) else {}

    def _job(self) -> dict:
        pointer = read_json(self.root / "last-job.json")
        if not valid_id(pointer.get("id")):
            return {}
        job = read_json(self.root / "jobs" / pointer["id"] / "job.json")
        if not same_app(job.get("app"), self.app):
            return {}
        job.setdefault("worker_pid", pointer.get("pid", 0))
        return job

    def _busy(self) -> bool:
        job = self._job()
        return bool((self.thread and self.thread.is_alive()) or
                    (job.get("phase") in ACTIVE and pid_alive(job.get("worker_pid", 0))))

    def state(self, _request=None) -> dict:
        with self.lock:
            catalog = read_json(self.root / "catalog.json")
            checked = read_json(self.root / "checked.json")
            ready = read_json(self.root / "ready.json")
            job = self._job()
            current = self._installed()
            pointer = read_json(self.root / "last-backup.json")
            backup_id = pointer.get("id", "")
            backup = read_json(self.root / "backups" / backup_id / "backup.json") if valid_id(backup_id) else {}
            progress = dict(self.progress)
            if job and not (self.thread and self.thread.is_alive()) and (job.get("phase") in ACTIVE or job.get("finished", 0) > self.action_started):
                progress.update(phase=job.get("phase", "idle"), message=job.get("message", ""))
                if job.get("phase") in ("rolled_back", "failed", "recovery_failed"):
                    progress["error"] = job.get("message", "")
            available = bool(checked.get("revision") == catalog.get("revision") and checked.get("available"))
            if current.get("revision") == catalog.get("revision") and current.get("installed_at", 0) >= checked.get("at", 0):
                available = False
            token = self.token()
            return {**progress, "busy": self._busy(), "repository": REPOSITORY,
                    "settings": self.settings(), "current": current.get("revision"),
                    "latest": {k: catalog.get(k) for k in ("revision", "title", "message", "date", "url", "channel")},
                    "last_checked": checked.get("at"), "available": available,
                    "changes": checked.get("changes", {}),
                    "prepared": bool(valid_id(ready.get("id")) and ready.get("revision") and ready.get("revision") == catalog.get("revision")
                                     and ready.get("channel") == self.settings()["channel"]
                                     and (self.root / "stages" / ready.get("id", "invalid")).is_dir()),
                    "prepared_revision": ready.get("revision"), "has_token": bool(token),
                    "token_hint": "…" + token[-4:] if len(token) > 8 else "•" * len(token), "can_rollback": bool(backup.get("files")),
                    "backup_date": backup.get("created"),
                    "can_install": callable(getattr(self.ctx, "request_exit", None)),
                    "local": bool(_request and getattr(_request, "access", None) and _request.access.is_local(_request)),
                    "job_id": job.get("id")}

    def _start(self, phase: str, work) -> dict:
        with self.lock:
            if self._busy():
                raise ValueError("Дождитесь завершения текущей операции")
            self.progress = {"phase": phase, "message": "Проверка GitHub" if phase == "checking" else "Подготовка обновления", "error": ""}
            self.action_started = time.time()

            def run():
                try:
                    work()
                except Exception as exc:
                    log.warning("Обновление: %s", type(exc).__name__)
                    with self.lock:
                        self.progress.update(phase="error", message="Операция не завершена", error=str(exc))

            self.thread = threading.Thread(target=run, name="yakumo-update", daemon=True)
            self.thread.start()
        return self.state()

    def check(self, _request=None) -> dict:
        return self._start("checking", self._check)

    def _check(self) -> None:
        catalog = self.client_factory(self.token()).resolve(self.settings()["channel"])
        current = self._installed()
        previous = current.get("files", {})
        changed, added, modified = [], [], []
        for rel, info in catalog["files"].items():
            if self.stopping.is_set():
                return
            target = safe_target(self.app, rel, self.protected)
            if not target.exists():
                added.append(rel)
            elif not matches(target, info):
                changed.append(rel)
            if target.is_file() and rel in previous and previous[rel].get("sha256") and digest(target) != previous[rel]["sha256"]:
                modified.append(rel)
        removed = sorted(set(previous) - set(catalog["files"]))
        for rel in removed:
            safe_target(self.app, rel, self.protected)
        available = bool(changed or added or removed)
        if not available:
            installed = {"app": str(self.app), "revision": catalog["revision"], "installed_at": time.time(), "files": {
                rel: {**info, "sha256": digest(self.app / rel)} for rel, info in catalog["files"].items()}}
            atomic_json(self.root / "installed.json", installed)
        atomic_json(self.root / "catalog.json", catalog)
        atomic_json(self.root / "checked.json", {"revision": catalog["revision"], "at": time.time(), "available": available,
                    "changes": {"changed": len(changed), "added": len(added), "removed": len(removed),
                                "local_modified": len(modified), "bytes": catalog["size"],
                                "preview": (added + changed + removed)[:30]}})
        with self.lock:
            self.progress.update(phase="available" if available else "current",
                                 message="Доступно обновление" if available else "Установлена актуальная версия", error="")

    def prepare(self, _request=None) -> dict:
        return self._start("preparing", self._prepare)

    def _prepare(self) -> None:
        catalog = read_json(self.root / "catalog.json")
        if not catalog.get("revision") or catalog.get("channel") != self.settings()["channel"]:
            raise ValueError("Сначала проверьте обновления для выбранного источника")
        for rel in catalog["files"]:
            safe_target(self.app, rel, self.protected)
        backup_size = sum((self.app / rel).stat().st_size for rel in catalog["files"] if (self.app / rel).is_file())
        if shutil.disk_usage(self.root).free < catalog["size"] * 2 + backup_size + 64 * 1024**2:
            raise ValueError("Не хватает места для загрузки, подготовки и резервной копии")
        stage_id = uuid.uuid4().hex
        stage = self.root / "stages" / stage_id
        stage.mkdir(parents=True)
        archive = self.root / f"{stage_id}.zip"
        try:
            def progress(done, total):
                if self.stopping.is_set():
                    raise ValueError("Подготовка остановлена при закрытии Yakumo")
                with self.lock:
                    self.progress.update(done=done, total=total)

            with self.lock:
                self.progress.update(phase="downloading", message="Загрузка архива", done=0, total=0)
            self.client_factory(self.token()).download(catalog["revision"], archive, progress)
            with self.lock:
                self.progress.update(phase="unpacking", message="Проверка файлов", done=0, total=len(catalog["files"]))
            files = unpack(archive, stage, catalog["files"], progress)
            previous = self._installed().get("files", {})
            ready = {"id": stage_id, "revision": catalog["revision"], "channel": catalog["channel"], "files": files,
                     "remove": sorted(set(previous) - set(files)),
                     "installed": {"app": str(self.app), "revision": catalog["revision"], "files": files}}
            old = read_json(self.root / "ready.json")
            atomic_json(self.root / "ready.json", ready)
            if valid_id(old.get("id")) and old["id"] != stage_id:
                shutil.rmtree(self.root / "stages" / old["id"], ignore_errors=True)
            with self.lock:
                self.progress.update(phase="ready", message="Файлы проверены. Можно устанавливать", error="")
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        finally:
            archive.unlink(missing_ok=True)

    def _launch_installer(self, ready: dict, kind: str) -> dict:
        command = getattr(self.ctx, "restart_command", None)
        info = getattr(self.ctx, "instance_info", None)
        exit_app = getattr(self.ctx, "request_exit", None)
        if not command or not info or not callable(exit_app):
            raise ValueError("Установка доступна при обычном запуске Yakumo")
        if shutil.disk_usage(self.app).free < sum(i["size"] for i in ready["files"].values()) + 64 * 1024**2:
            raise ValueError("На диске программы недостаточно свободного места")
        job_id = uuid.uuid4().hex
        folder = self.root / "jobs" / job_id
        folder.mkdir(parents=True)
        shutil.copy2(Path(__file__).with_name("installer.py"), folder / "worker.py")
        job = {"id": job_id, "kind": kind, "stage": ready["id"], "revision": ready.get("revision"),
               "files": ready["files"], "remove": ready["remove"], "installed": ready["installed"],
               "app": str(self.app), "root": str(self.root), "protected": self.protected,
               "parent_pid": os.getpid(), "command": list(command), "instance_info": str(info),
               "show_console": bool(getattr(self.ctx, "show_console", False)),
               "previous_url": getattr(self.ctx, "restart_url", ""),
               "open_browser_on_change": bool(getattr(self.ctx, "open_browser_on_change", False)),
               "allowed_errors": list(getattr(self.ctx, "module_errors", [])), "phase": "queued",
               "message": "Yakumo закроется и запустится после установки"}
        atomic_json(folder / "job.json", job)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (folder / "installer.log").open("ab") as output:
            process = subprocess.Popen([sys.executable, "-X", "utf8", str(folder / "worker.py"), str(folder / "job.json")],
                cwd=str(folder), stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                creationflags=flags, start_new_session=os.name != "nt")
        atomic_json(self.root / "last-job.json", {"id": job_id, "pid": process.pid})
        timer = threading.Timer(.8, exit_app)
        timer.daemon = True
        timer.start()
        return self.state()

    def install(self, _request=None) -> dict:
        with self.lock:
            if self._busy():
                raise ValueError("Дождитесь завершения текущей операции")
            ready = read_json(self.root / "ready.json")
            catalog = read_json(self.root / "catalog.json")
            if (not ready.get("id") or ready.get("revision") != catalog.get("revision")
                    or ready.get("channel") != self.settings()["channel"]):
                raise ValueError("Сначала скачайте и проверьте обновление")
            return self._launch_installer(ready, "install")

    def rollback(self, _request=None) -> dict:
        return self._start("preparing", self._prepare_rollback)

    def _prepare_rollback(self) -> None:
        pointer = read_json(self.root / "last-backup.json")
        if not valid_id(pointer.get("id")):
            raise ValueError("Резервная копия ещё не создана")
        backup = read_json(self.root / "backups" / pointer["id"] / "backup.json")
        if not same_app(backup.get("app"), self.app) or not backup.get("files"):
            raise ValueError("Резервная копия недоступна")
        stage_id = uuid.uuid4().hex
        stage = self.root / "stages" / stage_id
        stage.mkdir(parents=True)
        files, remove = {}, []
        try:
            for rel, record in backup["files"].items():
                safe_target(self.app, rel, self.protected)
                if record["exists"]:
                    source = safe_target(self.root / "backups" / pointer["id"] / "files", rel)
                    if digest(source) != record["sha256"]:
                        raise ValueError(f"Резервная копия повреждена: {rel}")
                    target = safe_target(stage, rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    files[rel] = {"sha256": record["sha256"], "mode": record["mode"], "size": source.stat().st_size}
                else:
                    remove.append(rel)
            installed = backup.get("installed", {})
            ready = {"id": stage_id, "revision": installed.get("revision"), "files": files,
                     "remove": remove, "installed": installed}
            # Этот поток уже владеет операцией, поэтому запуск без повторного _busy.
            with self.lock:
                self._launch_installer(ready, "rollback")
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    def save_settings(self, request) -> dict:
        body = request.read_json()
        if not isinstance(body, dict) or set(body) - {"channel", "schedule"}:
            raise ValueError("Ожидаются источник и расписание проверок")
        if ("channel" in body and body["channel"] not in ("main", "release")) or (
                "schedule" in body and (not isinstance(body["schedule"], str) or body["schedule"] not in INTERVALS)):
            raise ValueError("Недопустимые настройки обновления")
        with self.lock:
            if self._busy():
                raise ValueError("Дождитесь завершения текущей операции")
            previous = self.settings()
            atomic_json(self.root / "settings.json", {**previous, **body})
            if body.get("channel", previous["channel"]) != previous["channel"]:
                atomic_json(self.root / "catalog.json", {})
                atomic_json(self.root / "checked.json", {})
                self.progress.update(phase="idle", message="Проверьте выбранный источник", error="")
        return self.state(request)

    def save_token(self, request) -> dict:
        body = request.read_json()
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or len(token) > 4000 or any(c.isspace() for c in token):
            raise ValueError("Неверный токен GitHub")
        with self.lock:
            if self._busy():
                raise ValueError("Дождитесь завершения текущей операции")
            atomic_json(self.root / "secrets.json", {"github_token": token})
        return self.state(request)

    def start(self) -> None:
        def schedule():
            while not self.stopping.wait(2):
                interval = INTERVALS[self.settings()["schedule"]]
                last = read_json(self.root / "checked.json").get("at", 0)
                if not isinstance(last, (int, float)):
                    last = 0
                if interval and time.time() - max(last, getattr(self, "last_attempt", 0)) >= interval:
                    self.last_attempt = time.time()
                    try:
                        self.check()
                    except ValueError:
                        pass
        self.scheduler = threading.Thread(target=schedule, name="update-schedule", daemon=True)
        self.scheduler.start()

    def stop(self) -> None:
        self.stopping.set()


def setup(ctx):
    updater = Updater(ctx)

    def local(handler):
        def run(request):
            if not request.access.is_local(request):
                return AccessResponse(403, {"error": "Управлять обновлением можно только на компьютере с Yakumo"})
            return handler(request)
        return run

    ctx.route("/api/update", updater.state)
    for path, handler in {"check": updater.check, "prepare": updater.prepare, "install": updater.install,
                          "rollback": updater.rollback, "settings": updater.save_settings, "token": updater.save_token}.items():
        ctx.route("POST /api/update/" + path, local(handler))
    ctx.web("update.css", "update.js")
    ctx.status(lambda: {"current": updater._installed().get("revision"), "busy": updater._busy()})
    ctx.on_stop(updater.stop)
    updater.start()
