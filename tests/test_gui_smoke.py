"""Headless-проверка интерфейса: окно должно строиться и работать без дисплея.

Пропускается, если в системе нет tkinter или X-сервера (Xvfb).
"""
import os
import types

import pytest

tkinter = pytest.importorskip("tkinter")

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="нужен X-сервер (запускать через xvfb-run)")


@pytest.fixture
def app(monkeypatch, tmp_path):
    from tkinter import filedialog, messagebox, simpledialog

    from getpass_core import config
    # изоляция данных
    d = tmp_path / "data"
    d.mkdir()
    for name, value in (("DATA_DIR", str(d)), ("PHOTO_DIR", str(d / "photos")),
                        ("CONFIG_FILE", str(d / "settings.json")),
                        ("CARS_CACHE_FILE", str(d / "cars.json")),
                        ("CRASH_LOG_FILE", str(d / "crash.log"))):
        monkeypatch.setattr(config, name, value)

    monkeypatch.setattr(tkinter.Tk, "mainloop", lambda self, n=0: None)
    for name, ret in (("showerror", None), ("showwarning", None), ("showinfo", None),
                      ("askyesno", False), ("askokcancel", False),
                      ("askretrycancel", False), ("askyesnocancel", False)):
        monkeypatch.setattr(messagebox, name, lambda *a, **k: ret)
    monkeypatch.setattr(simpledialog, "askstring", lambda *a, **k: "тест")
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda *a, **k: "")
    monkeypatch.setattr(filedialog, "askopenfilename", lambda *a, **k: "")

    import subprocess
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda c, *a, **k: (
        types.SimpleNamespace(returncode=0, stdout="HP\n", stderr="")
        if c and "powershell" in str(c[0]).lower() else real(c, *a, **k)))

    from getpass_ui.app import App
    instance = App()
    yield instance
    try:
        instance.root.destroy()
    except Exception:
        pass


def pump(root, seconds=0.6):
    import time
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def test_window_builds_with_both_tabs(app):
    app.root.update()
    assert app.notebook.index("end") == 2


def test_startup_shows_no_modal_from_preview(app, monkeypatch):
    """Авто-предпросмотр не должен сам поднимать модальные окна."""
    from tkinter import messagebox
    seen = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: seen.append(a))
    pump(app.root, 1.2)
    assert seen == []


def test_preview_renders_after_input(app, tmp_path, monkeypatch):
    from PIL import Image

    from getpass_core import config
    from getpass_core import render
    path = tmp_path / "template.png"
    Image.new("RGB", (2480, 1560), "white").save(path)
    monkeypatch.setattr(config, "TEMPLATE_FILE", str(path))
    render.reset_template_cache()
    app.p1.plate_var.set("о777тв198")
    pump(app.root, 1.0)
    assert app.preview_label.cget("text") == ""
    render.reset_template_cache()


def test_preview_reports_missing_template(app, tmp_path, monkeypatch):
    """Без бланка предпросмотр объясняет причину, а не молчит и не падает."""
    from getpass_core import config, render
    monkeypatch.setattr(config, "TEMPLATE_FILE", str(tmp_path / "нет.png"))
    render.reset_template_cache()
    app.p1.plate_var.set("о777тв198")
    pump(app.root, 1.0)
    assert "template.png" in app.preview_label.cget("text")
    render.reset_template_cache()


def test_plate_normalized_to_cyrillic(app):
    app.p1.plate_var.set("O777TB198")
    pump(app.root, 0.3)
    assert app.p1.data()["plate"] == "О777ТВ198"


def test_a5_mode_disables_second_tab(app):
    app.print_mode.set("a5")
    app.update_tab_states()
    app.root.update()
    assert app.pass_notebook.tab(1, "state") == "disabled"
    app.print_mode.set("a4")
    app.update_tab_states()
    app.root.update()
    assert app.pass_notebook.tab(1, "state") == "normal"


def test_ctrl_s_ignored_from_other_window(app):
    """Ctrl+S из журнала не должен запускать печать главной формы."""
    other = tkinter.Toplevel(app.root)
    event = types.SimpleNamespace(widget=other, keysym="s", char="")
    assert app._on_ctrl(event) is None
    other.destroy()


def test_ctrl_s_works_in_main_window(app, monkeypatch):
    called = []
    monkeypatch.setattr(app, "generate_pass", lambda: called.append(1))
    event = types.SimpleNamespace(widget=app.root, keysym="s", char="")
    assert app._on_ctrl(event) == "break"
    assert called == [1]


def test_badge_requires_photo(app):
    app.badge.sur_var.set("ИВАНОВ")
    app.badge.nam_var.set("ИВАН")
    assert app.badge.validated_data() is None


def test_journal_windows_open(app):
    app.open_pass_journal()
    app.open_badge_journal()
    pump(app.root, 0.5)


def test_settings_saved_on_close(app, monkeypatch):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askokcancel", lambda *a, **k: True)
    app.entry_otb_name.delete(0, tkinter.END)
    app.entry_otb_name.insert(0, "Петров И.С.")
    app.on_closing()
    from getpass_core import config
    assert config.load_settings()["otb_name"] == "Петров И.С."
