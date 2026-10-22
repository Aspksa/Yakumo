"""Точка входа: связывает выбор носителя, пути, сеть и веб-сервер."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import webbrowser

from yakumo import APP_NAME, __version__
from yakumo.core.config import Config
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
    p.add_argument("--info", action="store_true", help="показать носители, пути и адрес и выйти")
    return p.parse_args(argv)


def setup_logging(paths: Paths) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(paths.logs / "yakumo.log", encoding="utf-8"))
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    storage = choose_storage(args.data_dir)
    # Рабочую папку можно задать в настройках, поэтому пути строим в два шага.
    paths = build_paths(storage).ensure()
    config = Config.load(paths.config_file)
    if not paths.config_file.exists():
        config.save(paths.config_file)
    paths = build_paths(storage, args.workspace or config.workspace).ensure()

    endpoint = choose_endpoint(args.host or config.host, args.port or config.port, args.lan or config.lan)

    if args.info:
        print_info(storage, paths, endpoint.url)
        return 0

    setup_logging(paths)
    log.info("Данные: %s (%s)", storage.data_root, storage.reason)
    log.info("Рабочая папка: %s", paths.workspace)

    from yakumo.web.server import create_server

    def status() -> dict:
        return {
            "app": APP_NAME,
            "version": __version__,
            "storage": {"root": str(storage.data_root), "reason": storage.reason},
            "paths": paths.as_dict(),
            "url": endpoint.url,
        }

    # Порт мог заняться между проверкой и запуском: пробуем следующий.
    for _ in range(5):
        try:
            server = create_server(endpoint.host, endpoint.port, paths.web, status)
            break
        except OSError:
            log.warning("Порт %s занят, ищу другой", endpoint.port)
            endpoint = choose_endpoint(endpoint.host, endpoint.port + 1)
    else:
        log.error("Не удалось найти свободный порт")
        return 1

    log.info("Веб-версия: %s", endpoint.url)
    if not args.no_browser and config.open_browser:
        threading.Timer(0.5, webbrowser.open, args=(endpoint.url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Остановка")
    finally:
        server.server_close()
    return 0
