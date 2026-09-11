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


def test_python_contract_hash_is_line_ending_independent(tmp_path):
    lf = tmp_path / "renderer_lf.py"
    crlf = tmp_path / "renderer_crlf.py"
    lf.write_bytes(b"def render():\n    return 1\n")
    crlf.write_bytes(b"def render():\r\n    return 1\r\n")

    assert _git_blob_sha(lf) == _git_blob_sha(crlf)


def test_binary_contract_hash_preserves_exact_bytes(tmp_path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"a\nb")
    second.write_bytes(b"a\r\nb")

    assert _git_blob_sha(first) != _git_blob_sha(second)


def test_renderer_contract_files_are_unchanged():
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = {
        path.relative_to(ROOT).as_posix(): _git_blob_sha(path)
        for path in _protected_paths()
    }
    assert actual == expected
