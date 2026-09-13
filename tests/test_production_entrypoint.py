from __future__ import annotations

import contextlib
import sys
import types
from pathlib import Path

import pass_generator


ROOT = Path(__file__).resolve().parents[1]


def _fake_qt_module(calls):
    module = types.ModuleType("getpass_qt.app")

    def main(argv=None):
        calls.append(list(argv or ()))
        return 23

    module.main = main
    return module


def test_production_self_test_delegates_to_qt_without_instance_lock(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "getpass_qt.app", _fake_qt_module(calls))
    monkeypatch.setattr(
        pass_generator,
        "_install_crash_handler",
        lambda: (_ for _ in ()).throw(AssertionError("self-test must not install production crash handler")),
    )

    result = pass_generator.main(["--self-test"])

    assert result == 23
    assert calls == [["--self-test"]]


def test_production_normal_run_uses_single_instance_and_qt(monkeypatch):
    calls = []
    lock_events = []
    monkeypatch.setitem(sys.modules, "getpass_qt.app", _fake_qt_module(calls))
    monkeypatch.setattr(pass_generator, "_install_crash_handler", lambda: lock_events.append("crash-handler"))

    import getpass_core.config as config
    import getpass_core.instance as instance

    @contextlib.contextmanager
    def fake_single_instance(data_dir):
        lock_events.append(("enter", data_dir))
        try:
            yield
        finally:
            lock_events.append(("exit", data_dir))

    monkeypatch.setattr(instance, "single_instance", fake_single_instance)

    result = pass_generator.main([])

    assert result == 23
    assert calls == [[]]
    assert lock_events == [
        "crash-handler",
        ("enter", config.DATA_DIR),
        ("exit", config.DATA_DIR),
    ]


def test_production_launcher_is_qt_only_and_legacy_launcher_preserves_tkinter():
    production = (ROOT / "pass_generator.py").read_text(encoding="utf-8")
    legacy = (ROOT / "legacy_pass_generator.py").read_text(encoding="utf-8")

    assert "from getpass_qt.app import main as qt_main" in production
    assert "getpass_ui.app" not in production
    assert "from tkinter import messagebox" not in production
    assert "from getpass_ui.app import App" in legacy
    assert "enable_dpi_awareness" in legacy


def test_qt_runtime_uses_production_name_not_preview_name():
    source = (ROOT / "getpass_qt" / "app.py").read_text(encoding="utf-8")

    assert 'argparse.ArgumentParser(prog="GET-Passes")' in source
    assert 'QApplication(["GET-Passes"])' in source
    assert "GET-Passes Qt Preview" not in source
