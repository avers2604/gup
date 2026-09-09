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


def test_preview_renders_after_input(app):
    app.p1.plate_var.set("о777тв198")
    pump(app.root, 1.0)
    assert app.preview_label.cget("text") == ""


def test_preview_works_without_any_template_file(app, tmp_path, monkeypatch):
    """Бланк строится кодом: предпросмотр обязан работать без template.png."""
    from getpass_core import config, render
    monkeypatch.setattr(config, "TEMPLATE_FILE", str(tmp_path / "нет.png"))
    render.reset_template_cache()
    app.p1.plate_var.set("о777тв198")
    pump(app.root, 1.2)
    assert app.preview_label.cget("text") == ""
    assert app.preview_label.cget("image") != ""
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


def test_badge_role_autocompletes_from_journal(app):
    """Должность в бейдже — свободный текст, но должна предлагать варианты
    из уже выданных бейджей, а не заставлять вводить одно и то же заново."""
    from getpass_core.storage import BADGE_JOURNAL
    BADGE_JOURNAL.append_many([{"tab_num": "00099", "fio": "Тестов Т.Т.", "role": "Слесарь"}])
    app.notebook.select(1)
    app.root.update()
    app.badge.role.widget.delete(0, tkinter.END)
    app.badge.role.widget.insert(0, "слес")
    app.badge.role._on_key(types.SimpleNamespace(keysym="e"))
    app.root.update()
    assert "Слесарь" in app.badge.role._listbox.get(0, tkinter.END)


def test_empty_plate_is_flagged_invalid_before_print(app, monkeypatch):
    """Регрессия: validate_required() существовал, но никогда не вызывался
    перед печатью — поле не подсвечивалось, хотя предупреждение появлялось."""
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    app.notebook.select(0)
    app.p1.plate_var.set("")
    app.root.update()
    assert app.build_documents() is None
    assert "invalid" in app.p1.plate.widget.state()


def test_back_side_checkbox_controls_build_documents(app):
    """Чекбокс «Печатать оборот» должен управлять пятым элементом
    build_documents() — по умолчанию оборота нет, при включении он того
    же размера, что и лицевая сторона."""
    app.notebook.select(0)
    app.print_mode.set("a5")
    app.p1.plate_var.set("о777тв198")
    app.root.update()

    app.print_back_var.set(False)
    document, back_document, prefix, records, next_num = app.build_documents()
    assert back_document is None

    app.print_back_var.set(True)
    document, back_document, prefix, records, next_num = app.build_documents()
    assert back_document is not None
    assert back_document.size == document.size


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


def test_paned_width_is_captured_on_close(app, monkeypatch):
    """Регрессия: ширина левой панели никогда не сохранялась — окно всегда
    открывалось с шириной панелей по умолчанию, даже если пользователь
    подвинул разделитель."""
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askokcancel", lambda *a, **k: True)
    app.root.update()
    app.on_closing()
    from getpass_core import config
    assert config.load_settings()["pass_paned_width"] > 0


def test_window_geometry_and_active_tab_persist_across_restart(app, monkeypatch):
    """Регрессия: размер окна и выбранная вкладка не запоминались — каждый
    перезапуск начинался с окна и вкладки по умолчанию."""
    from tkinter import messagebox

    from getpass_ui.app import App
    monkeypatch.setattr(messagebox, "askokcancel", lambda *a, **k: True)
    app.root.geometry("1200x800")
    app.root.update()
    app.notebook.select(1)
    app.root.update()
    app.on_closing()

    second = App()
    try:
        second.root.update()
        assert second.notebook.index(second.notebook.select()) == 1
        width, height = (int(v) for v in second.root.geometry().split("+")[0].split("x"))
        assert (width, height) == (1200, 800)
    finally:
        second.root.destroy()


def _really_visible(widget, min_w=40, min_h=12):
    """Виден ли виджет фактически.

    Проверять winfo_ismapped() у самого поля недостаточно: Tk сообщает 1 и
    тогда, когда родительский холст схлопнут в 1x1 и не отображён. Нужно
    пройти всю цепочку предков.
    """
    node = widget
    while node is not None:
        if not node.winfo_ismapped():
            return False, f"предок {node.winfo_class()} не отображён"
        if node.winfo_width() <= 1 or node.winfo_height() <= 1:
            return False, (f"предок {node.winfo_class()} схлопнут в "
                           f"{node.winfo_width()}x{node.winfo_height()}")
        node = node.master
    if widget.winfo_width() < min_w or widget.winfo_height() < min_h:
        return False, f"размер {widget.winfo_width()}x{widget.winfo_height()}"
    return True, "ок"


