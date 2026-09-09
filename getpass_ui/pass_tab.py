"""Форма одного пропуска на ТС."""
from __future__ import annotations

import tkinter as tk

from getpass_core.domain import increment_number, normalize_plate
from getpass_core.storage import lookup_car

from .components import AutocompleteEntry, Field, hbox, section_title
from .theme import Theme

TERRITORIES = ['ПТО "Шаврова"', "Парковка", 'ПТО "Шаврова", Парковка']


class PassForm:
    """Виджеты и данные одной вкладки «Пропуск №N»."""

    def __init__(self, parent, theme: Theme, default_num, on_change, is_second=False,
                 default_territory="", peer_getter=None, zones_source=None,
                 makes_source=None):
        self.theme = theme
        self.on_change = on_change
        self.peer_getter = peer_getter
        self._zones_source = zones_source or (lambda: TERRITORIES)
        self._makes_source = makes_source or (lambda: [])

        bg = theme.c("surface")
        self.frame = tk.Frame(parent, bg=bg)
        pad = tk.Frame(self.frame, bg=bg)
        pad.pack(fill="both", expand=True, padx=theme.sp(3), pady=theme.sp(3))

        top = hbox(pad, theme)
        tk.Label(top, text="№ бланка:", bg=bg, fg=theme.c("ink_muted"),
                 font=theme.font("caption")).pack(side="left")
        self.num = tk.Entry(top, width=10, font=theme.font("data"),
                            bg=theme.c("surface_alt"), fg=theme.c("ink"),
                            relief="flat", insertbackground=theme.c("ink"))
        self.num.insert(0, default_num)
        self.num.pack(side="left", padx=(theme.sp(2), theme.sp(3)), ipady=theme.px(3))
        if is_second:
            tk.Button(top, text="№1 + 1", command=self._sync_from_peer,
                      bg=theme.c("surface_alt"), fg=theme.c("ink_muted"),
                      font=theme.font("caption"), relief="flat", padx=theme.px(6),
                      cursor="hand2", activebackground=theme.c("line")
                      ).pack(side="left", padx=(0, theme.sp(3)))

        self.plate = Field(pad, theme, "Государственный регистрационный знак",
                           required=True)
        self.plate.pack(fill="x", pady=(theme.sp(2), theme.sp(3)))
        self.plate.configure_field(font=theme.font("data"))
        self.plate_var = tk.StringVar()
        self.plate.widget.configure(textvariable=self.plate_var)
        self.plate_var.trace_add("write", self._force_caps)

        row1 = hbox(pad, theme)
        self.brand = AutocompleteEntry(row1, theme, "Марка", self._makes_source)
        self.brand.pack(side="left", fill="x", expand=True, padx=(0, theme.sp(3)))
        self.type = Field(row1, theme, "Вид")
        self.type.pack(side="left", fill="x", expand=True)

        row2 = hbox(pad, theme, pady=(theme.sp(3), 0))
        self.model = Field(row2, theme, "Модель")
        self.model.pack(side="left", fill="x", expand=True, padx=(0, theme.sp(3)))
        self.color = Field(row2, theme, "Цвет")
        self.color.pack(side="left", fill="x", expand=True)

        section_title(pad, theme, "Водитель").pack(anchor="w",
                                                    pady=(theme.sp(4), theme.sp(2)))
        self.d_pos = Field(pad, theme, "Должность")
        self.d_pos.pack(fill="x", pady=(0, theme.sp(3)))
        row3 = hbox(pad, theme)
        self.d_fio = Field(row3, theme, "ФИО")
        self.d_fio.pack(side="left", fill="x", expand=True, padx=(0, theme.sp(3)))
        self.d_phone = Field(row3, theme, "Телефон", width=15, mask="phone")
        self.d_phone.pack(side="left")

        self.territory = Field(pad, theme, "Зона допуска", kind="combobox",
                               values=self._zones_source())
        self.territory.pack(fill="x", pady=(theme.sp(4), 0))
        self.territory.set(default_territory)

        self.plate.bind("<FocusOut>", lambda e: self.autocomplete())
        for widget in self.entries():
            widget.bind("<KeyRelease>", self.on_change, add="+")
        self.territory.bind("<<ComboboxSelected>>", self.on_change, add="+")
        self.territory.bind("<KeyRelease>", self.on_change, add="+")
        self.num.bind("<KeyRelease>", self.on_change, add="+")

    def refresh_suggestions(self):
        try:
            self.territory.widget.configure(values=self._zones_source())
        except Exception:
            pass

    def _force_caps(self, *_args):
        val = self.plate_var.get()
        if val and val != val.upper():
            try:
                pos = self.plate.widget.index(tk.INSERT)
            except Exception:
                pos = None
            self.plate_var.set(val.upper())
            if pos is not None:
                try:
                    self.plate.widget.icursor(pos)
                except Exception:
                    pass
            return
        self.plate.validate()
        self.on_change()

    def _sync_from_peer(self):
        if not self.peer_getter:
            return
        self.num.delete(0, tk.END)
        self.num.insert(0, increment_number(self.peer_getter()))
        self.on_change()

    def entries(self):
        return [self.plate, self.brand, self.type, self.model,
                self.color, self.d_pos, self.d_fio, self.d_phone]

    def autocomplete(self):
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
        # Сброс подсветки ошибок, чтобы чистая форма не была красной
        for widget in self.entries():
            widget.reset_validation()

    def validate_required(self) -> bool:
        return self.plate.validate()