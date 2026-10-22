"""Точка входа: связывает выбор носителя, пути, сеть, модули и веб-сервер."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser

from yakumo import APP_NAME, __version__
from yakumo.core.config import Config
from yakumo.core.instance import InstanceLock
from yakumo.core.modules import Context, load_all
from yakumo.core.network import choose_endpoint, local_addresses
from yakumo.core.paths import Paths, build_paths
from yakumo.core.storage import StorageChoice, choose_storage, list_media

log = logging.getLogger("yakumo")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="yakumo", description=f"{APP_NAME} {__version__}")
    p.add_argument("--data-dir", help="папка данных (иначе носитель выбирается автоматически)")
    p.add_argument("--workspace", help="папка, которая открывается по умолчанию")
    p.add_argument("--host", help="адрес для веб-версии (по умолчанию 127.0.0.1)")
    p.add_argument("--port", type=int, help="желаемый порт; если занят, берётся следующий свободный")
    p.add_argument("--lan", action="store_true", help="открыть доступ из локальной сети")
    p.add_argument("--no-browser", action="store_true", help="не открывать браузер")
    p.add_argument("--no-tray", action="store_true", help="без значка в трее")
    p.add_argument("--info", action="store_true", help="показать носители, пути и адрес и выйти")
    return p.parse_args(argv)


def setup_logging(paths: Paths) -> None:
    handlers: list[logging.Handler] = [logging.FileHandler(paths.logs / "yakumo.log", encoding="utf-8")]
    if sys.stdout is not None:  # под pythonw.exe консоли нет
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers, force=True)


def print_info(storage: StorageChoice, paths: Paths, url: str) -> None:
    print(f"{APP_NAME} {__version__}")
    print("Носители:")
    for m in list_media():
        flags = ", ".join(f for f, on in (("съёмный", m.removable), ("системный", m.system)) if on)
        print(f"  {m.root}  свободно {m.free_gb} ГБ" + (f"  ({flags})" if flags else ""))
    print(f"Выбрано: {storage.data_root}  [{storage.reason}]")
    print("Пути:")
    for name, value in paths.as_dict().items():
        print(f"  {name:<10} {value}")
    print(f"Адреса машины: {', '.join(local_addresses())}")
    print(f"Веб-версия: {url}")


def open_running(lock: InstanceLock, open_browser: bool) -> int:
    """Yakumo уже запущен: открыть его вместо второго сервера."""
    url = None
    for _ in range(50):  # первый экземпляр может ещё запускаться
        url = lock.running_url()
        if url:
            break
        time.sleep(0.1)
    if not url:
        print(f"{APP_NAME} уже запущен, но его адрес пока неизвестен.")
        return 1
    print(f"{APP_NAME} уже запущен: {url}")
    if open_browser:
        webbrowser.open(url)
    return 0


def safe_console() -> None:
    """Русский текст не должен ронять вывод ни в какой кодировке консоли."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    safe_console()
    args = parse_args(argv)

    storage = choose_storage(args.data_dir)
    # Рабочую папку можно задать в настройках, поэтому пути строим в два шага.
    paths = build_paths(storage).ensure()
    config = Config.load(paths.config_file)
    if not paths.config_file.exists():
        config.save(paths.config_file)
    paths = build_paths(storage, args.workspace or config.workspace).ensure()
    open_browser = not args.no_browser and config.open_browser

    if args.info:
        endpoint = choose_endpoint(args.host or config.host, args.port or config.port, args.lan or config.lan)
        print_info(storage, paths, endpoint.url)
        return 0

    with InstanceLock() as lock:
        if not lock.acquire():
            return open_running(lock, open_browser)
        return serve(args, storage, paths, config, lock, open_browser)


def serve(args, storage: StorageChoice, paths: Paths, config: Config,
          lock: InstanceLock, open_browser: bool) -> int:
    setup_logging(paths)
    log.info("Данные: %s (%s)", storage.data_root, storage.reason)
    log.info("Рабочая папка: %s", paths.workspace)

    from yakumo.web.server import create_server

    ctx = Context(paths=paths, config=config)
    modules = load_all(ctx, [paths.app / "modules", paths.modules], config.disabled_modules)
    endpoint = choose_endpoint(args.host or config.host, args.port or config.port, args.lan or config.lan)

    def status(_req=None) -> dict:
        extra = {}
        for name, hook in ctx.status_hooks.items():
            try:
                extra[name] = hook()
            except Exception as exc:  # noqa: BLE001
                extra[name] = {"error": str(exc)}
        return {
            "app": APP_NAME,
            "version": __version__,
            "storage": {"root": str(storage.data_root), "reason": storage.reason},
            "paths": paths.as_dict(),
            "url": endpoint.url,
            "modules": [m.as_dict() for m in modules],
            "modules_status": extra,
        }

    routes = {"/api/status": status, "/api/modules": lambda _req: [m.as_dict() for m in modules], **ctx.routes}

    # Порт мог заняться между проверкой и запуском: пробуем следующий.
    for _ in range(5):
        try:
            server = create_server(endpoint.host, endpoint.port, paths.web, routes)
            break
        except OSError:
            log.warning("Порт %s занят, ищу другой", endpoint.port)
            endpoint = choose_endpoint(endpoint.host, endpoint.port + 1)
    else:
        log.error("Не удалось найти свободный порт")
        return 1

    lock.publish(endpoint.url)
    log.info("Веб-версия: %s", endpoint.url)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(endpoint.url,)).start()

    from yakumo import tray

    use_tray = config.tray and not args.no_tray and tray.available()
    try:
        if use_tray:
            web = threading.Thread(target=server.serve_forever, name="web", daemon=True)
            web.start()
            folders = {"Папка данных": paths.data, "Рабочая папка": paths.workspace,
                       "Модули": paths.modules}
            try:
                tray.run(endpoint.url, folders, on_exit=server.shutdown)
            except Exception:  # noqa: BLE001
                log.exception("Значок в трее не запустился, работаю без него")
                while web.is_alive():
                    web.join(0.5)  # с таймаутом, чтобы Ctrl+C срабатывал
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        log.info("Остановка")
    finally:
        ctx.stop()
        server.server_close()
    return 0
