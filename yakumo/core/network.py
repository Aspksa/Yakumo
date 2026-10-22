"""Анализ сети и выбор свободного адреса и порта для веб-версии."""

from __future__ import annotations

import socket
import os
from dataclasses import dataclass

DEFAULT_PORT = 8765
PORT_SCAN_LIMIT = 100
LOCALHOST = "127.0.0.1"


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int

    @property
    def url(self) -> str:
        host = "localhost" if self.host in (LOCALHOST, "0.0.0.0") else self.host
        return f"http://{host}:{self.port}/"


def local_addresses() -> list[str]:
    """IPv4-адреса машины: loopback и адреса в локальной сети."""
    found: list[str] = [LOCALHOST]
    # Адрес, через который идёт маршрут наружу (пакеты не отправляются).
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except (OSError, UnicodeError):  # русское имя компьютера может не пройти IDNA
        pass
    result: list[str] = []
    for addr in found:
        if addr not in result and not addr.startswith("169.254."):
            result.append(addr)
    return result


def lan_address() -> str | None:
    """Первый не-loopback адрес, если он есть."""
    return next((a for a in local_addresses() if not a.startswith("127.")), None)


def is_port_free(host: str, port: int) -> bool:
    """Порт свободен, если на нём можно открыть слушающий сокет."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Без SO_REUSEADDR: на Windows он позволил бы «занять» чужой порт.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        elif os.name != "nt":
            # Разрешить повторный запуск после собственных TIME_WAIT-соединений.
            # Активный слушатель по-прежнему не даст занять его адрес.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:  # занят или запрещён
            return False
    # Дополнительно проверяем, что никто не слушает этот порт на loopback.
    probe_host = LOCALHOST if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((probe_host, port)) != 0


def find_free_port(host: str, start: int = DEFAULT_PORT, limit: int = PORT_SCAN_LIMIT) -> int:
    """Первый свободный порт начиная с start; иначе порт, выданный системой."""
    for port in range(start, min(start + limit, 65536)):
        if is_port_free(host, port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def choose_endpoint(host: str | None = None, port: int | None = None, lan: bool = False) -> Endpoint:
    """Выбирает адрес и порт.

    host: явный адрес; иначе 127.0.0.1, а с lan=True адрес в локальной сети
    (при его отсутствии 0.0.0.0).
    port: желаемый порт; если занят, берётся следующий свободный.
    """
    if host is None:
        host = (lan_address() or "0.0.0.0") if lan else LOCALHOST
    if host not in ("0.0.0.0", "") and host not in local_addresses():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, 0))
        except OSError:
            host = LOCALHOST
    return Endpoint(host, find_free_port(host, port or DEFAULT_PORT))
