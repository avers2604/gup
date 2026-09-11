from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "renderer_contract.json"
PROTECTED_FILES = (
    ROOT / "getpass_core" / "render.py",
    ROOT / "getpass_core" / "blank.py",
    ROOT / "getpass_core" / "fonts.py",
)
PROTECTED_DIRS = (
    ROOT / "assets",
    ROOT / "fonts",
    ROOT / "fronts",
)


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _protected_paths() -> list[Path]:
    files = list(PROTECTED_FILES)
    for directory in PROTECTED_DIRS:
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(files))


def main() -> int:
    payload = {
        path.relative_to(ROOT).as_posix(): _git_blob_sha(path)
        for path in _protected_paths()
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
