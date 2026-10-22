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

from .details import MAX_DIFF_BYTES, file_diff, read_small, version_info
from .installer import atomic_json, digest, error_info, pid_alive, read_json, safe_target, same_app
from .source import GitHub, REPOSITORY, matches, unpack

NAME = "Обновление проекта"
VERSION = "1.1"
log = logging.getLogger("yakumo.modules.update")
ACTIVE = {"queued", "waiting", "validating", "backing_up", "installing", "verifying", "restoring"}
INTERVALS = {"off": 0, "hourly": 3600, "daily": 86400}


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) is not None


def commit_titles(commits) -> list[str]:
    """Заголовки коммитов для «истории меня»; у слияний PR берётся название PR, а не «Merge pull request»."""
    titles = []
    for item in commits if isinstance(commits, list) else []:
        lines = [x.strip() for x in str(item.get("message", "") if isinstance(item, dict) else "").splitlines() if x.strip()]
        if lines and lines[0].startswith("Merge ") and len(lines) > 1:
            lines = lines[1:]
        if lines and not lines[0].startswith("Merge ") and lines[0] not in titles:
            titles.append(lines[0][:200])
    return titles[:15]


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
        self.preview_lock = threading.Lock()
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

    def _client(self):
        client = self.client_factory(self.token())
        if isinstance(client, GitHub):
            saved = read_json(self.root / "github-limit.json")
            client.rate_limit = {k: v for k, v in saved.items()
                                 if k in ("limit", "remaining", "used", "reset", "retry_at", "observed_at")
                                 and isinstance(v, (int, float)) and v >= 0}
            client.on_rate_limit = lambda value: atomic_json(self.root / "github-limit.json", value)
        return client

    def _error(self, exc):
        value = error_info(exc)
        token = self.token()
        if token:
            value = {k: v.replace(token, "[скрыто]") if isinstance(v, str) else v for k, v in value.items()}
        return value

    def _set_progress(self, phase, message, unit="steps", total=0):
        with self.lock:
            self.progress.update(phase=phase, message=message, done=0, total=total, unit=unit,
                                 speed=0, current_file="", phase_started=time.time(), error="", error_detail=None)

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

    def _busy(self, include_preview=True) -> bool:
        job = self._job()
        return bool((include_preview and self.preview_lock.locked()) or (self.thread and self.thread.is_alive()) or
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
                for key in ("done", "total", "unit", "speed", "current_file", "phase_started", "error_detail"):
                    progress[key] = job.get(key)
                if job.get("phase") in ("rolled_back", "failed", "recovery_failed"):
                    progress["error"] = job.get("message", "")
            available = bool(checked.get("revision") == catalog.get("revision") and checked.get("available"))
            if current.get("revision") == catalog.get("revision") and current.get("installed_at", 0) >= checked.get("at", 0):
                available = False
            token = self.token()
            return {**progress, "busy": self._busy(), "repository": REPOSITORY,
                    "settings": self.settings(), "current": current.get("revision"), "current_info": version_info(current),
                    "latest": {**version_info(catalog), "url": catalog.get("url")},
                    "notes": catalog.get("notes", ""), "notes_kind": catalog.get("notes_kind"),
                    "comparison": checked.get("comparison", {}), "notes_warning": checked.get("notes_warning"),
                    "rate_limit": read_json(self.root / "github-limit.json"),
                    "last_checked": checked.get("at"), "available": available,
                    "changes": {k: v for k, v in checked.get("changes", {}).items() if k != "items"},
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
            self._set_progress(phase, "Проверка GitHub" if phase == "checking" else "Подготовка обновления")
            self.action_started = time.time()

            def run():
                try:
                    work()
                except Exception as exc:
                    log.warning("Обновление: %s", type(exc).__name__)
                    with self.lock:
                        detail = self._error(exc)
                        self.progress.update(phase="error", message="Операция не завершена", error=detail["message"], error_detail=detail)

            self.thread = threading.Thread(target=run, name="yakumo-update", daemon=True)
            self.thread.start()
        return self.state()

    def check(self, _request=None) -> dict:
        self._start("checking", self._check)
        return self.state(_request)

    def _check(self) -> None:
        client = self._client()
        catalog = client.resolve(self.settings()["channel"])
        current = self._installed()
        previous = current.get("files", {})
        changed, added, modified = [], [], []
        self._set_progress("checking", "Сравнение файлов с выбранной версией", "files", len(catalog["files"]))
        for number, (rel, info) in enumerate(catalog["files"].items(), 1):
            if self.stopping.is_set():
                return
            target = safe_target(self.app, rel, self.protected)
            if not target.exists():
                added.append(rel)
            elif not matches(target, info):
                changed.append(rel)
            if target.is_file() and rel in previous and previous[rel].get("sha256") and digest(target) != previous[rel]["sha256"]:
                modified.append(rel)
            with self.lock:
                self.progress.update(done=number, current_file=rel)
        removed = sorted(set(previous) - set(catalog["files"]))
        for rel in removed:
            safe_target(self.app, rel, self.protected)
        available = bool(changed or added or removed)
        if not available:
            installed = {**version_info(catalog), "app": str(self.app), "revision": catalog["revision"], "installed_at": time.time(), "files": {
                rel: {**info, "sha256": digest(self.app / rel)} for rel, info in catalog["files"].items()}}
            atomic_json(self.root / "installed.json", installed)
            self._remember()
        comparison, notes_warning = {}, None
        if current.get("revision") and current["revision"] != catalog["revision"]:
            try:
                comparison = client.compare(current["revision"], catalog["revision"])
                if not isinstance(comparison, dict):
                    comparison = {}
            except Exception as exc:
                notes_warning = self._error(exc)
        atomic_json(self.root / "catalog.json", catalog)
        atomic_json(self.root / "checked.json", {"revision": catalog["revision"], "at": time.time(), "available": available,
                    "comparison": comparison, "notes_warning": notes_warning,
                    "changes": {"changed": len(changed), "added": len(added), "removed": len(removed),
                                "local_modified": len(modified), "bytes": catalog["size"],
                                "items": [{"path": p, "status": s} for s, paths in (("added", added), ("changed", changed), ("removed", removed)) for p in sorted(paths)],
                                "preview": (added + changed + removed)[:30]}})
        with self.lock:
            self.progress.update(phase="available" if available else "current",
                                 message="Доступно обновление" if available else "Установлена актуальная версия", error="", current_file="")

    def prepare(self, _request=None) -> dict:
        self._start("preparing", self._prepare)
        return self.state(_request)

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
            started = time.monotonic()

            def progress(done, total, current_file=""):
                if self.stopping.is_set():
                    raise ValueError("Подготовка остановлена при закрытии Yakumo")
                with self.lock:
                    self.progress.update(done=done, total=total, current_file=current_file,
                        speed=done / max(time.monotonic() - started, .01) if self.progress.get("unit") == "bytes" else 0)

            self._set_progress("downloading", "Загрузка архива", "bytes")
            self._client().download(catalog["revision"], archive, progress)
            archive_size = archive.stat().st_size
            self._set_progress("unpacking", "Распаковка и проверка файлов", "files", len(catalog["files"]))
            files = unpack(archive, stage, catalog["files"], progress)
            previous = self._installed().get("files", {})
            ready = {"id": stage_id, "revision": catalog["revision"], "channel": catalog["channel"], "files": files,
                     "remove": sorted(set(previous) - set(files)),
                     "installed": {**version_info(catalog), "app": str(self.app), "revision": catalog["revision"], "files": files}}
            old = read_json(self.root / "ready.json")
            atomic_json(self.root / "ready.json", ready)
            catalog["archive_size"] = archive_size
            atomic_json(self.root / "catalog.json", catalog)
            if valid_id(old.get("id")) and old["id"] != stage_id:
                shutil.rmtree(self.root / "stages" / old["id"], ignore_errors=True)
            with self.lock:
                self.progress.update(phase="ready", message="Файлы проверены. Можно устанавливать", error="", current_file="")
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
               "started": time.time(), "from_version": version_info(self._installed()), "to_version": version_info(ready["installed"]),
               "commits": self._commits(ready.get("revision")) if kind == "install" else [],
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

    def _commits(self, revision) -> list[dict]:
        checked = read_json(self.root / "checked.json")
        commits = checked.get("comparison", {}).get("commits") if checked.get("revision") == revision else None
        return [{"message": str(c.get("message", ""))[:2000]} for c in commits[:30] if isinstance(c, dict)] if isinstance(commits, list) else []

    def _remember(self) -> None:
        try:
            self.remember_versions()
        except Exception as exc:  # память не должна мешать обновлению
            log.warning("Обновление: история версий не записана: %s", type(exc).__name__)

    def remember_versions(self) -> int:
        """Отдать «Мозгу» установленные версии: Yakumo помнит, когда и чем её обновили."""
        memory = getattr(self.ctx, "memory", None)
        if memory is None or not callable(getattr(memory, "version", None)):
            return 0
        added = 0
        folders = sorted((p for p in (self.root / "jobs").glob("*") if p.is_dir() and valid_id(p.name)),
                         key=lambda p: p.stat().st_mtime)
        for folder in folders:
            job = read_json(folder / "job.json")
            if job.get("phase") != "done" or not same_app(job.get("app"), self.app):
                continue
            to = job.get("to_version") if isinstance(job.get("to_version"), dict) else {}
            before = job.get("from_version") if isinstance(job.get("from_version"), dict) else {}
            changes = commit_titles(job.get("commits"))
            if not changes and job.get("kind") == "install" and isinstance(to.get("message"), str):
                changes = commit_titles([{"message": to["message"]}])
            added += bool(memory.version({
                "key": "job:" + folder.name, "kind": "rollback" if job.get("kind") == "rollback" else "install",
                "revision": to.get("revision") or job.get("revision"), "from_revision": before.get("revision"),
                "title": to.get("title"), "date": to.get("date") or to.get("published_at"),
                "at": job.get("finished") or job.get("started"), "changes": changes}))
        current = self._installed()
        known = memory.versions()
        if current.get("revision") and (not known or known[0].get("revision") != current["revision"]):
            info = version_info(current)
            added += bool(memory.version({
                "key": "seen:" + current["revision"], "kind": "seen", "revision": current["revision"],
                "title": info.get("title"), "date": info.get("date") or info.get("published_at"),
                "at": current.get("installed_at"), "changes": commit_titles([{"message": info.get("message") or ""}])}))
        return added

    def _preview_body(self, request):
        body = request.read_json()
        if not isinstance(body, dict):
            raise ValueError("Неверный запрос просмотра")
        return body

    def changes(self, request):
        body = self._preview_body(request)
        checked = read_json(self.root / "checked.json")
        if body.get("revision") != checked.get("revision"):
            raise ValueError("Список изменений обновился. Откройте его заново")
        offset = body.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Неверная страница списка")
        items = checked.get("changes", {}).get("items", [])
        return {"revision": checked.get("revision"), "items": items[offset:offset + 50], "total": len(items)}

    def diff(self, request):
        body = self._preview_body(request)
        # Ограничиваем параллельные построения diff, чтобы длинные файлы не занимали все потоки.
        if not self.preview_lock.acquire(blocking=False):
            raise ValueError("Дождитесь открытия предыдущего файла")
        try:
            with self.lock:
                if self._busy(include_preview=False):
                    raise ValueError("Дождитесь завершения текущей операции")
                catalog = read_json(self.root / "catalog.json")
                checked = read_json(self.root / "checked.json")
                rel = body.get("path")
                if (not body.get("revision") or body["revision"] != catalog.get("revision")
                        or checked.get("revision") != catalog.get("revision")):
                    raise ValueError("Выбранная версия изменилась. Обновите список файлов")
                allowed = {i["path"] for i in checked.get("changes", {}).get("items", [])}
                if rel not in allowed:
                    raise ValueError("Файла нет в списке изменений выбранной версии")
            before, before_size = read_small(safe_target(self.app, rel, self.protected))
            expected = catalog["files"].get(rel)
            after, after_size = b"", 0
            if expected:
                after_size = expected["size"]
                if after_size > MAX_DIFF_BYTES or before is None:
                    after = None
                else:
                    ready = read_json(self.root / "ready.json")
                    staged = safe_target(self.root / "stages" / ready["id"], rel) if valid_id(ready.get("id")) else None
                    if ready.get("revision") == catalog["revision"] and staged and staged.is_file():
                        if not matches(staged, expected):
                            raise ValueError("Контрольная сумма подготовленного файла не совпала")
                        after, after_size = read_small(staged)
                    else:
                        after = self._client().blob(expected)
            return {**file_diff(rel, before, after, before_size, after_size), "revision": catalog["revision"]}
        finally:
            self.preview_lock.release()

    def history(self, request):
        body = self._preview_body(request)
        offset = body.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Неверная страница истории")
        folders = sorted((p for p in (self.root / "jobs").glob("*") if p.is_dir() and valid_id(p.name)),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        items = []
        for folder in folders[offset:offset + 20]:
            job = read_json(folder / "job.json")
            if not same_app(job.get("app"), self.app):
                continue
            before = job.get("from_version")
            if not isinstance(before, dict):
                before = version_info(read_json(self.root / "backups" / folder.name / "backup.json").get("installed", {}))
            phase = job.get("phase")
            pointer = read_json(self.root / "last-job.json")
            worker_pid = job.get("worker_pid") or (pointer.get("pid", 0) if pointer.get("id") == folder.name else 0)
            if phase in ACTIVE and not pid_alive(worker_pid):
                phase = "interrupted"
            items.append({"id": folder.name, "kind": job.get("kind", "install"), "started": job.get("started", folder.stat().st_ctime),
                          "finished": job.get("finished"), "from_version": before,
                          "to_version": job.get("to_version", version_info(job.get("installed", {}))),
                          "phase": phase, "message": job.get("message"), "error_detail": job.get("error_detail")})
        return {"items": items, "total": len(folders), "next_offset": min(offset + 20, len(folders))}

    def install(self, _request=None) -> dict:
        with self.lock:
            if self._busy():
                raise ValueError("Дождитесь завершения текущей операции")
            ready = read_json(self.root / "ready.json")
            catalog = read_json(self.root / "catalog.json")
            if (not ready.get("id") or ready.get("revision") != catalog.get("revision")
                    or ready.get("channel") != self.settings()["channel"]):
                raise ValueError("Сначала скачайте и проверьте обновление")
            self._launch_installer(ready, "install")
            return self.state(_request)

    def rollback(self, _request=None) -> dict:
        self._start("preparing", self._prepare_rollback)
        return self.state(_request)

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
            atomic_json(self.root / "github-limit.json", {})
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
            try:
                return handler(request)
            except Exception as exc:
                detail = updater._error(exc)
                return AccessResponse(400, {"error": detail["message"], "error_detail": detail})
        return run

    ctx.route("/api/update", updater.state)
    for path, handler in {"check": updater.check, "prepare": updater.prepare, "install": updater.install,
                          "rollback": updater.rollback, "settings": updater.save_settings, "token": updater.save_token,
                          "changes": updater.changes, "diff": updater.diff, "history": updater.history}.items():
        ctx.route("POST /api/update/" + path, local(handler))
    ctx.web("update.css", "update.js")
    ctx.status(lambda: {"current": updater._installed().get("revision"), "busy": updater._busy()})
    ctx.on_stop(updater.stop)
    updater._remember()
    updater.start()
