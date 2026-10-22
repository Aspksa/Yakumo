"""Рабочие пути Yakumo: где хранить данные и откуда открывать файлы."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from yakumo.core.storage import StorageChoice, app_dir


@dataclass(frozen=True)
class Paths:
    app: Path        # папка программы
    data: Path       # корень данных на выбранном носителе
    config: Path     # настройки
    logs: Path       # журналы
    cache: Path      # кэш
    temp: Path       # временные файлы
    workspace: Path  # рабочая папка пользователя (что открывать по умолчанию)
    modules: Path    # модули пользователя (в дополнение к <программа>/modules)
    web: Path        # статические файлы веб-версии

    @property
    def config_file(self) -> Path:
        return self.config / "yakumo.json"

    @property
    def secrets_file(self) -> Path:
        return self.config / "secrets.json"  # ключи доступа, отдельно от настроек

    def ensure(self) -> "Paths":
        for path in (self.data, self.config, self.logs, self.cache, self.temp, self.workspace, self.modules):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


def build_paths(storage: StorageChoice, workspace: str | None = None) -> Paths:
    root = storage.data_root
    app = app_dir()
    return Paths(
        app=app,
        data=root,
        config=root / "config",
        logs=root / "logs",
        cache=root / "cache",
        temp=root / "temp",
        workspace=Path(workspace).expanduser().resolve() if workspace else root / "workspace",
        modules=root / "modules",
        web=Path(__file__).resolve().parents[1] / "web" / "static",
    )
