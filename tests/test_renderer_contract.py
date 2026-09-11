import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "renderer_contract.json"
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
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _protected_paths() -> list[Path]:
    files = list(PROTECTED_FILES)
    for directory in PROTECTED_DIRS:
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(files))


def test_renderer_contract_files_are_unchanged():
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = {
        path.relative_to(ROOT).as_posix(): _git_blob_sha(path)
        for path in _protected_paths()
    }
    assert actual == expected
