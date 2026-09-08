"""Вкладка «Постоянный пропуск работника»."""
from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from getpass_core import config, printing
from getpass_core import render as R
from getpass_core.domain import (add_years_safe, format_date, next_number,
                                 parse_date, split_fio)
from getpass_core.storage import BADGE_JOURNAL, FileBusy

from .crop_window import open_crop_window, store_photo
from .widgets import (CLR_BG, CLR_CARD, CLR_NAVY, Debouncer, F, make_scrollable,
                      styled_button)

PARKS = ["ОСП «Трамвайный парк № 8»", "ОСП «Трамвайный парк № 5»",
         "ОСП «Трамвайный парк № 7»", "ОСП «Троллейбусный парк № 1»", 'ПТО "Шаврова"']


class BadgePanel:
    def __init__(self, notebook, settings, root, scale=1.0):
        self.settings = settings
        self.root = root
        self.scale = scale
        self.photo_path = None
        self.preview = Debouncer(root, self._render_preview, 60)

        self.container = ttk.Frame(notebook, padding="8")
        notebook.add(self.container, text="   🪪  Постоянный пропуск для работников   ")
        self.app = None          # проставляется владельцем для кнопок реестров

        self._build_buttons()
        paned = tk.PanedWindow(self.container, orient="horizontal", bg="#CBD2D9",
                               sashwidth=5, sashrelief="raised", borderwidth=0)
        paned.pack(side="top", fill="both", expand=True)
        left = tk.Frame(paned, bg=CLR_BG)
        paned.add(left, minsize=int(420 * self.scale), width=int(680 * self.scale))
        _, _, self.left_panel = make_scrollable(left, CLR_BG)
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
        bar = tk.Frame(self.container, bg=CLR_BG)
        bar.pack(side="bottom", fill="x", pady=(8, 0))
        row1 = tk.Frame(bar, bg=CLR_BG)
        row1.pack(fill="x", pady=(0, 6))
        styled_button(row1, "💾  Сохранить PDF  (Ctrl+S)", self.generate_pdf, CLR_NAVY,
                      font=F(11, True), pady=10, activebackground="#051627"
                      ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        styled_button(row1, "🖨️  Напечатать сразу  (Ctrl+P)", self.direct_print,
                      "#007799", font=F(11, True), pady=10, padx=18).pack(side="right")
        row2 = tk.Frame(bar, bg=CLR_BG)
        row2.pack(fill="x")
        self._btn_batch = styled_button(row2, "📦 Массовая печать", lambda: None,
                                        "#486581", pady=7, padx=12)
        self._btn_batch.pack(side="left", padx=(0, 6))
        self._btn_registry = styled_button(row2, "📋 Реестр работников", lambda: None,
                                           "#486581", pady=7, padx=12)
        self._btn_registry.pack(side="left", padx=(0, 6))
        self._btn_journal = styled_button(row2, "📊 Журнал бейджей", lambda: None,
                                          "#334E68", pady=7, padx=14)
        self._btn_journal.pack(side="right")
        row3 = tk.Frame(bar, bg=CLR_BG)
        row3.pack(fill="x", pady=(6, 0))
        styled_button(row3, "🗄 Внести в базу (без печати)", self.save_to_journal,
                      "#2E7D32", pady=7, padx=12).pack(side="left", padx=(0, 6))
        self._btn_export = styled_button(row3, "📤 Выгрузить таблицу", lambda: None,
                                         "#00838F", pady=7, padx=12)
        self._btn_export.pack(side="left")

    def _build_form(self):
        card = tk.LabelFrame(self.left_panel, text=" Данные сотрудника ",
                             font=F(10, True), bg=CLR_CARD, fg=CLR_NAVY, padx=12, pady=8)
        card.pack(fill="both", expand=True, pady=(0, 6), padx=4)

        row0 = tk.Frame(card, bg=CLR_CARD)
        row0.pack(fill="x", pady=(0, 6))
        tk.Label(row0, text="Подразделение:", font=F(9, True), bg=CLR_CARD,
                 fg="#334E68").pack(side="left")
        self.park = ttk.Combobox(row0, values=PARKS, state="normal", font=F(9))
        self.park.set(self.settings.get("badge_park", PARKS[0]))
        self.park.pack(side="left", fill="x", expand=True, padx=(6, 12))
        self.park.bind("<<ComboboxSelected>>", self.preview.schedule)
        self.park.bind("<KeyRelease>", self.preview.schedule)
        tk.Label(row0, text="Табельный №:", font=F(9, True), bg=CLR_CARD,
                 fg="#334E68").pack(side="left")
        self.tab_num = ttk.Entry(row0, width=9, font=F(10, True))
        self.tab_num.insert(0, self.settings.get("badge_tab_num", "01035"))
        self.tab_num.pack(side="left", padx=(6, 0))
        self.tab_num.bind("<KeyRelease>", self.preview.schedule)

        row_role = tk.Frame(card, bg=CLR_CARD)
        row_role.pack(fill="x", pady=(0, 6))
        tk.Label(row_role, text="Должность:", font=F(9, True), bg=CLR_CARD,
                 fg="#334E68").pack(side="left")
        self.role = ttk.Entry(row_role, font=F(10))
        self.role.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.role.bind("<KeyRelease>", self.preview.schedule)

        self.sur_var, self.nam_var, self.pat_var = (tk.StringVar() for _ in range(3))
        for var in (self.sur_var, self.nam_var, self.pat_var):
            var.trace_add("write", self._make_upper(var))
        for label, var, attr in (("Фамилия сотрудника:", self.sur_var, "sur_ent"),
                                 ("Имя сотрудника:", self.nam_var, "nam_ent"),
                                 ("Отчество сотрудника:", self.pat_var, "pat_ent")):
            tk.Label(card, text=label, font=F(9, True), bg=CLR_CARD,
                     fg="#486581").pack(anchor="w")
            entry = ttk.Entry(card, textvariable=var, font=F(11, True))
            entry.pack(fill="x", pady=(1, 4))
            setattr(self, attr, entry)

        tk.Label(card, text="Телефон (для базы и КПП):", font=F(9), bg=CLR_CARD,
                 fg="#486581").pack(anchor="w")
        self.phone = ttk.Entry(card, font=F(10))
        self.phone.pack(fill="x", pady=(1, 6))

        photo_row = tk.Frame(card, bg=CLR_CARD)
        photo_row.pack(fill="x", pady=(0, 6))
        styled_button(photo_row, "📷 Выбрать фото и обрезать (зум + сдвиг)",
                      self.select_photo, CLR_NAVY, padx=10, pady=6).pack(side="left")
        self.photo_status = tk.Label(photo_row, text="Фото не выбрано", font=F(8),
                                     bg=CLR_CARD, fg="#C62828")
        self.photo_status.pack(side="left", padx=(10, 0))

        date_box = tk.LabelFrame(card, text=" Срок действия (постоянный: 5 лет) ",
                                 font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=6)
        date_box.pack(fill="x", pady=(2, 6))
        dt_row = tk.Frame(date_box, bg=CLR_CARD)
        dt_row.pack(fill="x")
        today = datetime.now()
        tk.Label(dt_row, text="Выдан:", font=F(9, True), bg=CLR_CARD,
                 fg="#486581").pack(side="left")
        self.issue = ttk.Entry(dt_row, width=11, font=F(9))
        self.issue.insert(0, format_date(today))
        self.issue.pack(side="left", padx=(4, 10))
        self.issue.bind("<KeyRelease>", self.preview.schedule)
        tk.Label(dt_row, text="До:", font=F(9, True), bg=CLR_CARD,
                 fg="#486581").pack(side="left")
        self.valid = ttk.Entry(dt_row, width=11, font=F(9, True))
        self.valid.insert(0, format_date(add_years_safe(today, 5)))
        self.valid.pack(side="left", padx=(4, 10))
        self.valid.bind("<KeyRelease>", self.preview.schedule)
        for text, years, color in (("+ 5 лет", 5, "#0A2540"), ("+ 1 год", 1, "#486581")):
            tk.Button(dt_row, text=text, command=lambda y=years: self.set_years(y),
                      bg="#E2E8F0", fg=color, font=F(8, True), relief="flat",
                      padx=6, pady=2, cursor="hand2").pack(side="left", padx=(0, 4))

        fmt = tk.LabelFrame(card, text=" Формат формирования ", font=F(9, True),
                            bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=4)
        fmt.pack(fill="x", pady=(2, 0))
        self.print_mode = tk.StringVar(value=self.settings.get("badge_print_mode", "card"))
        for text, value in (
                ("🪪 Пластиковая карта (85 × 54 мм) — карточный принтер", "card"),
                ("📄 Лист А4 (сетка 3×3, 9 бейджей) — для нарезки резаком", "a4_grid"),
                ("📄 Лист А4 (1 бейдж по центру) — тестовый лист", "a4_single")):
            tk.Radiobutton(fmt, text=text, variable=self.print_mode, value=value,
                           bg=CLR_CARD, activebackground=CLR_CARD,
                           font=F(9)).pack(anchor="w")

    def _build_preview(self, paned):
        self.panel = tk.LabelFrame(paned, text=" ПРЕДПРОСМОТР БЕЙДЖА (85 × 54 мм) ",
                                   font=F(11, True), bg="#FFFFFF", fg=CLR_NAVY,
                                   padx=14, pady=12)
        paned.add(self.panel, minsize=int(330 * self.scale), width=int(520 * self.scale))
        self.preview_label = tk.Label(self.panel, bg="#FFFFFF", relief="solid",
                                      borderwidth=1, text="Предпросмотр загружается...",
                                      fg="#829AB1", font=F(10))
        self.preview_label.pack(fill="both", expand=True, pady=(0, 8))
        tk.Label(self.panel,
                 text="Макет обновляется на лету при изменении любых полей.\n"
                      "Растяните разделитель или окно — превью увеличится.",
                 bg="#FFFFFF", fg="#718096", font=F(8, italic=True),
                 justify="center").pack()
        self.panel.bind("<Configure>", lambda e: self.preview.schedule(delay=140))

    # ------------------------------------------------------- поведение

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
        self.valid.delete(0, tk.END)
        self.valid.insert(0, format_date(add_years_safe(issue, years)))
        self.preview.schedule()

    def select_photo(self):
        path = filedialog.askopenfilename(
            title="Выберите фотографию сотрудника",
            filetypes=[("Файлы изображений", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                       ("Все файлы", "*.*")])
        if not path:
            return
        self.photo_status.config(text="⏳ Открыт редактор кадрирования...", fg="#1565C0")
        open_crop_window(self.root, path, self._apply_crop, self.scale)

    def _apply_crop(self, cropped, box):
        # каждый кадр сохраняется отдельным файлом в архиве фотографий:
        # общий временный файл затирался следующим сотрудником
        self.photo_path = store_photo(cropped, config.PHOTO_DIR, self.tab_num.get().strip())
        self.photo_status.config(text=f"✓ Фото: {box[2]}×{box[3]} px (3:4)", fg="#2E7D32")
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

    def validated_data(self, require_photo=True):
        if require_photo and (not self.photo_path or not os.path.exists(self.photo_path)):
            messagebox.showwarning("Фото обязательно",
                                   "Выберите фотографию сотрудника и обрежьте её в редакторе!")
            return None
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
            self.sur_ent.focus()
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

    def _finish(self, data, operator):
        record = dict(data, operator=operator)
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
        self.tab_num.delete(0, tk.END)
        self.tab_num.insert(0, nxt.value)
        self.clear_form()
        return nxt.value

    def save_to_journal(self):
        """Внести работника в базу, не формируя бейдж (фото не требуется)."""
        data = self.validated_data(require_photo=False)
        if not data:
            return
        if not messagebox.askyesno(
                "Внести в базу",
                f"Записать в журнал без печати?\n\n"
                f"{data['fio']}, таб. № {data['tab_num']}\n\n"
                "Табельный номер будет увеличен, форма очищена."):
            return
        nxt = self._finish(data, self._operator())
        messagebox.showinfo("Готово",
                            f"Запись внесена.\nСледующий табельный номер: {nxt}")

    def generate_pdf(self, operator=""):
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
        nxt = self._finish(data, self._operator())
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
            self._finish(data, self._operator())
            messagebox.showinfo("Печать", "Бейдж успешно отправлен на принтер!")
            return
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
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
            self._finish(data, self._operator())

    def _operator(self):
        return self.app.operator_var.get().strip() if self.app else ""

    # ---------------------------------------------------------- прочее

    def collect_settings(self):
        return {"badge_park": self.park.get().strip(),
                "badge_tab_num": self.tab_num.get().strip()
                or self.settings.get("badge_tab_num", "01035"),
                "badge_print_mode": self.print_mode.get()}

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
        self.issue.delete(0, tk.END)
        self.issue.insert(0, format_date(today))
        self.valid.delete(0, tk.END)
        self.valid.insert(0, format_date(add_years_safe(today, 5)))
        self.photo_status.config(text="Фото не выбрано", fg="#C62828")
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
