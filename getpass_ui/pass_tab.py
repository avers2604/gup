"""Форма одного пропуска на ТС.

Раньше каждая из двух вкладок раскладывалась в 12 отдельных глобальных
переменных (p1_num, p1_plate_var, ... p2_...). Теперь это объект с методом
data(), и функции печати больше не зависят от состояния интерфейса.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from getpass_core.domain import increment_number, normalize_plate
from getpass_core.storage import lookup_car

from .widgets import CLR_CARD, CLR_NAVY, F

TERRITORIES = ["", 'ПТО "Шаврова"', "Парковка", 'ПТО "Шаврова", Парковка']


class PassForm:
    """Виджеты и данные одной вкладки «Пропуск №N»."""

    def __init__(self, parent, default_num, on_change, is_second=False,
                 default_territory="", peer_getter=None):
        self.on_change = on_change
        self.peer_getter = peer_getter
        self.frame = tk.Frame(parent, bg=CLR_CARD, padx=12, pady=8)

        top = tk.Frame(self.frame, bg=CLR_CARD)
        top.pack(fill="x", pady=(0, 4))
        tk.Label(top, text="Номер бланка:", font=F(9, True), bg=CLR_CARD,
                 fg="#334E68").pack(side="left")
        self.num = ttk.Entry(top, width=12, font=F(10, True))
        self.num.insert(0, default_num)
        self.num.pack(side="left", padx=(6, 12))
        if is_second:
            tk.Button(top, text="⚡ №1 + 1", command=self._sync_from_peer,
                      bg="#E2E8F0", fg="#102A43", font=F(8, True), relief="flat",
                      padx=6, cursor="hand2").pack(side="left", padx=(0, 15))
        tk.Label(top, text="Зона допуска:", font=F(9, True), bg=CLR_CARD,
                 fg="#334E68").pack(side="left")
        self.territory = ttk.Combobox(top, values=TERRITORIES, state="normal", font=F(9))
        self.territory.set(default_territory)
        self.territory.pack(side="left", fill="x", expand=True, padx=(6, 0))

        plate_box = tk.LabelFrame(self.frame,
                                  text=" Государственный регистрационный знак ТС ",
                                  font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY,
                                  padx=8, pady=4)
        plate_box.pack(fill="x", pady=(0, 4))
        self.plate_var = tk.StringVar()
        self.plate_var.trace_add("write", self._force_caps)
        self.plate = ttk.Entry(plate_box, textvariable=self.plate_var, font=F(13, True))
        self.plate.pack(fill="x")

        row1 = tk.Frame(self.frame, bg=CLR_CARD)
        row1.pack(fill="x", pady=2)
        self.brand = self._labeled_entry(row1, "Марка:", 8, expand=True, pad=(0, 10))
        self.type = self._labeled_entry(row1, "Вид:", 5, expand=True)
        row2 = tk.Frame(self.frame, bg=CLR_CARD)
        row2.pack(fill="x", pady=2)
        self.model = self._labeled_entry(row2, "Модель:", 8, expand=True, pad=(0, 10))
        self.color = self._labeled_entry(row2, "Цвет:", 5, expand=True)

        driver = tk.LabelFrame(self.frame, text=" Водитель (управляющий ТС) ",
                               font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=4)
        driver.pack(fill="x", pady=(4, 2))
        rd1 = tk.Frame(driver, bg=CLR_CARD)
        rd1.pack(fill="x", pady=(0, 2))
        self.d_pos = self._labeled_entry(rd1, "Должность:", 11, expand=True)
        rd2 = tk.Frame(driver, bg=CLR_CARD)
        rd2.pack(fill="x")
        self.d_fio = self._labeled_entry(rd2, "ФИО:", 11, expand=True, pad=(0, 10))
        tk.Label(rd2, text="Телефон:", bg=CLR_CARD, fg="#486581",
                 font=F(9)).pack(side="left")
        self.d_phone = ttk.Entry(rd2, width=17, font=F(9))
        self.d_phone.pack(side="left", padx=(4, 0))

        self.plate.bind("<FocusOut>", lambda e: self.autocomplete())
        for widget in self.entries():
            widget.bind("<KeyRelease>", self.on_change, add="+")
        self.territory.bind("<<ComboboxSelected>>", self.on_change, add="+")
        self.territory.bind("<KeyRelease>", self.on_change, add="+")

    def _labeled_entry(self, parent, label, width, expand=False, pad=(0, 0)):
        tk.Label(parent, text=label, width=width, bg=CLR_CARD, anchor="w",
                 fg="#486581", font=F(9)).pack(side="left")
        entry = ttk.Entry(parent, font=F(9))
        entry.pack(side="left", fill="x", expand=expand, padx=pad)
        return entry

    # ------------------------------------------------------ поведение

    def _force_caps(self, *_args):
        val = self.plate_var.get()
        if val and val != val.upper():
            self.plate_var.set(val.upper())
            return          # trace вызовется повторно — не дёргаем предпросмотр дважды
        self.on_change()

    def _sync_from_peer(self):
        if not self.peer_getter:
            return
        self.num.delete(0, tk.END)
        self.num.insert(0, increment_number(self.peer_getter()))
        self.on_change()

    def entries(self):
        return [self.num, self.plate, self.brand, self.type, self.model,
                self.color, self.d_pos, self.d_fio, self.d_phone]

    def autocomplete(self):
        """Подставить данные машины из базы по госномеру."""
        car = lookup_car(self.plate_var.get())
        if not car:
            return
        filled = False
        pairs = ((self.brand, "brand"), (self.model, "model"), (self.type, "type"),
                 (self.color, "color"), (self.d_pos, "d_pos"), (self.d_fio, "d_fio"),
                 (self.d_phone, "d_phone"))
        for widget, key in pairs:
            if not widget.get().strip() and car.get(key):
                widget.insert(0, car[key])
                filled = True
        if not self.territory.get().strip() and car.get("territory"):
            self.territory.set(car["territory"])
            filled = True
        if filled:
            self.on_change()

    # ---------------------------------------------------------- данные

    def data(self, placeholder=False):
        pos = self.d_pos.get().strip()
        fio = self.d_fio.get().strip()
        driver_full = f"{pos} {fio}".strip()
        if placeholder and not driver_full:
            driver_full = "Должность  Фамилия И.О."
        plate = normalize_plate(self.plate_var.get())
        return {
            "num": self.num.get().strip() or ("000-00" if placeholder else "б/н"),
            "plate": plate or ("А 000 АА 00" if placeholder else ""),
            "brand": self.brand.get().strip(), "model": self.model.get().strip(),
            "type": self.type.get().strip(), "color": self.color.get().strip(),
            "d_pos": pos, "d_fio": fio, "phone": self.d_phone.get().strip(),
            "driver_full": driver_full,
            "territory": self.territory.get().strip(),
        }

    def is_empty(self):
        return not self.plate_var.get().strip()

    def set_number(self, value):
        self.num.delete(0, tk.END)
        self.num.insert(0, value)

    def get_number(self):
        return self.num.get().strip()

    def clear(self, default_territory=""):
        self.plate_var.set("")
        for widget in (self.brand, self.type, self.model, self.color,
                       self.d_pos, self.d_fio, self.d_phone):
            widget.delete(0, tk.END)
        self.territory.set(default_territory)
