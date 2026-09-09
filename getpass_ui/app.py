"""Главное окно приложения."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import getpass_core
from getpass_core import blacklist
from getpass_core import config, printing
from getpass_core.domain import (add_months_safe, add_years_safe, format_date,
                                 next_number, parse_date)
from getpass_core.dpi import (apply_scaling, enable_dpi_awareness, fit_to_screen,
                              scaled)
from getpass_core.fonts import fonts_are_missing, setup_ui_font, verify_ui_family
from getpass_core.registry import BADGE_REGISTRY, PASS_REGISTRY, save_registry_pdf
from getpass_core import render as R
from getpass_core.storage import (BADGE_JOURNAL, PASS_JOURNAL, FileBusy,
                                  export_journal, known_car_brands,
                                  update_cars_cache)

from . import batch as B
from .badge_tab import BadgePanel
from .components import Field, brand_logo, section_title
from .journal import open_journal_window
from .pass_tab import TERRITORIES, PassForm
from .theme import Card, Theme
from .tokens import RADIUS
from .widgets import Debouncer, ProgressDialog, make_scrollable


class App:
    """Владеет главным окном и состоянием."""

    def __init__(self):
        setup_ui_font()
        self.settings = config.load_settings()
        config.harden_data_dir()

        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("СПб ГУП «Горэлектротранс» — Система выпуска пропусков и бейджей")

        self.scale = apply_scaling(self.root)
        default_w, default_h = scaled(1500, self.scale), scaled(920, self.scale)
        saved_w, saved_h = self._parse_geometry(self.settings.get("window_geometry", ""))
        win_w, win_h = fit_to_screen(self.root, saved_w or default_w, saved_h or default_h)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(min(win_w, scaled(1000, self.scale)),
                          min(win_h, scaled(660, self.scale)))
        if os.path.exists(config.ICON_FILE):
            try:
                self.root.iconbitmap(config.ICON_FILE)
            except Exception:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        palette = self.settings.get("theme", "light")
        self.theme = Theme(self.root, palette, self.scale)
        verify_ui_family(self.root)
        self.theme.apply_window(self.root)

        self._build_header()
        self._build_system_bar()

        self.main_frame = tk.Frame(self.root, bg=self.theme.c("ground"))
        self.main_frame.pack(fill="both", expand=True, padx=self.theme.sp(3),
                             pady=(0, self.theme.sp(3)))
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.preview = Debouncer(self.root, self._render_preview, 150)
        self._build_pass_tab()
        self.badge = BadgePanel(self.notebook, self.settings, self.root, self.theme)
        self.badge.bind_app(self)

        self._bind_hotkeys()
        self.root.bind_all("<MouseWheel>", self._global_mousewheel)
        self.update_tab_states()
        self.root.after(200, self._startup_checks)
        self.root.after(250, self._initial_previews)
        active_tab = self.settings.get("active_tab", 0)
        if active_tab in (0, 1):
            try:
                self.notebook.select(active_tab)
            except Exception:
                pass
        if self.notebook.index(self.notebook.select()) == 0:
            self.p1.plate.focus()

    @staticmethod
    def _parse_geometry(spec: str) -> tuple[int, int]:
        try:
            width, _, height = spec.partition("x")
            return int(width), int(height)
        except (ValueError, AttributeError):
            return 0, 0

    def _zones_source(self):
        seen = list(TERRITORIES)
        for z in PASS_JOURNAL.distinct("zone"):
            if z not in seen:
                seen.append(z)
        return seen

    def _build_header(self):
        th = self.theme
        header = tk.Frame(self.root, bg=th.c("primary"), height=th.px(72))
        header.pack(fill="x")
        header.pack_propagate(False)

        logo = brand_logo(th, 148, knockout=False)
        if logo is not None:
            plate = Card(header, th, radius=RADIUS["chip"], pad=2, fill="#FFFFFF")
            plate.configure(width=logo.width() + 2 * plate._pad,
                            height=logo.height() + 2 * plate._pad)
            plate.pack(side="left", padx=th.sp(5), pady=th.sp(3))
            lbl = tk.Label(plate.body, image=logo, bg="#FFFFFF")
            lbl.image = logo
            lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            tk.Label(header, text="ГЭТ", font=th.font("display"), bg=th.c("primary"),
                     fg=th.c("on_primary")).pack(side="left", padx=th.sp(5))

        text_box = tk.Frame(header, bg=th.c("primary"))
        text_box.pack(side="left", pady=th.sp(3))
        tk.Label(text_box, text="Система выпуска пропусков", font=th.font("title"),
                 bg=th.c("primary"), fg=th.c("on_primary")).pack(anchor="w")
        tk.Label(text_box, text="СПб ГУП «Горэлектротранс»", font=th.font("caption"),
                 bg=th.c("primary"), fg=th.c("accent")).pack(anchor="w")

    def _build_system_bar(self):
        th = self.theme
        bar = tk.Frame(self.root, bg=th.c("ground"))
        bar.pack(fill="x", padx=th.sp(3), pady=th.sp(3))
        tk.Label(bar, text="Принтер", bg=th.c("ground"), fg=th.c("ink_muted"),
                 font=th.font("caption")).pack(side="left", padx=(0, th.sp(2)))
        self.printer_var = tk.StringVar(value=self.settings.get("last_printer",
                                                                printing.DEFAULT_PRINTER))
        self.printer_cb = ttk.Combobox(bar, textvariable=self.printer_var,
                                       state="readonly", width=34,
                                       style="Field.TCombobox")
        self.printer_cb.pack(side="left", padx=(0, th.sp(4)))
        self.printer_cb["values"] = [self.printer_var.get()]
        self.printer_cb.bind("<<ComboboxSelected>>", lambda e: self.save_settings())

        self._printer_result = queue.Queue(maxsize=1)
        threading.Thread(target=self._load_printers, daemon=True).start()
        self.root.after(300, self._poll_printers)

        ttk.Button(bar, text="Очистить форму", command=self.clear_current_form,
                   style="Danger.TButton").pack(side="right", padx=(th.sp(2), 0))
        ttk.Button(bar, text="Восстановить", command=self.restore_database,
                   style="Ghost.TButton").pack(side="right", padx=(th.sp(2), 0))
        ttk.Button(bar, text="Бэкап", command=self.backup_database,
                   style="Ghost.TButton").pack(side="right", padx=(th.sp(2), 0))
        ttk.Button(bar, text="Черный список", command=self.open_blacklist,
               style="Danger.TButton").pack(side="right", padx=(th.sp(2), 0))
        ttk.Button(bar, text="Тёмная тема" if not th.is_dark else "Светлая тема",
                   command=self.toggle_theme, style="Ghost.TButton"
                   ).pack(side="right")

    def toggle_theme(self):
        current = self.settings.get("theme", "light")
        self.settings["theme"] = "dark" if current == "light" else "light"
        config.save_settings({"theme": self.settings["theme"]})
        if messagebox.askyesno(
                "Смена темы",
                "Тема изменена. Чтобы применить её ко всем окнам,\n"
                "программу нужно перезапустить.\n\nЗакрыть программу сейчас?"):
            self.preview.cancel()
            self.badge.preview.cancel()
            self.root.destroy()

    def open_blacklist(self):
        win = self.theme.toplevel(self.root, "Черный список", resizable=(True, True))
        win.geometry("760x520")
        body = tk.Frame(win, bg=self.theme.c("ground"))
        body.pack(fill="both", expand=True, padx=self.theme.sp(4), pady=self.theme.sp(4))
        tk.Label(body, text="Реестр нарушителей", bg=self.theme.c("ground"),
                 fg=self.theme.c("ink"), font=self.theme.font("title")).pack(anchor="w")
        columns = ("plate", "fio", "incident", "created_at")
        tree = ttk.Treeview(body, columns=columns, show="headings", height=12)
        for key, title, width in (("plate", "Госномер", 130), ("fio", "ФИО", 190),
                                  ("incident", "Инцидент", 300), ("created_at", "Дата", 120)):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True, pady=(self.theme.sp(3), self.theme.sp(3)))

        fields = tk.Frame(body, bg=self.theme.c("ground"))
        fields.pack(fill="x")
        plate = Field(fields, self.theme, "Госномер")
        plate.pack(side="left", fill="x", expand=True, padx=(0, self.theme.sp(2)))
        fio = Field(fields, self.theme, "ФИО")
        fio.pack(side="left", fill="x", expand=True, padx=(0, self.theme.sp(2)))
        incident = Field(fields, self.theme, "Описание нарушения")
        incident.pack(side="left", fill="x", expand=True)

        def refresh():
            tree.delete(*tree.get_children())
            for item in blacklist.load():
                tree.insert("", "end", iid=item.get("id"), values=(
                    item.get("plate", ""), item.get("fio", ""),
                    item.get("incident", ""), item.get("created_at", "")))

        def add_entry():
            if not plate.get().strip() and not fio.get().strip():
                messagebox.showwarning("Недостаточно данных", "Укажите госномер или ФИО.", parent=win)
                return
            if not incident.get().strip():
                messagebox.showwarning("Нет описания", "Опишите прошлый инцидент.", parent=win)
                return
            blacklist.add(plate.get(), fio.get(), incident.get())
            plate.delete(0, tk.END)
            fio.delete(0, tk.END)
            incident.delete(0, tk.END)
            refresh()

        def remove_entry():
            selected = tree.selection()
            if selected and messagebox.askyesno("Удалить запись", "Удалить выбранную запись?", parent=win):
                blacklist.remove(selected[0])
                refresh()

        buttons = tk.Frame(body, bg=self.theme.c("ground"))
        buttons.pack(fill="x", pady=(self.theme.sp(3), 0))
        ttk.Button(buttons, text="Добавить", command=add_entry,
                   style="Primary.TButton").pack(side="left")
        ttk.Button(buttons, text="Удалить выбранную", command=remove_entry,
                   style="Danger.TButton").pack(side="left", padx=(self.theme.sp(2), 0))
        refresh()

    def _load_printers(self):
        try:
            names = printing.get_available_printers()
        except Exception:
            names = [printing.DEFAULT_PRINTER]
        try:
            self._printer_result.put_nowait(names)
        except Exception:
            pass

    def _poll_printers(self):
        try:
            names = self._printer_result.get_nowait()
        except queue.Empty:
            self.root.after(300, self._poll_printers)
            return
        except Exception:
            return
        try:
            self.printer_cb["values"] = names
            if self.printer_var.get() not in names:
                self.printer_var.set(printing.DEFAULT_PRINTER)
        except Exception:
            pass

    def _build_pass_tab(self):
        th = self.theme
        container = tk.Frame(self.notebook, bg=th.c("ground"))
        self.notebook.add(container, text="  Пропуск на ТС  ")

        btn_bar = tk.Frame(container, bg=th.c("ground"))
        btn_bar.pack(side="bottom", fill="x", pady=(th.sp(3), 0))
        row1 = tk.Frame(btn_bar, bg=th.c("ground"))
        row1.pack(fill="x", pady=(0, th.sp(2)))
        ttk.Button(row1, text="Сохранить PDF   (Ctrl+S)", command=self.generate_pass,
                   style="Primary.TButton").pack(side="left", fill="x", expand=True,
                                                 padx=(0, th.sp(2)))
        ttk.Button(row1, text="Напечатать сразу   (Ctrl+P)", command=self.direct_print_pass,
                   style="Accent.TButton").pack(side="right", fill="x", expand=True)
        row2 = tk.Frame(btn_bar, bg=th.c("ground"))
        row2.pack(fill="x")
        ttk.Button(row2, text="Массовая печать", command=self.open_batch_passes,
                   style="Ghost.TButton").pack(side="left", padx=(0, th.sp(2)))
        ttk.Button(row2, text="Реестр ТС для печати", command=self.registry_passes,
                   style="Ghost.TButton").pack(side="left", padx=(0, th.sp(2)))
        ttk.Button(row2, text="Выгрузить таблицу", command=self.export_pass_journal,
                   style="Ghost.TButton").pack(side="left")
        ttk.Button(row2, text="Журнал ТС", command=self.open_pass_journal,
                   style="Ghost.TButton").pack(side="right")

        self.pass_paned = tk.PanedWindow(container, orient="horizontal", bg=th.c("ground"),
                                         sashwidth=th.px(6), sashrelief="flat", borderwidth=0)
        paned = self.pass_paned
        paned.pack(side="top", fill="both", expand=True)
        left = tk.Frame(paned, bg=th.c("ground"))
        left_width = int(self.settings.get("pass_paned_width") or 0) or scaled(700, self.scale)
        paned.add(left, minsize=scaled(440, self.scale), width=left_width)
        _, _, inner = make_scrollable(left, th.c("ground"))

        car_card = Card(inner, th)
        car_card.pack(fill="x", pady=(0, th.sp(3)))
        cb = car_card.body
        section_title(cb, th, "Транспортное средство").pack(anchor="w",
                                                             pady=(0, th.sp(3)))
        self.pass_notebook = ttk.Notebook(cb, style="Inner.TNotebook")
        self.pass_notebook.pack(fill="x")
        territory = self.settings.get("territory", "")
        self.p1 = PassForm(self.pass_notebook, th, self.settings["last_pass_num"],
                           self.preview.schedule, default_territory=territory,
                           zones_source=self._zones_source,
                           makes_source=known_car_brands)
        self.pass_notebook.add(self.p1.frame, text="Пропуск №1 (верхний)")
        self.p2 = PassForm(self.pass_notebook, th,
                           next_number(self.settings["last_pass_num"]).value,
                           self.preview.schedule, is_second=True,
                           default_territory="", peer_getter=self.p1.get_number,
                           zones_source=self._zones_source,
                           makes_source=known_car_brands)
        self.pass_notebook.add(self.p2.frame, text="Пропуск №2 (нижний)")
        car_card.fit()

        self._build_common_box(inner)
        self._build_format_box(inner)
        self._build_preview_panel(paned)

    def _build_common_box(self, parent):
        th = self.theme
        card = Card(parent, th)
        card.pack(fill="x", pady=(0, th.sp(3)))
        b = card.body
        section_title(b, th, "Реквизиты и ответственные лица").pack(
            anchor="w", pady=(0, th.sp(3)))
        row = tk.Frame(b, bg=th.c("surface"))
        row.pack(fill="x")
        self.entry_issue = Field(row, th, "Дата выдачи", width=12, required=True)
        self.entry_issue.pack(side="left", padx=(0, th.sp(3)))
        self.entry_issue.set(self.settings["issue_date"])
        self.entry_valid = Field(row, th, "Действителен до", width=12, required=True)
        self.entry_valid.pack(side="left")
        self.entry_valid.set(self.settings["valid_until"])

        self.is_temp_var = tk.BooleanVar(value=self.settings.get("is_temporary_car", False))
        th.check(b, "Временный пропуск на ТС (не более 3 месяцев)",
                 self.is_temp_var, command=self.on_toggle_temp,
                 style="Warning.TCheckbutton").pack(anchor="w", pady=(th.sp(3), 0))

        row2 = tk.Frame(b, bg=th.c("surface"))
        row2.pack(fill="x", pady=(th.sp(3), 0))
        self.entry_otb_post = Field(row2, th, "Должность ОТБ")
        self.entry_otb_post.pack(side="left", fill="x", expand=True, padx=(0, th.sp(3)))
        self.entry_otb_post.set(self.settings.get("otb_post", ""))
        self.entry_otb_name = Field(row2, th, "ФИО ОТБ", width=18)
        self.entry_otb_name.pack(side="left")
        self.entry_otb_name.set(self.settings.get("otb_name", ""))
        for widget in (self.entry_issue, self.entry_valid,
                       self.entry_otb_post, self.entry_otb_name):
            widget.bind("<KeyRelease>", self.preview.schedule, add="+")
        card.fit()

    def _build_format_box(self, parent):
        th = self.theme
        card = Card(parent, th)
        card.pack(fill="x")
        b = card.body
        section_title(b, th, "Формат формирования").pack(anchor="w", pady=(0, th.sp(2)))
        self.print_mode = tk.StringVar(value=self.settings["print_mode"])
        th.radio(b, "Лист А4 — два пропуска (№1 сверху, №2 снизу)", self.print_mode,
                 "a4", command=self.update_tab_states).pack(anchor="w")
        th.radio(b, "Лист А5 — один пропуск (вкладка №2 блокируется)", self.print_mode,
                 "a5", command=self.update_tab_states).pack(anchor="w")
        self.print_back_var = tk.BooleanVar(
            value=self.settings.get("print_pass_back", False))
        th.check(b, "Печатать оборот (правила пользования пропуском)",
                 self.print_back_var).pack(anchor="w", pady=(th.sp(2), 0))
        card.fit()

    def _build_preview_panel(self, paned):
        th = self.theme
        wrapper = tk.Frame(paned, bg=th.c("ground"))
        paned.add(wrapper, minsize=scaled(340, self.scale), width=scaled(520, self.scale))
        self.preview_panel = Card(wrapper, th)
        self.preview_panel.pack(fill="both", expand=True)
        b = self.preview_panel.body
        head = tk.Frame(b, bg=th.c("surface"))
        head.pack(fill="x", pady=(0, th.sp(3)))
        section_title(head, th, "Предпросмотр бланка").pack(side="left")
        self.preview_target = tk.StringVar(value=self.settings.get("auto_preview_target", "1"))
        switch = tk.Frame(head, bg=th.c("surface"))
        switch.pack(side="right")
        th.radio(switch, "№1", self.preview_target, "1",
                 command=self.preview.schedule).pack(side="left")
        th.radio(switch, "№2", self.preview_target, "2",
                 command=self.preview.schedule).pack(side="left", padx=(th.sp(2), 0))
        self.preview_label = tk.Label(b, bg=th.c("surface"), fg=th.c("ink_faint"),
                                      font=th.font("body"),
                                      text="Заполните поля —\nпредпросмотр появится здесь")
        self.preview_label.pack(fill="both", expand=True)
        tk.Label(b, text="Макет обновляется автоматически при вводе данных.",
                 bg=th.c("surface"), fg=th.c("ink_faint"), font=th.font("caption")
                 ).pack(pady=(th.sp(2), 0))
        self.preview_panel.bind("<Configure>",
                                lambda e: self.preview.schedule(delay=140))

    def _initial_previews(self):
        self.badge.preview.schedule(delay=10)
        self.preview.schedule(delay=20)

    def _render_preview(self):
        try:
            if not R.template_exists():
                self.preview_label.config(image="",
                                          text="Нет файла template.png\nв папке программы")
                return
            form = self.p2 if self.preview_target.get() == "2" else self.p1
            img = R.render_pass(form.data(placeholder=True), self.common_data(preview=True))
            panel_w = self.preview_panel.winfo_width() or 480
            panel_h = self.preview_panel.winfo_height() or 460
            max_w = max(140, panel_w - 34)
            max_h = max(120, panel_h - 140)
            ratio = img.height / img.width
            w = min(max_w, 1600)
            h = int(w * ratio)
            if h > max_h:
                h, w = max_h, int(max_h / ratio)
            thumb = img.resize((max(80, w), max(60, h)), R.Image.Resampling.LANCZOS)
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(thumb)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass

    def common_data(self, preview=False):
        issue = parse_date(self.entry_issue.get())
        if issue is None:
            issue = datetime.now()
        valid = parse_date(self.entry_valid.get())
        if valid is None:
            valid = add_years_safe(issue, 1)
        return {"issue_date": format_date(issue), "valid_until": format_date(valid),
                "otb_post": self.entry_otb_post.get().strip(),
                "otb_name": self.entry_otb_name.get().strip(),
                "is_temporary": self.is_temp_var.get()}

    def on_toggle_temp(self):
        if self.is_temp_var.get():
            issue = parse_date(self.entry_issue.get())
            if issue is None:
                messagebox.showwarning("Некорректная дата",
                                       "Поле «Дата выдачи»: укажите дату в формате ДД.ММ.ГГГГ.")
            else:
                self.entry_valid.delete(0, tk.END)
                self.entry_valid.insert(0, format_date(add_months_safe(issue, 3)))
        self.preview.schedule()

    def update_tab_states(self):
        if self.print_mode.get() == "a5":
            self.pass_notebook.select(self.p1.frame)
            self.pass_notebook.tab(1, state="disabled")
        else:
            self.pass_notebook.tab(1, state="normal")

    def collect_settings(self):
        try:
            pass_paned_width = self.pass_paned.sash_coord(0)[0]
        except Exception:
            pass_paned_width = self.settings.get("pass_paned_width", 0)
        return {
            "last_pass_num": self.p1.get_number() or self.settings.get("last_pass_num"),
            "territory": self.p1.territory.get().strip() or self.settings.get("territory"),
            "otb_post": self.entry_otb_post.get().strip(),
            "otb_name": self.entry_otb_name.get().strip(),
            "valid_until": self.entry_valid.get().strip() or self.settings.get("valid_until"),
            "is_temporary_car": self.is_temp_var.get(),
            "print_mode": self.print_mode.get(),
            "print_pass_back": self.print_back_var.get(),
            "last_printer": self.printer_var.get(),
            "auto_preview_target": self.preview_target.get(),
            "window_geometry": f"{self.root.winfo_width()}x{self.root.winfo_height()}",
            "active_tab": self.notebook.index(self.notebook.select()),
            "pass_paned_width": pass_paned_width,
            **self.badge.collect_settings(),
        }

    def save_settings(self):
        values = self.collect_settings()
        self.settings.update(values)
        config.save_settings(values)

    def on_closing(self):
        if messagebox.askokcancel("Выход", "Закрыть программу?\n\n"
                                           "Введённые реквизиты будут сохранены."):
            self.save_settings()
            self.preview.cancel()
            self.badge.preview.cancel()
            threading.Thread(target=self._rotate_backups, daemon=False).start()
            self.root.destroy()

    @staticmethod
    def _rotate_backups():
        try:
            getpass_core.backup.rotate_backups(14)
        except Exception:
            pass

    def _startup_checks(self):
        problems = []
        if not R.template_exists():
            problems.append(f"• Нет файла бланка template.png в папке:\n    {config.SCRIPT_DIR}\n"
                            "  Пропуска будут печататься на белом фоне.")
        if fonts_are_missing():
            problems.append("• Не найдены шрифты бланков — текст будет отрисован\n"
                            "  системным шрифтом без соблюдения кегля.")
        if problems:
            messagebox.showwarning("Проверка окружения", "\n\n".join(problems))

    def _bind_hotkeys(self):
        self.root.bind("<Control-KeyPress>", self._on_ctrl)

    def _on_ctrl(self, event):
        if event.widget.winfo_toplevel() is not self.root:
            return None
        on_pass = self.notebook.index(self.notebook.select()) == 0
        if event.keysym in ("s", "S", "Cyrillic_yeru", "Cyrillic_YERU") or event.char == "\x13":
            (self.generate_pass if on_pass else self.badge.generate_pdf)()
            return "break"
        if event.keysym in ("p", "P", "Cyrillic_ze", "Cyrillic_ZE") or event.char == "\x10":
            (self.direct_print_pass if on_pass else self.badge.direct_print)()
            return "break"
        return None

    def _global_mousewheel(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None
        steps = int(-1 * (event.delta / 120))
        while widget is not None:
            if isinstance(widget, tk.Canvas):
                try:
                    widget.yview_scroll(steps, "units")
                    return "break"
                except Exception:
                    return None
            widget = getattr(widget, "master", None)
        return None

    def clear_current_form(self):
        if self.notebook.index(self.notebook.select()) == 0:
            if messagebox.askyesno("Очистить форму", "Очистить поля пропусков на ТС (№1 и №2)?"):
                self.clear_pass_forms()
                self.p1.plate.focus()
        else:
            self.badge.clear_form(confirm=True)

    def clear_pass_forms(self):
        territory = self.settings.get("territory", "")
        self.p1.clear(territory)
        self.p2.clear(territory)
        self.entry_issue.reset_validation()
        self.entry_valid.reset_validation()
        self.preview.schedule()

    def _validate_pass_dates(self):
        raw_issue = self.entry_issue.get()
        issue = parse_date(raw_issue)
        if issue is None:
            self.entry_issue.widget.state(["invalid"])
            messagebox.showwarning("Некорректная дата выдачи",
                                   f"Поле «Дата выдачи»: «{raw_issue}»\nФормат: ДД.ММ.ГГГГ")
            self.entry_issue.focus()
            return None, None
        self.entry_issue.reset_validation()

        valid = parse_date(self.entry_valid.get())
        if valid is None:
            self.entry_valid.widget.state(["invalid"])
            messagebox.showwarning("Укажите срок",
                                   "Заполните поле «Действителен до» (ДД.ММ.ГГГГ).")
            self.entry_valid.focus()
            return None, None
        self.entry_valid.reset_validation()

        if valid < issue:
            messagebox.showwarning("Ошибка дат",
                                   "Дата окончания не может быть раньше даты выдачи!")
            return None, None
        if self.is_temp_var.get():
            limit = add_months_safe(issue, 3)
            if valid > limit:
                messagebox.showwarning(
                    "Превышен срок",
                    "Временный пропуск выдается не более чем на 3 месяца!\n\n"
                    f"Максимальная дата: {format_date(limit)}")
                return None, None
        return issue, valid

    def _check_duplicates(self, forms):
        for form in forms:
            data = form.data()
            incidents = blacklist.find(data["plate"], data["d_fio"])
            if incidents:
                details = "\n".join(
                    f"  • {item.get('created_at', '')}: {item.get('incident', '')}"
                    for item in incidents[:5])
                messagebox.showwarning(
                    "ВНИМАНИЕ: черный список",
                    f"Найдено совпадение по госномеру или ФИО.\n\n{details}",
                    parent=self.root)
                if not messagebox.askyesno(
                        "ВНИМАНИЕ: запись в черном списке",
                        f"Совпадение по госномеру или ФИО:\n"
                        f"{data['plate']} / {data['d_fio'] or 'ФИО не указано'}\n\n"
                        f"Прошлые инциденты:\n{details}\n\n"
                        "Продолжить выдачу пропуска?"):
                    return False
                if not self.settings.get("warn_duplicates", True):
                    continue
            if not data["plate"]:
                continue
            dups = PASS_JOURNAL.find_duplicates(data["plate"])
            if not dups:
                continue
            lines = "\n".join(
                f"  • №{d.get('num','')} — до {d.get('valid_until','')} "
                f"({d.get('driver','') or 'водитель не указан'})" for d in dups[:5])
            more = f"\n  ... и ещё {len(dups) - 5}" if len(dups) > 5 else ""
            if not messagebox.askyesno(
                    "Уже есть действующий пропуск",
                    f"На госномер {data['plate']} уже выдан действующий пропуск:\n\n"
                    f"{lines}{more}\n\nВыдать ещё один?"):
                return False
        return True

    def build_documents(self):
        issue, valid = self._validate_pass_dates()
        if issue is None:
            return None
        if not self.p1.validate_required() or self.p1.is_empty():
            messagebox.showwarning("Внимание",
                                   "Заполните «Гос. номер автомобиля» во вкладке «Пропуск №1»!")
            self.notebook.select(0)
            self.pass_notebook.select(self.p1.frame)
            self.p1.plate.focus()
            return None

        common = {"issue_date": format_date(issue), "valid_until": format_date(valid),
                  "otb_post": self.entry_otb_post.get().strip(),
                  "otb_name": self.entry_otb_name.get().strip(),
                  "is_temporary": self.is_temp_var.get()}
        mode = self.print_mode.get()
        forms = [self.p1]
        if mode == "a4" and not self.p2.is_empty():
            forms.append(self.p2)
        if not self._check_duplicates(forms):
            return None

        p1 = self.p1.data()
        img1 = R.render_pass(p1, common)
        records = [dict(p1, **common)]
        img2 = None

        if mode == "a4":
            if self.p2.is_empty():
                answer = messagebox.askyesnocancel(
                    "Второй пропуск не заполнен",
                    "Выбран лист А4, но во вкладке «Пропуск №2» нет госномера.\n\n"
                    "• «Да» — напечатать 2 копии Пропуска №1.\n"
                    "• «Нет» — напечатать 1 пропуск (А5).\n"
                    "• «Отмена» — вернуться к заполнению.")
                if answer is None:
                    return None
                if answer:
                    img2 = img1
                    prefix = f"Пропуск_{p1['num']}_2копии_А4"
                else:
                    mode = "a5"
                    prefix = f"Пропуск_{p1['num']}_А5"
                source_num = p1["num"]
            else:
                p2 = self.p2.data()
                img2 = R.render_pass(p2, common)
                records.append(dict(p2, **common))
                prefix = f"Пропуска_{p1['num']}_{p2['num']}"
                source_num = p2["num"]
        else:
            prefix = f"Пропуск_{p1['num']}_А5"
            source_num = p1["num"]

        document = R.build_pass_a4_sheet(img1, img2) if mode == "a4" else img1
        back_document = None
        if self.print_back_var.get():
            back = R.render_pass_back()
            back_document = R.build_pass_a4_sheet(back, back) if mode == "a4" else back
        return document, back_document, prefix, records, next_number(source_num)

    def _finish_pass(self, records, next_num):
        for rec in records:
            rec["zone"] = rec.get("territory") or "Основная (Без зоны)"
            rec["driver"] = rec.get("driver_full", "")
        try:
            PASS_JOURNAL.append_many(records)
        except FileBusy as exc:
            messagebox.showerror(
                "Журнал не обновлён",
                f"Документ готов, но «{os.path.basename(exc.path)}» открыт "
                "в другой программе.\nЗакройте его — записи в журнал не попали.")
        except Exception as exc:
            messagebox.showerror("Журнал не обновлён", str(exc))
        update_cars_cache(records)

        if next_num.overflowed:
            messagebox.showwarning(
                "Переполнение нумерации",
                f"Следующий номер «{next_num.value}» вышел за разрядность бланка.\n"
                "Проверьте серию и при необходимости задайте номер вручную.")
        self.p1.set_number(next_num.value)
        self.p2.set_number(next_number(next_num.value).value)
        self.save_settings()
        self.clear_pass_forms()

    def generate_pass(self):
        built = self.build_documents()
        if not built:
            return
        document, back_document, prefix, records, next_num = built
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Документ (для печати)", "*.pdf"), ("Изображение JPEG", "*.jpg")],
            initialfile=f"{prefix}.pdf")
        if not path:
            return
        is_pdf = os.path.splitext(path)[1].lower() == ".pdf"
        try:
            if back_document is not None and is_pdf:
                printing.save_pdf_pages([document, back_document], path)
            else:
                printing.save_document(document, path)
                if back_document is not None:
                    messagebox.showinfo(
                        "Оборот не сохранён",
                        "Оборотная сторона поддерживается только при сохранении в PDF.\n"
                        "Сохранена только лицевая сторона.")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{exc}")
            return
        self._finish_pass(records, next_num)
        messagebox.showinfo("Готово",
                            f"Документ сформирован!\nСледующий номер: {next_num.value}")

    def direct_print_pass(self):
        built = self.build_documents()
        if not built:
            return
        document, back_document, prefix, records, next_num = built
        if back_document is not None:
            ok, err = printing.print_pass_two_sided(
                document, back_document, self.printer_var.get(),
                confirm_flip=self._confirm_flip_for_back_side)
        else:
            ok, err = printing.send_image_to_printer(document, self.printer_var.get())
        if ok:
            self._finish_pass(records, next_num)
            messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
            return
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
        try:
            if back_document is not None:
                printing.save_pdf_pages([document, back_document], temp_pdf)
            else:
                printing.save_document(document, temp_pdf)
            os.startfile(temp_pdf)  # noqa: Windows only
            opened = True
        except Exception:
            opened = False
        if messagebox.askyesno(
                "Принтер не ответил",
                f"Не удалось напечатать напрямую.\n{err or ''}\n\n"
                + ("Документ открыт — напечатайте вручную (Ctrl+P).\n\n" if opened else "")
                + "Считать пропуск выданным и записать в журнал?"):
            self._finish_pass(records, next_num)

    def _confirm_flip_for_back_side(self) -> bool:
        return messagebox.askokcancel(
            "Печать оборотной стороны",
            "Лицевая сторона напечатана.\n\n"
            "Переверните лист в лотке принтера и нажмите «ОК», чтобы "
            "напечатать оборот с правилами пользования пропуском.")

    def export_pass_journal(self):
        self._export_journal(PASS_JOURNAL, "Журнал_пропусков_ТС")

    def export_badge_journal(self):
        self._export_journal(BADGE_JOURNAL, "Журнал_работников")

    def _export_journal(self, journal, name):
        if not journal.read():
            messagebox.showinfo("Журнал пуст", "В базе нет записей для выгрузки.")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Таблица Excel", "*.xlsx"), ("CSV (разделитель ;)", "*.csv")],
            initialfile=f"{name}_{today}.xlsx")
        if not path:
            return
        try:
            count = export_journal(journal, path)
        except (PermissionError, FileBusy):
            messagebox.showerror("Файл занят",
                                 "Файл открыт в другой программе. Закройте его и повторите.")
            return
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось выгрузить таблицу:\n{exc}")
            return
        if messagebox.askyesno("Выгружено",
                               f"Записей выгружено: {count}\n{path}\n\nОткрыть файл?"):
            try:
                os.startfile(path)  # noqa: Windows only
            except Exception:
                pass

    def registry_passes(self):
        self._build_registry(PASS_JOURNAL, PASS_REGISTRY, "Реестр_ТС_для_печати")

    def registry_badges(self):
        self._build_registry(BADGE_JOURNAL, BADGE_REGISTRY, "Реестр_работников")

    def _build_registry(self, journal, spec, name):
        all_records = journal.read()
        if not all_records:
            messagebox.showinfo("Реестр пуст", "В базе нет записей.")
            return
        live, _expired, unknown = journal.active(all_records)
        if not live and not unknown:
            messagebox.showinfo("Нет действующих",
                                "Все записи просрочены или аннулированы.")
            return
        if unknown and not messagebox.askyesno(
                "Записи без срока",
                f"У {len(unknown)} записей не указан или испорчен срок действия.\n\n"
                "• «Да» — включить их в реестр отдельным блоком в конце.\n"
                "• «Нет» — не включать."):
            unknown = []
        records = live + unknown
        today = datetime.now().strftime("%d.%m.%Y")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
            initialfile=f"{name}_{today}.pdf")
        if not path:
            return
        try:
            with ProgressDialog(self.root, self.theme, "Формирование реестра",
                                max(1, len(records) // 23 + 1)) as dlg:
                pages = save_registry_pdf(
                    records, spec, len(all_records), path,
                    progress=lambda i, total: dlg.step(i, f"Лист {i} из {total}..."))
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сформировать реестр:\n{exc}")
            return
        if messagebox.askyesno("Готово",
                               f"Реестр сформирован ({len(records)} зап., {pages} л.).\n\n"
                               "Открыть файл?"):
            try:
                os.startfile(path)  # noqa: Windows only
            except Exception:
                pass

    def open_pass_journal(self):
        open_journal_window(self.root, PASS_JOURNAL,
                            "Журнал выданных пропусков ТС — ГЭТ СПб", self.theme)

    def open_badge_journal(self):
        open_journal_window(self.root, BADGE_JOURNAL,
                            "Журнал постоянных пропусков работников — ГЭТ СПб",
                            self.theme)

    def open_batch_passes(self):
        B.open_batch_dialog(
            self.root, self.theme, "Массовая печать пропусков на ТС",
            "1. Скачайте шаблон таблицы и заполните список машин.\n"
            "2. Выберите готовый файл для генерации единого PDF.",
            lambda: B.export_template(B.PASS_TEMPLATE_HEADER, B.PASS_TEMPLATE_SAMPLE,
                                      "Шаблон_массовой_печати_ТС.csv"),
            self.run_batch_passes)

    def run_batch_passes(self):
        issue, valid = self._validate_pass_dates()
        if issue is None:
            return
        _path, rows = B.read_csv_rows("Массовая печать: выберите CSV со списком машин")
        if rows is None:
            return
        common = {"issue_date": format_date(issue), "valid_until": format_date(valid),
                  "otb_post": self.entry_otb_post.get().strip(),
                  "otb_name": self.entry_otb_name.get().strip(),
                  "is_temporary": self.is_temp_var.get()}
        items = B.parse_pass_rows(rows, common)
        if not items:
            messagebox.showwarning("Пусто", "В файле нет записей.")
            return
        records = [dict(it, zone=it.get("territory") or "Основная (Без зоны)",
                        driver=it.get("driver_full", ""))
                   for it in items]
        pages_total = (len(items) + 1) // 2
        if B.run_batch(self.root, self.theme, "Массовая печать ТС", items,
                       lambda: B.pass_pages(items, common), pages_total,
                       PASS_JOURNAL, records,
                       f"Массовая_печать_ТС_{len(items)}шт.pdf"):
            update_cars_cache(items)

    def open_batch_badges(self):
        B.open_batch_dialog(
            self.root, self.theme, "Массовая печать бейджей работников",
            "1. Скачайте шаблон и заполните сотрудников.\n"
            "2. Укажите имена файлов фото (лежат рядом с CSV).\n"
            "3. Выберите файл — бейджи разместятся на А4 (сетка 3×3).",
            lambda: B.export_template(
                B.BADGE_TEMPLATE_HEADER, B.BADGE_TEMPLATE_SAMPLE,
                "Шаблон_массовой_печати_бейджей.csv",
                "\n\nФотографии положите в ту же папку, где лежит таблица."),
            self.run_batch_badges)

    def run_batch_badges(self):
        path, rows = B.read_csv_rows("Массовая печать: выберите CSV со списком сотрудников")
        if rows is None:
            return
        items = B.parse_badge_rows(rows, os.path.dirname(path), self.badge.batch_defaults())
        if not items:
            messagebox.showwarning("Пусто", "В файле нет записей.")
            return
        bad = [it for it in items
               if parse_date(it["issue_date"]) and parse_date(it["valid_until"])
               and parse_date(it["valid_until"]) < parse_date(it["issue_date"])]
        if bad and not messagebox.askyesno(
                "Ошибка в датах",
                f"У {len(bad)} записей дата окончания раньше даты выдачи.\n\nПродолжить?"):
            return
        records = list(items)
        pages_total = (len(items) + 8) // 9
        B.run_batch(self.root, self.theme, "Массовая печать бейджей", items,
                    lambda: B.badge_pages(items), pages_total,
                    BADGE_JOURNAL, records,
                    f"Массовая_печать_бейджей_{len(items)}шт.pdf")

    def backup_database(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", filetypes=[("ZIP Архив", "*.zip")],
            initialfile=f"Backup_GET_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        if not path:
            return
        try:
            count, size = getpass_core.backup.create_backup(path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось создать бэкап: {exc}")
            return
        messagebox.showwarning(
            "Резервная копия создана",
            f"Сохранено файлов: {count} ({size // 1024} КБ)\n{path}\n\n"
            "Архив содержит персональные данные (ФИО, телефоны, госномера,\n"
            "фотографии) и НЕ зашифрован. Храните его на носителе с\n"
            "ограниченным доступом и не пересылайте по открытым каналам.")

    def restore_database(self):
        path = filedialog.askopenfilename(title="Выберите ZIP-архив",
                                          filetypes=[("ZIP Архив", "*.zip")])
        if not path:
            return
        try:
            accepted, skipped = getpass_core.backup.inspect_backup(path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось прочитать архив: {exc}")
            return
        if not accepted:
            messagebox.showwarning("Архив не подходит",
                                   "В архиве нет файлов системы пропусков.")
            return
        note = (f"\n\nБудет пропущено посторонних файлов: {len(skipped)}"
                if skipped else "")
        if not messagebox.askyesno(
                "Восстановление",
                f"Будет восстановлено файлов: {len(accepted)}.\n"
                f"Текущие данные будут перезаписаны.{note}\n\nПродолжить?"):
            return
        try:
            restored, _ = getpass_core.backup.restore_backup(path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось восстановить: {exc}")
            return
        messagebox.showinfo("Успех",
                            f"Восстановлено файлов: {restored}.\nПерезапустите программу.")

    def run(self):
        self.root.mainloop()