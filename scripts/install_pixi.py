"""Install the pinned PixiJS distribution locally for the optional Galaxy view.

Run once with: py -3 scripts/install_pixi.py
No network requests are needed by Yakumo after installation.
"""
from __future__ import annotations
import hashlib
import pathlib
import urllib.request

VERSION = "8.21.0"
URL = f"https://cdn.jsdelivr.net/npm/pixi.js@{VERSION}/dist/pixi.min.js"
DEST = pathlib.Path(__file__).resolve().parents[1] / "modules" / "brain" / "pixi.min.js"
MAX_BYTES = 3_000_000


def main() -> None:
    request = urllib.request.Request(URL, headers={"User-Agent": "Yakumo-Pixi-vendor/1"})
    with urllib.request.urlopen(request, timeout=35) as response:
        data = response.read(MAX_BYTES + 1)
    if not 100_000 < len(data) <= MAX_BYTES:
        raise RuntimeError("Unexpected PixiJS bundle size")
    if b"PIXI" not in data[:10000] and b"PIXI" not in data[-10000:]:
        raise RuntimeError("Downloaded file does not look like PixiJS")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(".js.tmp")
    temp.write_bytes(data)
    temp.replace(DEST)
    print("Installed:", DEST)
    print("SHA-256:", hashlib.sha256(data).hexdigest())
    print("For reproducible production releases, record and pin this SHA-256.")


if __name__ == "__main__":
    main()
