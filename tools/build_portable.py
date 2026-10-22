"""Сборка портативной версии Yakumo для Windows со встроенным Python.

Запуск (на любой ОС с Python 3.10+ и pip):

    python tools/build_portable.py

Результат: dist/Yakumo/ и dist/Yakumo-portable-win64.zip. Распакуйте архив
куда угодно (например, на флешку) и запустите Yakumo.bat: установка Python
не нужна, данные хранятся рядом в YakumoData.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = "3.12.10"
COPY = ["Yakumo.bat", "launcher", "yakumo", "modules", "README.md", "requirements.txt"]


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        print(f"Уже скачано: {dest.name}")
        return dest
    print(f"Скачиваю {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    tmp.replace(dest)
    return dest


def configure_pth(python_dir: Path) -> None:
    """Встроенный Python игнорирует PYTHONPATH: пути задаются в ._pth."""
    pth = next(python_dir.glob("python*._pth"))
    zip_line = next(line for line in pth.read_text(encoding="utf-8").splitlines() if line.endswith(".zip"))
    # ".." — папка программы, чтобы работал `python -m yakumo`.
    pth.write_text("\n".join([zip_line, ".", "Lib\\site-packages", "..", "import site", ""]), encoding="utf-8")


def install_requirements(python_dir: Path, version: str, arch: str) -> None:
    short = ".".join(version.split(".")[:2])
    platform = {"amd64": "win_amd64", "arm64": "win_arm64", "win32": "win32"}[arch]
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-compile",
        "--target", str(python_dir / "Lib" / "site-packages"),
        "--platform", platform, "--python-version", short, "--implementation", "cp",
        "--only-binary=:all:", "-r", str(ROOT / "requirements.txt"),
    ], check=True)


def ignore(_dir, names):
    return [n for n in names if n in ("__pycache__", "YakumoData") or n.endswith(".pyc")]


def build(version: str, arch: str, out: Path, with_requirements: bool) -> Path:
    stage = out / "Yakumo"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, stage / name, ignore=ignore)
        elif src.exists():
            shutil.copy2(src, stage / name)
    (stage / "portable").write_text("Портативный режим: данные хранятся в YakumoData рядом с программой.\n",
                                    encoding="utf-8")

    url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-{arch}.zip"
    archive = download(url, out / "cache" / Path(url).name)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(stage / "python")
    configure_pth(stage / "python")
    if with_requirements:
        install_requirements(stage / "python", version, arch)

    zip_path = out / f"Yakumo-portable-{'win64' if arch == 'amd64' else arch}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*")):
            zf.write(path, Path("Yakumo") / path.relative_to(stage))
    print(f"Готово: {zip_path}")
    return zip_path


def main() -> int:
    p = argparse.ArgumentParser(description="Портативная сборка Yakumo для Windows")
    p.add_argument("--python", default=DEFAULT_PYTHON, help=f"версия встроенного Python (по умолчанию {DEFAULT_PYTHON})")
    p.add_argument("--arch", default="amd64", choices=["amd64", "arm64", "win32"])
    p.add_argument("--out", type=Path, default=ROOT / "dist")
    p.add_argument("--no-requirements", action="store_true", help="без pystray/Pillow (без значка в трее)")
    args = p.parse_args()
    build(args.python, args.arch, args.out.resolve(), not args.no_requirements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
