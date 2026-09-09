"""Вкладка «Постоянный пропуск работника» — карточная компоновка (вариант В)."""
from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from getpass_core import config, printing
from getpass_core import render as R
from getpass_core.dpi import scaled
from getpass_core.domain import (add_years_safe, format_date, next_number,
                                 parse_date, split_fio)
from getpass_core.storage import BADGE_JOURNAL, FileBusy

from .components import AutocompleteEntry, Field, section_title
from .crop_window import open_crop_window, store_photo
from .theme import Card, Theme
from .widgets import Debouncer, make_scrollable

PARKS = ["ОСП «Трамвайный парк № 8»", "ОСП «Трамвайный парк № 5»",
         "ОСП «Трамвайный парк № 7»", "ОСП «Троллейбусный парк № 1»", 'ПТО "Шаврова"']


class BadgePanel:
    def __init__(self, notebook, settings, root, theme: Theme):
        self.settings = settings
        self.root = root
        self.theme = theme
        self.scale = theme.scale
        self.photo_path = None
        self.preview = Debouncer(root, self._render_preview, 60)

        th = theme
        self.container = tk.Frame(notebook, bg=th.c("ground"))
        notebook.add(self.container, text="  Пропуск работника  ")
        self.app = None          # проставляется владельцем для кнопок реестров

        self._build_buttons()
        self.paned = tk.PanedWindow(self.container, orient="horizontal", bg=th.c("ground"),
                                    sashwidth=th.px(6), sashrelief="flat", borderwidth=0)
        paned = self.paned
        paned.pack(side="top", fill="both", expand=True)
        left = tk.Frame(paned, bg=th.c("ground"))
        left_width = int(settings.get("badge_paned_width") or 0) or scaled(680, th.scale)
        paned.add(left, minsize=scaled(420, th.scale), width=left_width)
        _, _, self.left_panel = make_scrollable(left, th.c("ground"))
        self._build_form()
        self._build_preview(paned)

    def bind_app(self, app):
        """Связать кнопки, которым нужны действия уровня приложения."""
        self.app = app
        self._btn_batch.config(command=app.open_batch_badges)
        self._btn_registry.config(command=app.registry_badges)
        self._btn_journal.config(command=app.open_badge_journal)
        self._btn_export.config(command=app.export_badge_journal)

    # ------------------------------------------------------- разметка

    def _build_buttons(self):
        th = self.theme
        bar = tk.Frame(self.container, bg=th.c("ground"))
        bar.pack(side="bottom", fill="x", pady=(th.sp(3), 0))
        row1 = tk.Frame(bar, bg=th.c("ground"))
        row1.pack(fill="x", pady=(0, th.sp(2)))
        ttk.Button(row1, text="Сохранить PDF   (Ctrl+S)", command=self.generate_pdf,
                  style="Primary.TButton").pack(side="left", fill="x", expand=True,
                                                padx=(0, th.sp(2)))
        ttk.Button(row1, text="Напечатать сразу   (Ctrl+P)", command=self.direct_print,
                  style="Accent.TButton").pack(side="right", fill="x", expand=True)
        row2 = tk.Frame(bar, bg=th.c("ground"))
        row2.pack(fill="x")
        self._btn_batch = ttk.Button(row2, text="Массовая печать", style="Ghost.TButton")
        self._btn_batch.pack(side="left", padx=(0, th.sp(2)))
        self._btn_registry = ttk.Button(row2, text="Реестр работников", style="Ghost.TButton")
        self._btn_registry.pack(side="left", padx=(0, th.sp(2)))
        self._btn_export = ttk.Button(row2, text="Выгрузить таблицу", style="Ghost.TButton")
        self._btn_export.pack(side="left")
        self._btn_journal = ttk.Button(row2, text="Журнал бейджей", style="Ghost.TButton")
        self._btn_journal.pack(side="right")

    def _build_form(self):
        th = self.theme
        card = Card(self.left_panel, th)
        card.pack(fill="x", pady=(0, th.sp(3)))
        b = card.body
        section_title(b, th, "Данные сотрудника").pack(anchor="w", pady=(0, th.sp(3)))

        row0 = tk.Frame(b, bg=th.c("surface"))
        row0.pack(fill="x", pady=(0, th.sp(3)))
        self.park = Field(row0, th, "Подразделение", kind="combobox", values=PARKS)
        self.park.pack(side="left", fill="x", expand=True, padx=(0, th.sp(3)))
        self.park.set(self.settings.get("badge_park", PARKS[0]))
        self.park.bind("<<ComboboxSelected>>", self.preview.schedule)
        self.park.bind("<KeyRelease>", self.preview.schedule)
        self.tab_num = Field(row0, th, "Табельный №", width=10)
        self.tab_num.pack(side="left")
        self.tab_num.set(self.settings.get("badge_tab_num", "01035"))
        self.tab_num.bind("<KeyRelease>", self.preview.schedule)

        self.role = AutocompleteEntry(b, th, "Должность", self._known_roles, required=True)
        self.role.pack(fill="x", pady=(0, th.sp(3)))
        self.role.bind("<KeyRelease>", self.preview.schedule, add="+")

        self.sur_var, self.nam_var, self.pat_var = (tk.StringVar() for _ in range(3))
        for var in (self.sur_var, self.nam_var, self.pat_var):
            var.trace_add("write", self._make_upper(var))
        self.sur_field = Field(b, th, "Фамилия сотрудника", textvariable=self.sur_var,
                               required=True)
        self.sur_field.pack(fill="x", pady=(0, th.sp(3)))
        self.nam_field = Field(b, th, "Имя сотрудника", textvariable=self.nam_var,
                               required=True)
        self.nam_field.pack(fill="x", pady=(0, th.sp(3)))
        self.pat_field = Field(b, th, "Отчество сотрудника", textvariable=self.pat_var)
        self.pat_field.pack(fill="x", pady=(0, th.sp(3)))
        self.phone = Field(b, th, "Телефон (для базы и КПП)")
        self.phone.pack(fill="x")
        card.fit()

        photo_card = Card(self.left_panel, th)
        photo_card.pack(fill="x", pady=(0, th.sp(3)))
        pb = photo_card.body
        section_title(pb, th, "Фотография").pack(anchor="w", pady=(0, th.sp(3)))
        photo_row = tk.Frame(pb, bg=th.c("surface"))
        photo_row.pack(fill="x")
        ttk.Button(photo_row, text="Выбрать и обрезать (зум + сдвиг)",
                  command=self.select_photo, style="Primary.TButton").pack(side="left")
        self.photo_status = tk.Label(photo_row, text="Фото не выбрано",
                                     bg=th.c("surface"), fg=th.c("danger"),
                                     font=th.font("caption"))
        self.photo_status.pack(side="left", padx=(th.sp(3), 0))
        photo_card.fit()

        date_card = Card(self.left_panel, th)
        date_card.pack(fill="x", pady=(0, th.sp(3)))
        db = date_card.body
        section_title(db, th, "Срок действия (постоянный: 5 лет)").pack(
            anchor="w", pady=(0, th.sp(3)))
        dt_row = tk.Frame(db, bg=th.c("surface"))
        dt_row.pack(fill="x")
        today = datetime.now()
        self.issue = Field(dt_row, th, "Выдан", width=11, required=True)
        self.issue.pack(side="left", padx=(0, th.sp(3)))
        self.issue.set(format_date(today))
        self.issue.bind("<KeyRelease>", self.preview.schedule)
        self.valid = Field(dt_row, th, "До", width=11, required=True)
        self.valid.pack(side="left", padx=(0, th.sp(3)))
        self.valid.set(format_date(add_years_safe(today, 5)))
        self.valid.bind("<KeyRelease>", self.preview.schedule)
        quick = tk.Frame(dt_row, bg=th.c("surface"))
        quick.pack(side="left", anchor="s", pady=(0, th.px(2)))
        ttk.Button(quick, text="+5 лет", command=lambda: self.set_years(5),
                  style="Ghost.TButton").pack(side="left", padx=(0, th.sp(1)))
        ttk.Button(quick, text="+1 год", command=lambda: self.set_years(1),
                  style="Ghost.TButton").pack(side="left")
        date_card.fit()

        fmt_card = Card(self.left_panel, th)
        fmt_card.pack(fill="x")
        fb = fmt_card.body
        section_title(fb, th, "Формат формирования").pack(anchor="w", pady=(0, th.sp(2)))
        self.print_mode = tk.StringVar(value=self.settings.get("badge_print_mode", "card"))
        for text, value in (
                ("Пластиковая карта (85 × 54 мм) — карточный принтер", "card"),
                ("Лист А4, сетка 3×3 (9 бейджей) — для нарезки резаком", "a4_grid"),
                ("Лист А4, 1 бейдж по центру — тестовый лист", "a4_single")):
            th.radio(fb, text, self.print_mode, value).pack(anchor="w")
        fmt_card.fit()

    def _build_preview(self, paned):
        th = self.theme
        wrapper = tk.Frame(paned, bg=th.c("ground"))
        paned.add(wrapper, minsize=scaled(340, th.scale), width=scaled(520, th.scale))
        self.panel = Card(wrapper, th)
        self.panel.pack(fill="both", expand=True)
        b = self.panel.body
        section_title(b, th, "Предпросмотр бейджа (85 × 54 мм)").pack(
            anchor="w", pady=(0, th.sp(3)))
        self.preview_label = tk.Label(b, bg=th.c("surface"), fg=th.c("ink_faint"),
                                      font=th.font("body"), text="Предпросмотр загружается...")
        self.preview_label.pack(fill="both", expand=True)
        tk.Label(b, text="Макет обновляется на лету при изменении любых полей.",
                bg=th.c("surface"), fg=th.c("ink_faint"), font=th.font("caption")
                ).pack(pady=(th.sp(2), 0))
        self.panel.bind("<Configure>", lambda e: self.preview.schedule(delay=140))

    # ------------------------------------------------------- поведение

    def _known_roles(self):
        """Должности, уже встречавшиеся в журнале бейджей — для автодополнения."""
        return BADGE_JOURNAL.distinct("role")

    def _make_upper(self, var):
        def callback(*_a):
            value = var.get()
            if value and value != value.upper():
                var.set(value.upper())
                return
            self.preview.schedule()
        return callback

    def set_years(self, years):
        issue = parse_date(self.issue.get())
        if issue is None:
            messagebox.showwarning("Некорректная дата",
                                   "Поле «Выдан»: укажите дату в формате ДД.ММ.ГГГГ.")
            return
        self.valid.set(format_date(add_years_safe(issue, years)))
        self.preview.schedule()

    def select_photo(self):
        path = filedialog.askopenfilename(
            title="Выберите фотографию сотрудника",
            filetypes=[("Файлы изображений", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                       ("Все файлы", "*.*")])
        if not path:
            return
        self.photo_status.config(text="Открыт редактор кадрирования...",
                                 fg=self.theme.c("accent_fill"))
        open_crop_window(self.root, path, self._apply_crop, self.theme)

    def _apply_crop(self, cropped, box):
        # каждый кадр сохраняется отдельным файлом в архиве фотографий:
        # общий временный файл затирался следующим сотрудником
        self.photo_path = store_photo(cropped, config.PHOTO_DIR, self.tab_num.get().strip())
        self.photo_status.config(text=f"Фото: {box[2]}×{box[3]} px (3:4)",
                                 fg=self.theme.c("success"))
        self.preview.schedule()

    # ---------------------------------------------------------- данные

    def preview_data(self):
        sur = self.sur_var.get().strip() or "ФАМИЛИЯ"
        nam = self.nam_var.get().strip() or "ИМЯ"
        pat = self.pat_var.get().strip() or "ОТЧЕСТВО"
        return {"tab_num": self.tab_num.get().strip() or "00000",
                "park": self.park.get().strip() or PARKS[0],
                "role": self.role.get().strip() or "Должность",
                "surname": sur, "name": nam, "patronymic": pat,
                "fio": split_fio(sur, nam, pat), "phone": self.phone.get().strip(),
                "issue_date": self.issue.get().strip() or format_date(datetime.now()),
                "valid_until": self.valid.get().strip()
                or format_date(add_years_safe(datetime.now(), 5)),
                "photo_path": self.photo_path}

    def batch_defaults(self):
        return {"park": self.park.get().strip() or PARKS[0],
                "issue_date": self.issue.get().strip() or format_date(datetime.now()),
                "valid_until": self.valid.get().strip()
                or format_date(add_years_safe(datetime.now(), 5))}

    def validate_required(self) -> bool:
        """Подсветить незаполненные обязательные поля. True — форма годна."""
        ok = True
        for field in (self.role, self.sur_field, self.nam_field, self.issue, self.valid):
            ok = field.validate() and ok
        return ok

    def validated_data(self):
        if not self.photo_path or not os.path.exists(self.photo_path):
            messagebox.showwarning("Фото обязательно",
                                   "Выберите фотографию сотрудника и обрежьте её в редакторе!")
            return None
        self.validate_required()
        issue = parse_date(self.issue.get())
        if issue is None:
            messagebox.showwarning("Некорректная дата",
                                   f"Поле «Выдан»: «{self.issue.get()}»\nФормат: ДД.ММ.ГГГГ")
            return None
        valid = parse_date(self.valid.get())
        if valid is None:
            messagebox.showwarning("Некорректная дата",
                                   f"Поле «До»: «{self.valid.get()}»\nФормат: ДД.ММ.ГГГГ")
            return None
        if valid < issue:
            messagebox.showwarning("Ошибка дат",
                                   "Дата окончания не может быть раньше даты выдачи!")
            return None
        sur, nam = self.sur_var.get().strip(), self.nam_var.get().strip()
        if not (sur and nam):
            messagebox.showwarning("Заполните ФИО", "Заполните Фамилию и Имя сотрудника!")
            self.sur_field.focus()
            return None
        tab_num = self.tab_num.get().strip() or "00001"
        dups = BADGE_JOURNAL.find_duplicates(tab_num)
        if dups and not messagebox.askyesno(
                "Табельный номер уже выдан",
                f"На табельный № {tab_num} уже есть действующий пропуск:\n"
                + "\n".join(f"  • {d.get('fio','')} — до {d.get('valid_until','')}"
                            for d in dups[:5])
                + "\n\nВыдать ещё один?"):
            return None
        pat = self.pat_var.get().strip()
        return {"tab_num": tab_num, "park": self.park.get().strip(),
                "role": self.role.get().strip() or "Сотрудник",
                "surname": sur, "name": nam, "patronymic": pat,
                "fio": split_fio(sur, nam, pat), "phone": self.phone.get().strip(),
                "issue_date": format_date(issue), "valid_until": format_date(valid),
                "photo_path": self.photo_path}

    def build_document(self, data):
        badge = R.render_single_badge_image(data)
        mode = self.print_mode.get()
        if mode == "card":
            return badge, f"Пропуск_{data['tab_num']}_{data['surname']}_CR80"
        if mode == "a4_grid":
            return (R.build_badge_a4_grid([badge] * 9),
                    f"Пропуска_{data['tab_num']}_9шт_А4")
        return R.build_badge_a4_single(badge), f"Пропуск_{data['tab_num']}_1шт_А4"

    # --------------------------------------------------------- выпуск

    def _finish(self, data):
        record = dict(data)
        try:
            BADGE_JOURNAL.append_many([record])
        except FileBusy as exc:
            messagebox.showerror(
                "Журнал не обновлён",
                f"Документ готов, но «{os.path.basename(exc.path)}» открыт "
                "в другой программе.\nЗакройте его — запись в журнал не попала.")
        except Exception as exc:
            messagebox.showerror("Журнал не обновлён", str(exc))
        nxt = next_number(data["tab_num"])
        if nxt.overflowed:
            messagebox.showwarning(
                "Переполнение нумерации",
                f"Следующий табельный номер «{nxt.value}» вышел за разрядность.")
        self.tab_num.set(nxt.value)
        self.clear_form()
        return nxt.value

    def generate_pdf(self):
        data = self.validated_data()
        if not data:
            return
        document, prefix = self.build_document(data)
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
            initialfile=f"{prefix}.pdf")
        if not path:
            return
        try:
            printing.save_document(document, path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{exc}")
            return
        nxt = self._finish(data)
        messagebox.showinfo("Готово",
                            f"Пропуск работника сформирован!\nСледующий табельный: {nxt}")

    def direct_print(self):
        data = self.validated_data()
        if not data:
            return
        document, prefix = self.build_document(data)
        printer = self.app.printer_var.get() if self.app else printing.DEFAULT_PRINTER
        ok, err = printing.send_image_to_printer(document, printer)
        if ok:
            self._finish(data)
            messagebox.showinfo("Печать", "Бейдж успешно отправлен на принтер!")
            return
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{data['tab_num']}.pdf")
        opened = False
        try:
            printing.save_document(document, temp_pdf)
            os.startfile(temp_pdf)  # noqa: Windows only
            opened = True
        except Exception:
            pass
        if messagebox.askyesno(
                "Принтер не ответил",
                f"Не удалось напечатать напрямую.\n{err or ''}\n\n"
                + ("Документ открыт — напечатайте вручную (Ctrl+P).\n\n" if opened else "")
                + "Считать бейдж выданным и записать в журнал?"):
            self._finish(data)

    # ---------------------------------------------------------- прочее

    def collect_settings(self):
        try:
            paned_width = self.paned.sash_coord(0)[0]
        except Exception:
            paned_width = self.settings.get("badge_paned_width", 0)
        return {"badge_park": self.park.get().strip(),
                "badge_tab_num": self.tab_num.get().strip()
                or self.settings.get("badge_tab_num", "01035"),
                "badge_print_mode": self.print_mode.get(),
                "badge_paned_width": paned_width}

    def clear_form(self, confirm=False):
        if confirm and not messagebox.askyesno(
                "Очистить форму", "Очистить данные сотрудника и выбранное фото?"):
            return
        self.photo_path = None
        for var in (self.sur_var, self.nam_var, self.pat_var):
            var.set("")
        self.role.delete(0, tk.END)
        self.phone.delete(0, tk.END)
        today = datetime.now()
        self.issue.set(format_date(today))
        self.valid.set(format_date(add_years_safe(today, 5)))
        self.photo_status.config(text="Фото не выбрано", fg=self.theme.c("danger"))
        for field in (self.role, self.sur_field, self.nam_field, self.issue, self.valid):
            field.validate()
        self.preview.schedule()

    def _render_preview(self):
        try:
            badge = R.render_single_badge_image(self.preview_data())
            panel_w = self.panel.winfo_width() or 420
            panel_h = self.panel.winfo_height() or 620
            max_w = max(120, panel_w - 40)
            max_h = max(160, panel_h - 130)
            ratio = R.CARD_H / R.CARD_W
            w = min(max_w, 1200)
            h = int(w * ratio)
            if h > max_h:
                h, w = max_h, int(max_h / ratio)
            thumb = badge.resize((max(60, w), max(80, h)), R.Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumb)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass
