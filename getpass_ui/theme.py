"""Движок оформления: превращает токены брендбука в виджеты Tkinter.

Скругления в ttk делаются 9-patch изображениями, которые Pillow рисует при
запуске под текущий масштаб экрана. Родных скруглений в Tk нет, но такой
приём даёт настоящие скруглённые кнопки, поля и списки без смены технологии.

Модуль зависит только от tkinter и Pillow — его можно перенести в другую
программу вместе с tokens.py.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .tokens import (FONT_STACK, PALETTES, RADIUS, SPACE, TYPE, Palette,
                     lighten)

#: Размер заготовки 9-patch. Реальный виджет растягивается из неё.
_PATCH_W, _PATCH_H = 96, 44


class Theme:
    """Оформление одного окна Tk: палитра, шрифты, стили ttk."""

    def __init__(self, root: tk.Misc, palette: str | Palette = "light",
                 scale: float = 1.0, family: str | None = None):
        self.root = root
        self.palette = PALETTES[palette] if isinstance(palette, str) else palette
        self.scale = max(0.5, min(scale, 4.0))
        self.family = family or self._pick_family()
        self._images: list = []          # ссылки на PhotoImage, иначе Tk их соберёт
        self._elements: set[str] = set()
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._build_styles()

    # ─────────────────────────────── основы

    def _pick_family(self) -> str:
        try:
            available = {f.lower() for f in tkfont.families(self.root)}
        except Exception:
            return "Segoe UI"
        for name in FONT_STACK:
            if name.lower() in available:
                return name
        return "Segoe UI"

    def px(self, value: int) -> int:
        """Пиксели с поправкой на масштаб экрана."""
        return int(round(value * self.scale))

    def sp(self, step: int) -> int:
        """Отступ по сетке 4 px: sp(4) → 16 px при масштабе 100%."""
        return self.px(SPACE[max(0, min(step, len(SPACE) - 1))])

    def font(self, role: str = "body", bold: bool | None = None):
        size, weight = TYPE.get(role, TYPE["body"])
        if bold is not None:
            weight = "bold" if bold else "normal"
        return (self.family, size, weight) if weight != "normal" else (self.family, size)

    def c(self, name: str) -> str:
        """Цвет по имени токена."""
        return getattr(self.palette, name)

    @property
    def is_dark(self) -> bool:
        return self.palette.name == "dark"

    # ─────────────────────────── 9-patch элементы

    def _rounded(self, radius: int, fill: str, outline: str | None = None,
                 width: int = 0) -> ImageTk.PhotoImage:
        w, h = self.px(_PATCH_W), self.px(_PATCH_H)
        r = self.px(radius)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, w - 1, h - 1], radius=r, fill=fill, outline=outline, width=width)
        photo = ImageTk.PhotoImage(img)
        self._images.append(photo)
        return photo

    def _element(self, name: str, default, *states, radius: int, padding):
        """Создать image-элемент ttk; повторное создание в одном Tk запрещено."""
        if name in self._elements:
            return
        try:
            self.style.element_create(name, "image", default, *states,
                                      border=self.px(radius) + 2, sticky="nsew",
                                      padding=padding)
            self._elements.add(name)
        except tk.TclError:
            pass

    def _button(self, style_name: str, fill: str, hover: str, fg: str,
                radius: int = RADIUS["button"], pad=(18, 10), role="body",
                border: str | None = None):
        element = f"{style_name}.fill"
        self._element(
            element,
            self._rounded(radius, fill, border, 1 if border else 0),
            ("pressed", self._rounded(radius, hover, border, 1 if border else 0)),
            ("active", self._rounded(radius, hover, border, 1 if border else 0)),
            ("disabled", self._rounded(radius, self.c("surface_alt"),
                                       self.c("line"), 1)),
            radius=radius,
            padding=(self.px(pad[0]), self.px(pad[1])))
        self.style.layout(style_name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [
                ("Button.label", {"sticky": "nsew"})]})]})])
        self.style.configure(style_name, foreground=fg, anchor="center",
                             font=self.font(role, bold=True),
                             background=self.c("surface"), borderwidth=0)
        self.style.map(style_name,
                       foreground=[("disabled", self.c("ink_faint")), ("active", fg)])

    def _input(self, style_name: str, widget: str, radius: int = RADIUS["field"]):
        element = f"{style_name}.fill"
        self._element(
            element,
            self._rounded(radius, self.c("surface"), self.c("line_strong"), 1),
            ("focus", self._rounded(radius, self.c("surface"), self.c("focus"), 2)),
            ("invalid", self._rounded(radius, self.c("surface"), self.c("danger"), 2)),
            ("disabled", self._rounded(radius, self.c("surface_alt"),
                                       self.c("line"), 1)),
            radius=radius,
            padding=(self.px(11), self.px(8)))
        children = [(f"{widget}.padding", {"sticky": "nsew", "children": [
            (f"{widget}.textarea", {"sticky": "nsew"})]})]
        if widget == "Combobox":
            # свой 9-patch layout заменяет весь Combobox.field целиком и по
            # умолчанию теряет стрелку раскрытия списка — возвращаем её
            # явным элементом, иначе поле не отличить от обычного текстового
            children.insert(0, (f"{widget}.downarrow", {"side": "right", "sticky": "ns"}))
        self.style.layout(style_name, [(element, {"sticky": "nsew", "children": children})])
        self.style.configure(style_name, foreground=self.c("ink"),
                             fieldbackground=self.c("surface"),
                             insertcolor=self.c("ink"), font=self.font("body"),
                             arrowsize=self.px(13), background=self.c("surface"),
                             arrowcolor=self.c("ink_muted"))
        if widget == "Combobox":
            self.style.map(style_name, arrowcolor=[("disabled", self.c("ink_faint"))])

    # ───────────────────────────── набор стилей

    def _build_styles(self):
        p = self.palette
        base = {"background": p.surface, "foreground": p.ink,
                "font": self.font("body")}
        self.style.configure(".", **base)
        self.style.configure("TFrame", background=p.surface)
        self.style.configure("Ground.TFrame", background=p.ground)
        self.style.configure("TLabel", background=p.surface, foreground=p.ink)
        self.style.configure("Muted.TLabel", background=p.surface,
                             foreground=p.ink_muted, font=self.font("caption"))
        self.style.configure("FieldLabel.TLabel", background=p.surface,
                             foreground=p.ink_muted, font=self.font("label"))
        self.style.configure("Heading.TLabel", background=p.surface,
                             foreground=p.ink, font=self.font("heading"))
        self.style.configure("Title.TLabel", background=p.surface,
                             foreground=p.ink, font=self.font("title"))

        self._button("Accent.TButton", p.accent_fill, p.accent_fill_hover,
                     p.on_primary if not self.is_dark else p.on_accent)
        self._button("Primary.TButton", p.primary, p.primary_hover, p.on_primary)
        self._button("Ghost.TButton", p.surface_alt,
                     lighten(p.surface_alt, 0.06) if not self.is_dark
                     else p.line, p.ink, border=p.line_strong, pad=(16, 9))
        self._button("Danger.TButton", p.danger, lighten(p.danger, 0.12), "#FFFFFF")

        self._input("Field.TEntry", "Entry")
        self._input("Field.TCombobox", "Combobox")
        self.style.map("Field.TCombobox",
                       fieldbackground=[("readonly", p.surface)],
                       foreground=[("readonly", p.ink)])

        self.style.configure("Treeview", background=p.surface,
                             fieldbackground=p.surface, foreground=p.ink,
                             rowheight=self.px(28), borderwidth=0,
                             font=self.font("body"))
        self.style.configure("Treeview.Heading", background=p.surface_alt,
                             foreground=p.ink_muted, font=self.font("label"),
                             relief="flat", padding=(self.px(8), self.px(7)))
        self.style.map("Treeview", background=[("selected", p.accent_fill)],
                       foreground=[("selected", "#FFFFFF")])
        self.style.map("Treeview.Heading", background=[("active", p.line)])

        self.style.configure("TScrollbar", background=p.surface_alt,
                             troughcolor=p.ground, borderwidth=0, arrowsize=self.px(12))
        self.style.configure("TSeparator", background=p.line)
        self.style.configure("TProgressbar", background=p.accent,
                             troughcolor=p.surface_alt, borderwidth=0)
        self.style.configure("TCheckbutton", background=p.surface, foreground=p.ink,
                             font=self.font("body"))
        self.style.map("TCheckbutton", background=[("active", p.surface)])
        self.style.configure("Warning.TCheckbutton", background=p.surface,
                             foreground=p.danger, font=self.font("body", bold=True))
        self.style.map("Warning.TCheckbutton", background=[("active", p.surface)])
        self.style.configure("TRadiobutton", background=p.surface, foreground=p.ink,
                             font=self.font("body"))
        self.style.map("TRadiobutton", background=[("active", p.surface)])

        # вкладки: главный переключатель разделов программы
        self.style.configure("TNotebook", background=p.ground, borderwidth=0,
                             tabmargins=(0, 0, 0, 0))
        self.style.configure("TNotebook.Tab", background=p.surface_alt,
                             foreground=p.ink_muted, font=self.font("body", bold=True),
                             padding=(self.px(20), self.px(10)), borderwidth=0)
        self.style.map("TNotebook.Tab",
                       background=[("selected", p.primary), ("active", p.line)],
                       foreground=[("selected", p.on_primary), ("active", p.ink)])

        # вложенные вкладки внутри карточки (Пропуск №1 / №2)
        self.style.configure("Inner.TNotebook", background=p.surface, borderwidth=0)
        self.style.configure("Inner.TNotebook.Tab", background=p.surface_alt,
                             foreground=p.ink_muted, font=self.font("caption", bold=True),
                             padding=(self.px(14), self.px(7)), borderwidth=0)
        self.style.map("Inner.TNotebook.Tab",
                       background=[("selected", p.accent_fill), ("active", p.line)],
                       foreground=[("selected", "#FFFFFF"), ("active", p.ink)])

        # попап списка Combobox — не подчиняется ttk-стилям напрямую
        self.root.option_add("*TCombobox*Listbox.background", p.surface)
        self.root.option_add("*TCombobox*Listbox.foreground", p.ink)
        self.root.option_add("*TCombobox*Listbox.selectBackground", p.accent_fill)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.root.option_add("*TCombobox*Listbox.font", self.font("body"))

    # ───────────────────────────── утилиты окон

    def apply_window(self, window: tk.Misc) -> None:
        try:
            window.configure(bg=self.palette.ground)
        except tk.TclError:
            pass

    def toplevel(self, parent: tk.Misc, title: str, resizable=(True, True)) -> tk.Toplevel:
        """Дочернее окно на полотне текущей темы, привязанное к владельцу."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=self.palette.ground)
        win.resizable(*resizable)
        win.transient(parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent)
        return win

    def check(self, parent, text, variable, style="TCheckbutton", **kw):
        return ttk.Checkbutton(parent, text=text, variable=variable,
                               style=style, **kw)

    def radio(self, parent, text, variable, value, style="TRadiobutton", **kw):
        return ttk.Radiobutton(parent, text=text, variable=variable, value=value,
                               style=style, **kw)


