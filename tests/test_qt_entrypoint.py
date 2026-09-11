from pathlib import Path

from getpass_qt.app import main


def test_qt_self_test_returns_zero(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main(["--self-test"]) == 0


def test_phase1_keeps_tkinter_as_default_production_entrypoint():
    source = (
        Path(__file__).resolve().parents[1] / "pass_generator.py"
    ).read_text(encoding="utf-8")
    assert "from getpass_ui.app import App" in source
    assert "from getpass_qt" not in source
