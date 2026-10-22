"""Неизменяемый снимок GitHub: каталог файлов, архив и проверка каждого blob."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .installer import UpdateError, safe_rel, safe_target

REPOSITORY = "Aspksa/Yakumo"
API = "https://api.github.com/repos/" + REPOSITORY
MAX_ARCHIVE = 256 * 1024**2
MAX_UNPACKED = 512 * 1024**2
MAX_FILES = 10_000
MAX_FILE = 64 * 1024**2
MAX_TEXT = 8 * 1024**2  # предел для сверки текста с переводом строк CRLF
REQUIRED = {"Yakumo.bat", "Yakumo.pyw", "yakumo/__init__.py", "yakumo/__main__.py", "yakumo/app.py"}


class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, observe=None):
        super().__init__()
        self.observe = observe

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        if (url.scheme != "https" or url.username is not None or url.password is not None
                or url.hostname not in {"api.github.com", "github.com", "codeload.github.com"}):
            raise ValueError("GitHub перенаправил загрузку на неподдерживаемый адрес")
        if self.observe and urllib.parse.urlsplit(req.full_url).hostname == "api.github.com":
            self.observe(headers)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and url.hostname != "api.github.com":
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, token=""):
        self.token = token
        self.rate_limit = {}
        self.on_rate_limit = None
        self.opener = urllib.request.build_opener(GitHubRedirect(self._observe))

    def _observe(self, headers, limited=False):
        values = {}
        for key in ("limit", "remaining", "used", "reset"):
            try:
                value = int(headers.get("X-RateLimit-" + key, ""))
                if 0 <= value < 2**53:
                    values[key] = value
            except (ValueError, TypeError):
                pass
        try:
            retry = max(0, int(headers.get("Retry-After", "")))
            values["retry_at"] = time.time() + min(retry, 86400)
        except (ValueError, TypeError):
            pass
        if not values and not limited:
            return
        self.rate_limit.update(values, observed_at=time.time())
        if limited:
            until = self.rate_limit.get("reset", 0) if self.rate_limit.get("remaining") == 0 else 0
            until = max(values.get("retry_at", 0), until)
            self.rate_limit["retry_at"] = until if until > time.time() else time.time() + 60
        elif values.get("remaining", 0) > 0:
            self.rate_limit.pop("retry_at", None)
        if callable(self.on_rate_limit):
            self.on_rate_limit(dict(self.rate_limit))

    def _limited(self):
        until = max(self.rate_limit.get("retry_at", 0),
                    self.rate_limit.get("reset", 0) if self.rate_limit.get("remaining") == 0 else 0)
        return UpdateError("github_rate_limit", "GitHub временно ограничил запросы.",
                           "Дождитесь указанного времени восстановления лимита. Для публичного репозитория можно также настроить собственный токен Contents: read-only.", until)

    def open(self, suffix: str):
        if self._limited().retry_at > time.time():
            raise self._limited()
        headers = {"User-Agent": "Yakumo-Updater", "Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(API + suffix, headers=headers)
        try:
            response = self.opener.open(request, timeout=30)
            if urllib.parse.urlsplit(response.geturl()).hostname == "api.github.com":
                self._observe(response.headers)
            return response
        except urllib.error.HTTPError as exc:
            limited = (exc.code == 429 or exc.headers.get("X-RateLimit-Remaining") == "0"
                       or bool(exc.headers.get("Retry-After")))
            if exc.code == 403 and not limited:
                limited = b"rate limit" in exc.read(4096).lower()
            self._observe(exc.headers, limited=limited)
            exc.close()
            if limited:
                raise self._limited() from None
            if exc.code == 401:
                raise UpdateError("github_token", "GitHub не принял токен.",
                                  "Обновите токен или удалите его для публичного репозитория. Проверьте срок действия и Contents: read-only.") from None
            elif exc.code == 403:
                raise UpdateError("github_access", "GitHub запретил доступ к репозиторию.",
                                  "Проверьте доступ токена к Aspksa/Yakumo и разрешение Contents: read-only.") from None
            elif exc.code == 404 and suffix.startswith("/releases/latest"):
                raise UpdateError("github_no_release", "Опубликованный выпуск не найден.",
                                  "Выберите источник «Основная ветка · main» или опубликуйте выпуск на GitHub. Для закрытого репозитория проверьте доступ токена.") from None
            elif exc.code == 404:
                raise UpdateError("github_not_found", "Репозиторий, коммит или файл не найден на GitHub.",
                                  "Повторите проверку обновлений. Для закрытого репозитория проверьте токен и его доступ к репозиторию.") from None
            else:
                raise UpdateError("github_http", f"GitHub вернул HTTP {exc.code}.",
                                  "Повторите операцию позже. Если ошибка сохраняется, проверьте доступность GitHub и настройки подключения.") from None
        except (urllib.error.URLError, OSError):
            raise UpdateError("github_network", "Не удалось соединиться с GitHub.",
                              "Проверьте интернет, прокси и системную дату, затем повторите операцию.") from None

    def json(self, suffix: str) -> dict:
        with self.open(suffix) as response:
            raw = response.read(8 * 1024**2 + 1)
        if len(raw) > 8 * 1024**2:
            raise ValueError("Ответ GitHub слишком большой")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Неожиданный ответ GitHub")
        return data

    def resolve(self, channel: str) -> dict:
        ref, title = "main", "Основная ветка main"
        release = {}
        if channel == "release":
            release = self.json("/releases/latest")
            ref = release.get("tag_name")
            if not isinstance(ref, str) or not ref:
                raise ValueError("У опубликованного выпуска нет тега")
            title = str(release.get("name") or ref)[:200]
        elif channel != "main":
            raise ValueError("Неизвестный источник обновления")
        commit = self.json("/commits/" + urllib.parse.quote(ref, safe=""))
        sha = commit.get("sha", "")
        tree_sha = commit.get("commit", {}).get("tree", {}).get("sha", "")
        if not re.fullmatch(r"[a-f0-9]{40}", sha) or not re.fullmatch(r"[a-f0-9]{40}", tree_sha):
            raise ValueError("GitHub вернул неверный номер коммита")
        tree = self.json("/git/trees/" + tree_sha + "?recursive=1")
        if tree.get("truncated") or not isinstance(tree.get("tree"), list):
            raise ValueError("GitHub вернул неполный каталог. Обновление остановлено")
        files, seen, size = {}, set(), 0
        for item in tree["tree"]:
            if item.get("type") == "tree":
                continue
            if item.get("type") != "blob" or item.get("mode") not in ("100644", "100755"):
                raise ValueError("Обновление содержит ссылку или вложенный Git-репозиторий")
            rel = safe_rel(item["path"])
            if rel.casefold() in seen:
                raise ValueError("Имена файлов обновления совпадают без учёта регистра")
            seen.add(rel.casefold())
            amount = item.get("size")
            if type(amount) is not int or not 0 <= amount <= MAX_FILE or not re.fullmatch(r"[a-f0-9]{40}", item.get("sha", "")):
                raise ValueError("Повреждён каталог файлов обновления")
            files[rel] = {"git_sha": item["sha"], "size": amount,
                          "mode": 0o755 if item["mode"] == "100755" else 0o644}
            size += amount
        if len(files) > MAX_FILES or size > MAX_UNPACKED or not REQUIRED <= files.keys():
            raise ValueError("Снимок не содержит ядро Yakumo или превышает допустимый размер")
        return {"revision": sha, "title": title, "channel": channel, "files": files, "size": size,
                "version": ref if channel == "release" else sha[:10],
                "notes": str(release.get("body") or commit.get("commit", {}).get("message", ""))[:16000],
                "notes_kind": "release" if release.get("body") else "commit",
                "published_at": release.get("published_at"),
                "message": str(commit.get("commit", {}).get("message", "")).split("\n")[0][:300],
                "date": commit.get("commit", {}).get("committer", {}).get("date"),
                "url": f"https://github.com/{REPOSITORY}/commit/{sha}"}

    def compare(self, base: str, revision: str) -> dict:
        if not all(isinstance(v, str) and re.fullmatch(r"[a-f0-9]{40}", v) for v in (base, revision)):
            raise ValueError("Неверные версии для сравнения")
        data = self.json(f"/compare/{base}...{revision}?per_page=30&page=1")
        commits = []
        for item in data.get("commits", [])[:30]:
            sha = item.get("sha", "")
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                continue
            commits.append({"revision": sha, "message": str(item.get("commit", {}).get("message", ""))[:2000],
                            "date": item.get("commit", {}).get("committer", {}).get("date")})
        return {"commits": commits, "total": data.get("total_commits", len(commits)),
                "status": data.get("status"), "url": f"https://github.com/{REPOSITORY}/compare/{base}...{revision}"}

    def blob(self, expected: dict) -> bytes:
        sha, size = expected.get("git_sha", ""), expected.get("size", -1)
        if not re.fullmatch(r"[a-f0-9]{40}", sha) or type(size) is not int or not 0 <= size <= 65536:
            raise ValueError("Файл слишком большой для просмотра изменений")
        data = self.json("/git/blobs/" + sha)
        try:
            raw = base64.b64decode("".join(data["content"].split()), validate=True)
        except (KeyError, ValueError, TypeError):
            raise ValueError("GitHub вернул повреждённое содержимое файла") from None
        if (data.get("encoding") != "base64" or len(raw) != size
                or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != sha):
            raise ValueError("Контрольная сумма файла для просмотра не совпала")
        return raw

    def download(self, revision: str, destination: Path, progress) -> None:
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("Неверный номер коммита")
        total = 0
        try:
            with self.open("/zipball/" + revision) as response, destination.open("wb") as out:
                length = int(response.headers.get("Content-Length") or 0)
                if length > MAX_ARCHIVE:
                    raise ValueError("Архив обновления слишком большой")
                while True:
                    block = response.read(128 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_ARCHIVE:
                        raise ValueError("Архив обновления слишком большой")
                    out.write(block)
                    progress(total, length)
                out.flush()
                os.fsync(out.fileno())
            if length and total != length:
                raise ValueError("Архив скачан не полностью")
        except Exception:
            destination.unlink(missing_ok=True)
            raise


def git_digest(path: Path, normalize: bool = False) -> str:
    if normalize:
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def matches(path: Path, expected: dict) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    amount = path.stat().st_size
    if amount == expected["size"] and git_digest(path) == expected["git_sha"]:
        return True
    if amount > expected["size"] * 2 or amount > MAX_TEXT:
        return False
    # Git for Windows применяет eol=crlf из .gitattributes (и core.autocrlf).
    return git_digest(path, True) == expected["git_sha"]


def unpack(archive: Path, stage: Path, expected: dict, progress) -> dict:
    result, seen, root_name, expanded = {}, set(), None, 0
    with zipfile.ZipFile(archive) as zf:
        if len(zf.infolist()) > MAX_FILES * 3:
            raise ValueError("В архиве слишком много записей")
        for item in zf.infolist():
            raw = item.filename
            parts = raw.rstrip("/").split("/", 1)
            if not parts[0] or parts[0] in (".", "..") or "\\" in raw:
                raise ValueError("Повреждён корень архива")
            if root_name is None:
                root_name = parts[0]
            if parts[0] != root_name:
                raise ValueError("У архива несколько корневых папок")
            if len(parts) == 1:
                if not item.is_dir():
                    raise ValueError("Файл находится вне папки снимка")
                continue
            rel = safe_rel(parts[1])
            if item.is_dir():
                continue
            if stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG):
                raise ValueError("Архив содержит ссылку или специальный файл")
            if rel.casefold() in seen or rel not in expected:
                raise ValueError("В архиве повторный или неизвестный файл")
            seen.add(rel.casefold())
            info = expected[rel]
            expanded += item.file_size
            # Архив GitHub собирается git archive и применяет eol=crlf из .gitattributes,
            # поэтому текстовый файл может быть длиннее blob из каталога.
            crlf = info["size"] < item.file_size <= min(info["size"] * 2, MAX_TEXT)
            if (item.file_size != info["size"] and not crlf) or expanded > MAX_UNPACKED:
                raise ValueError(f"Размер файла не совпадает с каталогом GitHub: {rel}")
            target = safe_target(stage, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            git_hash = hashlib.sha1(f"blob {info['size']}\0".encode())
            sha256 = hashlib.sha256()
            amount, text = 0, []
            with zf.open(item) as source, target.open("wb") as out:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    amount += len(block)
                    if amount > item.file_size:
                        raise ValueError("Файл распаковался сверх заявленного размера")
                    out.write(block)
                    sha256.update(block)
                    if crlf:
                        text.append(block)
                    else:
                        git_hash.update(block)
            if crlf:
                raw = b"".join(text).replace(b"\r\n", b"\n")
                git_hash = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw)
            if amount != item.file_size or git_hash.hexdigest() != info["git_sha"]:
                raise ValueError(f"Контрольная сумма не совпала: {rel}")
            result[rel] = {**info, "size": amount, "sha256": sha256.hexdigest()}
            progress(len(result), len(expected), rel)
    if result.keys() != expected.keys():
        raise ValueError("В архиве не хватает файлов")
    for rel in result:
        if Path(rel).suffix.lower() in (".py", ".pyw"):
            ast.parse((stage / rel).read_text(encoding="utf-8-sig"), filename=rel)
    return result
