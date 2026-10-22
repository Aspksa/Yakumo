"""Модули (плагины): ядро само подхватывает их из папок ``modules``.

Модуль — это файл ``имя.py`` или папка ``имя/`` с ``__init__.py`` в одной из папок:
``<программа>/modules`` и ``<данные>/modules``. Файлы, начинающиеся с ``_``,
пропускаются. Модуль может объявить:

    NAME = "Понятное имя"
    VERSION = "1.0"

    def setup(ctx):            # обязательно
        ctx.route("/api/hello", lambda req: {"hello": "мир"})
        ctx.on_stop(lambda: ...)
        ctx.web("page.js", "page.css")   # своя страница в веб-версии
        ctx.chat_tool("имя", "что делает", run)  # инструмент для чата с Yakumo
        ctx.chat_context(lambda history, chat_id: "текст в подсказку")
        ctx.on_chat(lambda history, answer, chat_id, tools: ...)  # после ответа в чате
        if ctx.memory: ctx.memory.remember("факт", about=["Аня"])  # память Yakumo

Ошибка в одном модуле не мешает запуску остальных и ядра.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

log = logging.getLogger(__name__)

# Обработчик получает запрос (http.server.BaseHTTPRequestHandler) и возвращает
# dict/list (ответ JSON), str (HTML), bytes или кортеж (код, тип, тело).
RouteHandler = Callable[[Any], Any]


@dataclass
class ModuleInfo:
    name: str
    title: str
    version: str
    path: Path
    error: str | None = None
    web: list[str] = field(default_factory=list)  # адреса скриптов и стилей страницы модуля

    def as_dict(self) -> dict:
        return {"name": self.name, "title": self.title, "version": self.version,
                "path": str(self.path), "error": self.error, "web": self.web}


@dataclass
class Context:
    """То, что ядро даёт модулям."""

    paths: Any
    config: Any
    routes: dict[str, RouteHandler] = field(default_factory=dict)
    stop_hooks: list[Callable[[], None]] = field(default_factory=list)
    status_hooks: dict[str, Callable[[], Any]] = field(default_factory=dict)
    current: str = ""
    current_dir: Path | None = None
    web_files: dict[str, list[str]] = field(default_factory=dict)
    cloud: Any = None  # CloudService: модули могут обращаться к моделям Cloud.ru
    chat_tools: dict[str, Any] = field(default_factory=dict)
    memory: Any = None  # память Yakumo (модуль brain): remember, recall, facts, moved, say
    services: dict[str, Any] = field(default_factory=dict)  # что модули дают друг другу, например "disk"
    chat_contexts: list[Callable] = field(default_factory=list)
    chat_listeners: list[Callable] = field(default_factory=list)
    request_exit: Callable[[], None] | None = None  # завершение ядра для установщика
    restart_command: list[str] = field(default_factory=list)
    instance_info: Path | None = None
    module_errors: list[str] = field(default_factory=list)
    show_console: bool = False
    restart_url: str = ""
    open_browser_on_change: bool = False

    @property
    def log(self) -> logging.Logger:
        return logging.getLogger(f"yakumo.modules.{self.current}")

    def route(self, path: str, handler: RouteHandler) -> None:
        if path in self.routes:
            raise ValueError(f"Маршрут {path} уже занят")
        self.routes[path] = handler

    def web(self, *files: str) -> None:
        """Подключить к веб-версии файлы .js/.css из папки модуля.

        Они отдаются по адресу /modules/<модуль>/<файл> и загружаются на
        каждой странице; скрипт может добавить свой раздел через Yakumo.addPage.
        """
        types = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
        for name in files:
            path = self.current_dir / name
            ctype = types.get(path.suffix)
            if ctype is None or not path.is_file():
                raise ValueError(f"Нет файла {name} (нужен .js или .css)")
            url = f"/modules/{self.current}/{name}"
            # Читаем при каждом запросе: правки видны после обновления страницы.
            self.route(url, lambda _req, p=path, t=ctype: (200, t, p.read_bytes()))
            self.web_files.setdefault(self.current, []).append(url)

    def chat_tool(self, name: str, description: str, run: Callable[[dict], Any], *, change: bool = False,
                  title: Callable[[dict], str] | None = None) -> None:
        """Инструмент, которым Yakumo пользуется в чате.

        description объясняет модели, что делает инструмент и какие аргументы ждёт.
        change=True: инструмент меняет данные — Yakumo только предлагает его в плане,
        а выполняется он после подтверждения пользователя. title(args) — подпись для пользователя.
        """
        from yakumo.core.cloud import ChatTool

        if name in self.chat_tools:
            raise ValueError(f"Инструмент {name} уже есть")
        self.chat_tools[name] = ChatTool(name, description, run, change, title)

    def chat_context(self, hook: Callable[[list[dict], str], str | None]) -> None:
        """Дополнение к системной подсказке чата.

        hook(history, chat_id) получает реплики разговора и id беседы из браузера
        и возвращает текст, который модель увидит перед разговором (или None).
        """
        self.chat_contexts.append(hook)

    def on_chat(self, hook: Callable[[list[dict], str, str, list], None]) -> None:
        """hook(history, answer, chat_id, tools) — после каждого ответа в чате; tools — [(имя, args)],
        которые модель вызвала. Должен работать быстро."""
        self.chat_listeners.append(hook)

    def on_stop(self, hook: Callable[[], None]) -> None:
        self.stop_hooks.append(hook)

    def status(self, hook: Callable[[], Any]) -> None:
        """Добавить данные модуля в /api/status."""
        self.status_hooks[self.current] = hook

    def stop(self) -> None:
        for hook in reversed(self.stop_hooks):
            try:
                hook()
            except Exception:  # noqa: BLE001
                log.exception("Ошибка при остановке модуля")


def discover(dirs: list[Path]) -> list[tuple[str, Path]]:
    """Найти модули; при совпадении имён побеждает первая папка в списке."""
    found: dict[str, Path] = {}
    for base in dirs:
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.name.startswith(("_", ".")):
                continue
            if entry.suffix == ".py" and entry.is_file():
                found.setdefault(entry.stem, entry)
            elif entry.is_dir() and (entry / "__init__.py").is_file():
                found.setdefault(entry.name, entry / "__init__.py")
    return list(found.items())


def _import(name: str, path: Path) -> ModuleType:
    # Общий родительский пакет: без него не работает «from . import соседний_файл» внутри модуля-папки.
    if "yakumo_modules" not in sys.modules:
        parent = ModuleType("yakumo_modules")
        parent.__path__ = []
        sys.modules["yakumo_modules"] = parent
    mod_name = f"yakumo_modules.{name}"
    spec = importlib.util.spec_from_file_location(
        mod_name, path, submodule_search_locations=[str(path.parent)] if path.name == "__init__.py" else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return module


def load_all(ctx: Context, dirs: list[Path], disabled: list[str] | None = None) -> list[ModuleInfo]:
    infos: list[ModuleInfo] = []
    for name, path in discover(dirs):
        if name in (disabled or []):
            continue
        info = ModuleInfo(name, name, "", path)
        try:
            module = _import(name, path)
            info.title = getattr(module, "NAME", name)
            info.version = str(getattr(module, "VERSION", ""))
            setup = getattr(module, "setup", None)
            if not callable(setup):
                raise AttributeError("нет функции setup(ctx)")
            ctx.current, ctx.current_dir = name, path.parent
            setup(ctx)
            info.web = ctx.web_files.get(name, [])
            log.info("Модуль загружен: %s %s", info.title, info.version)
        except Exception as exc:  # noqa: BLE001
            info.error = f"{type(exc).__name__}: {exc}"
            log.exception("Модуль %s не загружен", name)
        finally:
            ctx.current, ctx.current_dir = "", None
        infos.append(info)
    return infos
