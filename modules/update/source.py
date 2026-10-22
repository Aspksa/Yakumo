"""Неизменяемый снимок GitHub: каталог файлов, архив и проверка каждого blob."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .installer import safe_rel, safe_target

REPOSITORY = "Aspksa/Yakumo"
API = "https://api.github.com/repos/" + REPOSITORY
MAX_ARCHIVE = 256 * 1024**2
MAX_UNPACKED = 512 * 1024**2
MAX_FILES = 10_000
MAX_FILE = 64 * 1024**2
MAX_TEXT = 8 * 1024**2  # предел для сверки текста с переводом строк CRLF
REQUIRED = {"Yakumo.bat", "Yakumo.pyw", "yakumo/__init__.py", "yakumo/__main__.py", "yakumo/app.py"}


class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        if (url.scheme != "https" or url.username is not None or url.password is not None
                or url.hostname not in {"api.github.com", "github.com", "codeload.github.com"}):
            raise ValueError("GitHub перенаправил загрузку на неподдерживаемый адрес")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and url.hostname != "api.github.com":
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, token=""):
        self.token = token
        self.opener = urllib.request.build_opener(GitHubRedirect())

    def open(self, suffix: str):
        headers = {"User-Agent": "Yakumo-Updater", "Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(API + suffix, headers=headers)
        try:
            return self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                text = "GitHub не принял токен. Проверьте его или удалите для публичного репозитория"
            elif exc.code in (403, 429):
                text = "GitHub ограничил запросы или доступ. Попробуйте позже либо укажите токен с Contents: read-only"
            elif exc.code == 404:
                text = "Репозиторий, ветка или опубликованный выпуск не найдены. Для закрытого репозитория нужен токен"
            else:
                text = f"GitHub временно недоступен (HTTP {exc.code})"
            raise ValueError(text) from None
        except (urllib.error.URLError, OSError):
            raise ValueError("Нет связи с GitHub. Проверьте подключение к интернету") from None

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
                "message": str(commit.get("commit", {}).get("message", "")).split("\n")[0][:300],
                "date": commit.get("commit", {}).get("committer", {}).get("date"),
                "url": f"https://github.com/{REPOSITORY}/commit/{sha}"}

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
                    block = response.read(1024 * 1024)
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
            progress(len(result), len(expected))
    if result.keys() != expected.keys():
        raise ValueError("В архиве не хватает файлов")
    for rel in result:
        if Path(rel).suffix.lower() in (".py", ".pyw"):
            ast.parse((stage / rel).read_text(encoding="utf-8-sig"), filename=rel)
    return result