class Card(tk.Frame):
    """Карточка со скруглением и рамкой. Содержимое кладут в `.body`."""

    def __init__(self, parent, theme: Theme, radius: int = RADIUS["card"],
                 pad: int = 5, fill: str | None = None, **kw):
        self.theme = theme
        self._fill = fill or theme.c("surface")
        self._radius = radius
        self._pad = theme.sp(pad)
        super().__init__(parent, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, **kw)
        self._canvas = tk.Canvas(self, bg=parent.cget("bg"),
                                 highlightthickness=0, bd=0)
        self._canvas.place(relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=self._fill)
        self.body.place(x=self._pad, y=self._pad, relwidth=1, relheight=1,
                        width=-2 * self._pad, height=-2 * self._pad)
        self._image = None
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, w - 1, h - 1], radius=self.theme.px(self._radius),
            fill=self._fill, outline=self.theme.c("line"), width=1)
        self._image = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, image=self._image, anchor="nw")
        tk.Misc.lower(self._canvas)

    def fit(self) -> None:
        """Подогнать высоту под содержимое."""
        self.body.update_idletasks()
        self.configure(height=self.body.winfo_reqheight() + 2 * self._pad)


def field_label(parent, theme: Theme, text: str) -> tk.Label:
    """Капительная подпись поля."""
    return tk.Label(parent, text=text.upper(), bg=parent.cget("bg"),
                    fg=theme.c("ink_muted"), font=theme.font("label"), anchor="w")


def status_dot(parent, theme: Theme, color: str, size: int = 8) -> tk.Canvas:
    """Точка состояния: форма несёт смысл наравне с цветом."""
    d = theme.px(size)
    canvas = tk.Canvas(parent, width=d, height=d, bg=parent.cget("bg"),
                       highlightthickness=0, bd=0)
    canvas.create_oval(0, 0, d - 1, d - 1, fill=color, outline="")
    return canvas