@pytest.mark.parametrize("geometry", ["1500x920", "1080x720"])
def test_pass_tab_input_fields_are_visible(app, geometry):
    """Регрессия: прокручиваемая область не упаковывалась, и вся форма была невидима."""
    app.root.geometry(geometry)
    app.notebook.select(0)
    pump(app.root, 1.0)
    fields = {
        "Номер бланка": app.p1.num, "Госномер": app.p1.plate, "Марка": app.p1.brand,
        "Модель": app.p1.model, "Вид": app.p1.type, "Цвет": app.p1.color,
        "Должность водителя": app.p1.d_pos, "ФИО водителя": app.p1.d_fio,
        "Телефон водителя": app.p1.d_phone, "Зона допуска": app.p1.territory,
        "Дата выдачи": app.entry_issue, "Действителен до": app.entry_valid,
        "Должность ОТБ": app.entry_otb_post, "ФИО ОТБ": app.entry_otb_name,
    }
    hidden = {name: _really_visible(w)[1] for name, w in fields.items()
              if not _really_visible(w)[0]}
    assert not hidden, f"невидимые поля: {hidden}"


def test_badge_tab_input_fields_are_visible(app):
    app.root.geometry("1500x920")
    app.notebook.select(1)
    pump(app.root, 1.0)
    b = app.badge
    fields = {
        "Подразделение": b.park, "Табельный номер": b.tab_num, "Должность": b.role,
        "Фамилия": b.sur_field, "Имя": b.nam_field, "Отчество": b.pat_field,
        "Телефон": b.phone, "Выдан": b.issue, "До": b.valid,
    }
    hidden = {name: _really_visible(w)[1] for name, w in fields.items()
              if not _really_visible(w)[0]}
    assert not hidden, f"невидимые поля: {hidden}"


def test_form_stretches_to_panel_width(app):
    """Внутренняя рамка должна тянуться по ширине холста, иначе поля схлопываются."""
    app.notebook.select(0)
    app.root.geometry("1500x920")
    pump(app.root, 1.0)
    assert app.p1.brand.winfo_width() > 150, "поле «Марка» не растянулось"
    assert app.p1.plate.winfo_width() > 300, "поле госномера не растянулось"


def test_unavailable_brand_font_falls_back(app, monkeypatch):
    """Если Tk не видит зарегистрированный брендбук-шрифт — откат на Segoe UI."""
    from getpass_core import fonts
    monkeypatch.setattr(fonts, "UI_FAMILY", "Шрифт Которого Нет")
    assert fonts.verify_ui_family(app.root) == "Segoe UI"


def test_export_button_is_present(app):
    """Кнопка выгрузки таблицы должна быть на вкладке."""
    def button_texts(widget, found=None):
        found = [] if found is None else found
        for child in widget.winfo_children():
            try:
                if child.winfo_class() in ("Button", "TButton"):
                    found.append(child.cget("text"))
            except Exception:
                pass
            button_texts(child, found)
        return found

    app.notebook.select(0)
    pump(app.root, 0.4)
    texts = " | ".join(button_texts(app.root))
    assert "Выгрузить таблицу" in texts
    assert "Внести в базу" not in texts


def test_crop_window_fits_small_screen(app, monkeypatch):
    """Регрессия: окно было жёстко 760x920 и кнопки уезжали под панель задач."""
    from PIL import Image

    from getpass_ui.crop_window import CropWindow
    monkeypatch.setattr(app.root, "winfo_screenwidth", lambda: 1366)
    monkeypatch.setattr(app.root, "winfo_screenheight", lambda: 768)
    window = CropWindow(app.root, Image.new("RGB", (1200, 1600), "#888"), lambda *a: None,
                        app.theme)
    pump(app.root, 0.5)
    geometry = window.win.geometry().split("+")[0]
    width, height = (int(v) for v in geometry.split("x"))
    assert height <= 768 - 40, f"окно {height} px выше рабочей области экрана"
    for button in window.btn_bar.winfo_children():
        ok, info = _really_visible(button, min_w=60, min_h=20)
        assert ok, f"кнопка окна кадрирования не видна: {info}"
    window.win.destroy()


def test_window_geometry_respects_screen(app):
    """Главное окно не должно быть больше экрана."""
    app.root.update()
    geometry = app.root.geometry().split("+")[0]
    width, height = (int(v) for v in geometry.split("x"))
    assert width <= app.root.winfo_screenwidth()
    assert height <= app.root.winfo_screenheight()
