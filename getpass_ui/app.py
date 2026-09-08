"""Главное окно приложения."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from getpass_core import backup as backup_mod
from getpass_core import config, printing
from getpass_core.dpi import (apply_scaling, enable_dpi_awareness, fit_to_screen,
                              scaled)
from getpass_core import render as R
from getpass_core.domain import (add_months_safe, add_years_safe, format_date,
                                 next_number, parse_date)
from getpass_core.fonts import (fonts_are_missing, setup_ui_font, ui_family,
                                verify_ui_family)
from getpass_core.registry import BADGE_REGISTRY, PASS_REGISTRY, save_registry_pdf
from getpass_core.storage import (BADGE_JOURNAL, PASS_JOURNAL, FileBusy,
                                  export_journal, update_cars_cache)

from . import batch as B
from .badge_tab import BadgePanel
from .journal import open_journal_window
from .pass_tab import PassForm
from .widgets import (CLR_BG, CLR_CARD, CLR_NAVY, CLR_RED, CLR_TEAL, F,
                      Debouncer, ProgressDialog, make_scrollable, styled_button)


class App:
    """Владеет главным окном и состоянием. Заменяет ~130 глобальных переменных."""

    def __init__(self):
        setup_ui_font()
        self.settings = config.load_settings()
        config.harden_data_dir()

        enable_dpi_awareness()      # на случай запуска App в обход main()
        self.root = tk.Tk()
        self.root.title("СПб ГУП «Горэлектротранс» — Система выпуска пропусков и бейджей")
        # масштаб экрана: на 125/150% интерфейс должен стать крупнее, а не мыльнее
        self.scale = apply_scaling(self.root)
        win_w, win_h = fit_to_screen(self.root, scaled(1500, self.scale),
                                     scaled(920, self.scale))
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(min(win_w, scaled(1000, self.scale)),
                          min(win_h, scaled(660, self.scale)))
        self.root.configure(bg=CLR_BG)
        if os.path.exists(config.ICON_FILE):
            try:
                self.root.iconbitmap(config.ICON_FILE)
            except Exception:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # шрифт проверяем уже после создания root: до него список семейств
        # Tk недоступен
        verify_ui_family(self.root)

        self._apply_style()
        self._build_header()
        self._build_system_bar()

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.preview = Debouncer(self.root, self._render_preview, 150)
        self._build_pass_tab()
        self.badge = BadgePanel(self.notebook, self.settings, self.root, self.scale)
        self.badge.bind_app(self)

        self._bind_hotkeys()
        self.root.bind_all("<MouseWheel>", self._global_mousewheel)
        self.update_tab_states()
        self.root.after(200, self._startup_checks)
        self.root.after(250, self._initial_previews)
        self.p1.plate.focus()

    # =============================================== оформление

    def _apply_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=CLR_BG, font=F(9))
        style.configure("TLabel", background=CLR_BG, foreground="#2C3E50")
        style.configure("TLabelframe", background=CLR_BG, borderwidth=0)
        style.configure("TLabelframe.Label", background=CLR_BG, foreground=CLR_NAVY)
        style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=F(10, True), padding=[20, 9],
                        background="#D0DCE5", foreground="#334E68")
        style.map("TNotebook.Tab",
                  background=[("selected", CLR_NAVY), ("active", "#BCCCDC")],
                  foreground=[("selected", "#FFFFFF"), ("active", "#102A43")])
        style.configure("Treeview", font=F(10), rowheight=26)
        style.configure("Treeview.Heading", font=F(9, True))

    def _build_header(self):
        header = tk.Frame(self.root, bg=CLR_NAVY, height=78)
        header.pack(fill="x")
        strip = tk.Frame(header, height=5)
        strip.pack(fill="x", side="top")
        for clr in ("#1E2548", CLR_TEAL, CLR_RED):
            tk.Frame(strip, bg=clr, height=5).pack(side="left", fill="both", expand=True)
        tk.Label(header, text="СПБ ГУП «ГОРЭЛЕКТРОТРАНС»", font=F(14, True),
                 bg=CLR_NAVY, fg="#FFFFFF").pack(anchor="w", padx=20, pady=(9, 0))
        note = f"  •  брендбук-шрифт: {ui_family()}" if ui_family() != "Segoe UI" else ""
        tk.Label(header,
                 text="Комплекс оформления пропусков на транспорт и постоянных "
                      f"пропусков работников{note}",
                 font=F(9), bg=CLR_NAVY, fg="#A0C4E2").pack(anchor="w", padx=20, pady=(0, 9))

    def _build_system_bar(self):
        bar = tk.Frame(self.root, bg=CLR_BG)
        bar.pack(fill="x", padx=12, pady=6)
        tk.Label(bar, text="🖨️ Принтер:", bg=CLR_BG, font=F(9, True)).pack(side="left")
        self.printer_var = tk.StringVar(value=self.settings.get("last_printer",
                                                                printing.DEFAULT_PRINTER))
        self.printer_cb = ttk.Combobox(bar, textvariable=self.printer_var,
                                       state="readonly", width=38, font=F(9))
        self.printer_cb.pack(side="left", padx=6)
        self.printer_cb["values"] = [self.printer_var.get()]
        self.printer_cb.bind("<<ComboboxSelected>>", lambda e: self.save_settings())
        # перечисление принтеров занимает секунды — не держим им запуск окна.
        # Результат забирает главный поток: вызывать tk из чужого потока нельзя.
        self._printer_result = queue.Queue(maxsize=1)
        threading.Thread(target=self._load_printers, daemon=True).start()
        self.root.after(300, self._poll_printers)

        styled_button(bar, "🧹 ОЧИСТИТЬ ФОРМУ", self.clear_current_form, "#E91E63",
                      font=F(10, True), padx=14, pady=3).pack(side="right", padx=(6, 0))
        styled_button(bar, "♻️ Восстановить", self.restore_database, "#FF9800",
                      padx=10, pady=3).pack(side="right", padx=3)
        styled_button(bar, "💾 Бэкап", self.backup_database, "#4CAF50",
                      padx=10, pady=3).pack(side="right", padx=3)
        styled_button(bar, "🧪 Тест иконок", self.dot_icons_test, "#7E57C2",
                      padx=10, pady=3).pack(side="right", padx=3)

    def _load_printers(self):
        """Выполняется в фоновом потоке: только считает список, tk не трогает."""
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

    # =============================================== вкладка ТС

    def _build_pass_tab(self):
        container = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(container, text="   🚗  Пропуск на ТС (Авто)   ")

        btn_bar = tk.Frame(container, bg=CLR_BG)
        btn_bar.pack(side="bottom", fill="x", pady=(8, 0))
        row1 = tk.Frame(btn_bar, bg=CLR_BG)
        row1.pack(fill="x", pady=(0, 6))
        styled_button(row1, "💾  Сохранить PDF  (Ctrl+S)", self.generate_pass, CLR_NAVY,
                      font=F(11, True), pady=10, activebackground="#051627"
                      ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        styled_button(row1, "🖨️  Напечатать сразу  (Ctrl+P)", self.direct_print_pass,
                      "#007799", font=F(11, True), pady=10, padx=18).pack(side="right")
        row2 = tk.Frame(btn_bar, bg=CLR_BG)
        row2.pack(fill="x")
        styled_button(row2, "📦 Массовая печать", self.open_batch_passes, "#486581",
                      pady=7, padx=12).pack(side="left", padx=(0, 6))
        styled_button(row2, "📋 Реестр ТС для печати", self.registry_passes, "#486581",
                      pady=7, padx=12).pack(side="left", padx=(0, 6))
        styled_button(row2, "📊 Журнал ТС", self.open_pass_journal, "#334E68",
                      pady=7, padx=14).pack(side="right")
        row3 = tk.Frame(btn_bar, bg=CLR_BG)
        row3.pack(fill="x", pady=(6, 0))
        styled_button(row3, "📤 Выгрузить таблицу", self.export_pass_journal, "#00838F",
                      pady=7, padx=12).pack(side="left")

        paned = tk.PanedWindow(container, orient="horizontal", bg="#CBD2D9",
                               sashwidth=5, sashrelief="raised", borderwidth=0)
        paned.pack(side="top", fill="both", expand=True)
        left = tk.Frame(paned, bg=CLR_CARD)
        paned.add(left, minsize=scaled(420, self.scale), width=scaled(700, self.scale))
        _, _, inner = make_scrollable(left, CLR_CARD)

        self.pass_notebook = ttk.Notebook(inner)
        self.pass_notebook.pack(fill="x", pady=(0, 6), padx=2)
        territory = self.settings.get("territory", "")
        self.p1 = PassForm(self.pass_notebook, self.settings["last_pass_num"],
                           self.preview.schedule, default_territory=territory)
        self.pass_notebook.add(self.p1.frame, text="  🚗 Пропуск №1 (Верхний)  ")
        self.p2 = PassForm(self.pass_notebook,
                           next_number(self.settings["last_pass_num"]).value,
                           self.preview.schedule, is_second=True,
                           default_territory="", peer_getter=self.p1.get_number)
        self.pass_notebook.add(self.p2.frame, text="  🚙 Пропуск №2 (Нижний)  ")

        self._build_common_box(inner)
        self._build_format_box(inner)
        self._build_preview_panel(paned)

    def _build_common_box(self, parent):
        box = tk.LabelFrame(parent, text=" Реквизиты и ответственные лица ",
                            font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=10, pady=6)
        box.pack(fill="x", pady=(0, 6), padx=2)
        row = tk.Frame(box, bg=CLR_CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Дата выдачи:", bg=CLR_CARD, fg="#486581",
                 font=F(9)).pack(side="left")
        self.entry_issue = ttk.Entry(row, width=13, font=F(9))
        self.entry_issue.insert(0, self.settings["issue_date"])
        self.entry_issue.pack(side="left", padx=(6, 16))
        tk.Label(row, text="Действителен до:", bg=CLR_CARD, fg="#486581",
                 font=F(9)).pack(side="left")
        self.entry_valid = ttk.Entry(row, width=13, font=F(9))
        self.entry_valid.insert(0, self.settings["valid_until"])
        self.entry_valid.pack(side="left", padx=(6, 0))
        # галка живёт на отдельной строке: в одной строке с двумя датами
        # её подпись не помещалась и обрезалась вместе с самим переключателем
        self.is_temp_var = tk.BooleanVar(value=self.settings.get("is_temporary_car", False))
        row_temp = tk.Frame(box, bg=CLR_CARD)
        row_temp.pack(fill="x", pady=(2, 0))
        tk.Checkbutton(row_temp, text="⚠️ Временный пропуск на ТС (не более 3 месяцев)",
                       variable=self.is_temp_var, command=self.on_toggle_temp,
                       bg=CLR_CARD, activebackground=CLR_CARD, font=F(9, True),
                       fg="#C62828", anchor="w").pack(side="left", anchor="w")

        row2 = tk.Frame(box, bg=CLR_CARD)
        row2.pack(fill="x", pady=(4, 2))
        tk.Label(row2, text="Должность ОТБ:", bg=CLR_CARD, fg="#486581",
                 font=F(9)).pack(side="left")
        self.entry_otb_post = ttk.Entry(row2, font=F(9))
        self.entry_otb_post.insert(0, self.settings.get("otb_post", ""))
        self.entry_otb_post.pack(side="left", fill="x", expand=True, padx=(6, 10))
        tk.Label(row2, text="ФИО ОТБ:", bg=CLR_CARD, fg="#486581",
                 font=F(9)).pack(side="left")
        self.entry_otb_name = ttk.Entry(row2, width=18, font=F(9))
        self.entry_otb_name.insert(0, self.settings.get("otb_name", ""))
        self.entry_otb_name.pack(side="left", padx=(6, 0))
        for widget in (self.entry_issue, self.entry_valid,
                       self.entry_otb_post, self.entry_otb_name):
            widget.bind("<KeyRelease>", self.preview.schedule, add="+")

    def _build_format_box(self, parent):
        box = tk.LabelFrame(parent, text=" Формат формирования ", font=F(9, True),
                            bg=CLR_CARD, fg=CLR_NAVY, padx=10, pady=4)
        box.pack(fill="x", pady=(0, 6), padx=2)
        self.print_mode = tk.StringVar(value=self.settings["print_mode"])
        for text, value in (("📄 Лист А4: Два пропуска (№1 сверху, №2 снизу)", "a4"),
                            ("📄 Лист А5: Один пропуск (вкладка №2 блокируется)", "a5")):
            tk.Radiobutton(box, text=text, variable=self.print_mode, value=value,
                           command=self.update_tab_states, bg=CLR_CARD,
                           activebackground=CLR_CARD, font=F(9)).pack(anchor="w")

    def _build_preview_panel(self, paned):
        self.preview_panel = tk.LabelFrame(paned, text=" ПРЕДПРОСМОТР ПРОПУСКА НА ТС ",
                                           font=F(11, True), bg="#FFFFFF", fg=CLR_NAVY,
                                           padx=12, pady=10)
        paned.add(self.preview_panel, minsize=scaled(330, self.scale), width=scaled(520, self.scale))
        switch = tk.Frame(self.preview_panel, bg="#FFFFFF")
        switch.pack(fill="x", pady=(0, 6))
        tk.Label(switch, text="Показывать:", bg="#FFFFFF", fg="#334E68",
                 font=F(9, True)).pack(side="left")
        self.preview_target = tk.StringVar(value=self.settings.get("auto_preview_target", "1"))
        for text, value in ((" Пропуск №1", "1"), (" Пропуск №2", "2")):
            tk.Radiobutton(switch, text=text, variable=self.preview_target, value=value,
                           bg="#FFFFFF", activebackground="#FFFFFF", font=F(9),
                           command=self.preview.schedule).pack(side="left", padx=4)
        self.preview_label = tk.Label(self.preview_panel, bg="#FFFFFF", relief="solid",
                                      borderwidth=1, fg="#829AB1", font=F(10),
                                      text="Заполните поля —\nпредпросмотр появится здесь")
        self.preview_label.pack(fill="both", expand=True, pady=(0, 8))
        tk.Label(self.preview_panel,
                 text="Макет обновляется автоматически при вводе данных.\n"
                      "Растяните разделитель или окно, чтобы увеличить превью.",
                 bg="#FFFFFF", fg="#718096", font=F(8, italic=True),
                 justify="center").pack()
        self.preview_panel.bind("<Configure>",
                                lambda e: self.preview.schedule(delay=140))

    # =============================================== предпросмотр

    def _initial_previews(self):
        self.badge.preview.schedule(delay=10)
        self.preview.schedule(delay=20)

    def _render_preview(self):
        try:
            if not R.template_exists():
                self.preview_label.config(image="",
                                          text="⚠ Нет файла template.png\nв папке программы")
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
            photo = R.ImageTk.PhotoImage(thumb) if hasattr(R, "ImageTk") else None
            if photo is None:
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(thumb)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass

    # =============================================== общие данные

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

    # =============================================== настройки

    def collect_settings(self):
        return {
            "last_pass_num": self.p1.get_number() or self.settings.get("last_pass_num"),
            "territory": self.p1.territory.get().strip() or self.settings.get("territory"),
            "otb_post": self.entry_otb_post.get().strip(),
            "otb_name": self.entry_otb_name.get().strip(),
            "valid_until": self.entry_valid.get().strip() or self.settings.get("valid_until"),
            "is_temporary_car": self.is_temp_var.get(),
            "print_mode": self.print_mode.get(),
            "last_printer": self.printer_var.get(),
            "auto_preview_target": self.preview_target.get(),
            **self.badge.collect_settings(),
        }

    def save_settings(self):
        values = self.collect_settings()
        self.settings.update(values)
        config.save_settings(values)

    def on_closing(self):
        if messagebox.askokcancel("Выход", "Закрыть программу?\n\n"
                                           "Введённые реквизиты будут сохранены."):
            self.save_settings()      # раньше настройки при выходе терялись
            self.preview.cancel()
            self.badge.preview.cancel()
            self.root.destroy()

    # =============================================== запуск/проверки

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
        # bind (не bind_all): раньше Ctrl+S из окна журнала или редактора фото
        # запускал печать главной формы
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
        self.preview.schedule()

    # =============================================== выпуск пропусков ТС

    def _validate_pass_dates(self):
        """Даты для выпуска. В отличие от предпросмотра здесь ошибки блокируют."""
        raw_issue = self.entry_issue.get()
        issue = parse_date(raw_issue)
        if issue is None:
            # раньше сюда молча подставлялась сегодняшняя дата, несмотря на
            # показанное предупреждение — документ печатался не с той датой
            messagebox.showwarning("Некорректная дата выдачи",
                                   f"Поле «Дата выдачи»: «{raw_issue}»\nФормат: ДД.ММ.ГГГГ")
            self.entry_issue.focus()
            return None, None
        valid = parse_date(self.entry_valid.get())
        if valid is None:
            messagebox.showwarning("Укажите срок",
                                   "Заполните поле «Действителен до» (ДД.ММ.ГГГГ).")
            self.entry_valid.focus()
            return None, None
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
        """Предупредить о действующем пропуске на тот же госномер."""
        if not self.settings.get("warn_duplicates", True):
            return True
        for form in forms:
            data = form.data()
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
        """Собрать документ к печати. Возвращает (изображение, имя, записи, след. номер)."""
        issue, valid = self._validate_pass_dates()
        if issue is None:
            return None
        if self.p1.is_empty():
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
        return document, prefix, records, next_number(source_num)

    def _finish_pass(self, records, next_num):
        """Записать журнал, базу машин и передвинуть нумерацию."""
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
        document, prefix, records, next_num = built
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Документ (для печати)", "*.pdf"), ("Изображение JPEG", "*.jpg")],
            initialfile=f"{prefix}.pdf")
        if not path:
            return
        try:
            printing.save_document(document, path)
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
        document, prefix, records, next_num = built
        ok, err = printing.send_image_to_printer(document, self.printer_var.get())
        if ok:
            # журнал и нумерация двигаются ТОЛЬКО после успешной отправки:
            # раньше при отказе принтера номер сгорал, а в журнале оставалась
            # запись о невыданном пропуске
            self._finish_pass(records, next_num)
            messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
            return
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
        try:
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

    def export_pass_journal(self):
        self._export_journal(PASS_JOURNAL, "Журнал_пропусков_ТС")

    def export_badge_journal(self):
        self._export_journal(BADGE_JOURNAL, "Журнал_работников")

    def _export_journal(self, journal, name):
        """Выгрузить журнал в отдельный файл (XLSX или CSV)."""
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
        except PermissionError:
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

    # =============================================== реестры и журналы

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
                "• «Нет» — не включать.\n\n"
                "Раньше такие записи молча попадали в число действующих."):
            unknown = []
        records = live + unknown
        today = datetime.now().strftime("%d.%m.%Y")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
            initialfile=f"{name}_{today}.pdf")
        if not path:
            return
        try:
            with ProgressDialog(self.root, "Формирование реестра",
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
                            "Журнал выданных пропусков ТС — ГЭТ СПб")

    def open_badge_journal(self):
        open_journal_window(self.root, BADGE_JOURNAL,
                            "Журнал постоянных пропусков работников — ГЭТ СПб")

    # =============================================== массовая печать

    def open_batch_passes(self):
        B.open_batch_dialog(
            self.root, "МАССОВАЯ ПЕЧАТЬ пропусков на ТС",
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
        if B.run_batch(self.root, "Массовая печать ТС", items,
                       lambda: B.pass_pages(items, common), pages_total,
                       PASS_JOURNAL, records,
                       f"Массовая_печать_ТС_{len(items)}шт.pdf"):
            update_cars_cache(items)

    def open_batch_badges(self):
        B.open_batch_dialog(
            self.root, "МАССОВАЯ ПЕЧАТЬ бейджей работников",
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
        B.run_batch(self.root, "Массовая печать бейджей", items,
                    lambda: B.badge_pages(items), pages_total,
                    BADGE_JOURNAL, records,
                    f"Массовая_печать_бейджей_{len(items)}шт.pdf")

    # =============================================== сервис

    def dot_icons_test(self):
        img, has_raqm = R.render_dot_icons_test_sheet()
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")],
            initialfile="test_DoT_Icons.png")
        if not path:
            return
        img.save(path)
        note = "" if has_raqm else "\n\nPillow собран без RAQM — лигатуры могут не собраться."
        messagebox.showinfo("Готово", f"Тестовый лист сохранён:\n{path}{note}")
        try:
            os.startfile(path)  # noqa: Windows only
        except Exception:
            pass

    def backup_database(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", filetypes=[("ZIP Архив", "*.zip")],
            initialfile=f"Backup_GET_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        if not path:
            return
        try:
            count, size = backup_mod.create_backup(path)
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
            accepted, skipped = backup_mod.inspect_backup(path)
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
            restored, _ = backup_mod.restore_backup(path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось восстановить: {exc}")
            return
        messagebox.showinfo("Успех",
                            f"Восстановлено файлов: {restored}.\nПерезапустите программу.")

    def run(self):
        self.root.mainloop()
