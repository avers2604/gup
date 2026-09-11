"""Составные элементы формы поверх theme.py."""
from __future__ import annotations

import tkinter as tk
import re
from tkinter import ttk

from PIL import ImageTk

from getpass_core.blank import load_logo, load_logo_knockout
from getpass_core.domain import format_phone

from .theme import Theme, field_label, status_dot


def brand_logo(theme: Theme, width: int, knockout: bool = True):
    pil_img = (load_logo_knockout if knockout else load_logo)(theme.px(width))
    if pil_img is None:
        return None
    return ImageTk.PhotoImage(pil_img)


class Field(tk.Frame):
    """Капительная подпись + поле ввода — одна визуальная единица."""

    def __init__(self, parent, theme: Theme, label: str, kind: str = "entry",
                 values=None, width=None, textvariable=None, required=False,
                 mask=None, **kw):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.theme = theme
        self._required = required
        self._label_widget = field_label(self, theme, label)
        self._base_text = label
        self._label_widget.pack(fill="x")

        if kind == "combobox":
            self.widget = ttk.Combobox(self, style="Field.TCombobox",
                                       values=values or [], textvariable=textvariable)
        else:
            self.widget = ttk.Entry(self, style="Field.TEntry", textvariable=textvariable,
                                    **{k: v for k, v in kw.items() if k in ("font", "show")})
        if width:
            self.widget.configure(width=width)
        self.widget.pack(fill="x", pady=(theme.px(2), 0))
        if required:
            self._mark_label()
        self.widget.bind("<KeyRelease>", lambda e: self.validate(), add="+")
        self.widget.bind("<FocusOut>", lambda e: self.validate(), add="+")
        if mask == "phone":
            validate = self.widget.register(self._valid_phone_input)
            self.widget.configure(validate="key", validatecommand=(validate, "%P"))
            self.widget.bind("<KeyRelease>", self._format_phone_input, add="+")

    def _mark_label(self):
        self._label_widget.config(text=f"{self._base_text.upper()} *")

    @staticmethod
    def _valid_phone_input(proposed):
        allowed = set("0123456789+()- ")
        digits = re.sub(r"\D", "", proposed)
        maximum = 11 if proposed.strip().startswith(("+7", "8")) else 10
        return all(char in allowed for char in proposed) and len(digits) <= maximum

    def _format_phone_input(self, _event=None):
        if getattr(self, "_formatting", False):
            return
        current = self.get()
        formatted = format_phone(current)
        if current == formatted:
            return
        self._formatting = True
        try:
            self.widget.delete(0, tk.END)
            self.widget.insert(0, formatted)
            self.widget.icursor(tk.END)
        finally:
            self._formatting = False

    def get(self):
        return self.widget.get()

    def set(self, value):
        if isinstance(self.widget, ttk.Combobox):
            self.widget.set(value)
        else:
            self.widget.delete(0, tk.END)
            self.widget.insert(0, value)

    def insert(self, index, value):
        self.widget.insert(index, value)

    def delete(self, first, last=None):
        self.widget.delete(first, last)

    def bind(self, sequence=None, func=None, add=None):
        return self.widget.bind(sequence, func, add)

    def focus(self):
        self.widget.focus()

    def focus_set(self):
        self.widget.focus_set()

    def configure_field(self, **kw):
        self.widget.configure(**kw)

    def is_required(self) -> bool:
        return self._required

    def validate(self) -> bool:
        if self._required and not self.get().strip():
            self.widget.state(["invalid"])
            self._label_widget.config(text=f"{self._base_text.upper()} — заполните поле",
                                      fg=self.theme.c("danger"))
            return False
        self.widget.state(["!invalid"])
        self._label_widget.config(text=self._base_text.upper() + (" *" if self._required else ""),
                                  fg=self.theme.c("ink_muted"))
        return True

    def reset_validation(self):
        """Снять визуальную ошибку без принудительной валидации."""
        try:
            self.widget.state(["!invalid"])
        except Exception:
            pass


class AutocompleteEntry(Field):
    """Поле ввода с выпадающим списком подсказок, отфильтрованным по подстроке."""

    def __init__(self, parent, theme: Theme, label: str, suggestions, **kw):
        super().__init__(parent, theme, label, kind="entry", **kw)
        self._suggestions = suggestions
        self._popup = None
        self._listbox = None
        self.widget.bind("<KeyRelease>", self._on_key, add="+")
        self.widget.bind("<FocusOut>", self._on_focus_out, add="+")
        self.widget.bind("<Down>", self._focus_list, add="+")
        self.widget.bind("<Escape>", lambda e: self._close(), add="+")

    def _on_key(self, event):
        self.validate()
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.get().strip().lower()
        if not text:
            self._close()
            return
        try:
            options = [s for s in self._suggestions() if s]
        except Exception:
            options = []
        matches = [s for s in options if text in s.lower()][:8]
        if not matches or (len(matches) == 1 and matches[0].lower() == text):
            self._close()
            return
        self._show(matches)

    def _show(self, matches):
        th = self.theme
        if self._popup is None:
            self._popup = tk.Toplevel(self.winfo_toplevel())
            self._popup.wm_overrideredirect(True)
            self._popup.configure(bg=th.c("line_strong"))
            self._listbox = tk.Listbox(
                self._popup, bg=th.c("surface"), fg=th.c("ink"),
                selectbackground=th.c("accent_fill"), selectforeground="#FFFFFF",
                font=th.font("body"), highlightthickness=0, bd=0,
                activestyle="none")
            self._listbox.pack(fill="both", expand=True, padx=1, pady=1)
            self._listbox.bind("<<ListboxSelect>>", self._on_pick)
            self._listbox.bind("<Return>", self._on_pick)
            self._listbox.bind("<Escape>", lambda e: self._close())

        self._listbox.delete(0, tk.END)
        for m in matches:
            self._listbox.insert(tk.END, m)

        x = self.widget.winfo_rootx()
        w = max(self.widget.winfo_width(), th.px(160))
        h = min(len(matches), 8) * th.px(24) + th.px(4)
        y = self.widget.winfo_rooty() + self.widget.winfo_height()

        # Если окно подсказок не помещается снизу, открываем его над полем
        try:
            screen_h = self.winfo_screenheight()
            if y + h > screen_h - 10:
                y = max(0, self.widget.winfo_rooty() - h)
        except Exception:
            pass

        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._listbox.configure(height=min(len(matches), 8))
        self._popup.deiconify()
        self._popup.lift()

    def _focus_list(self, _event=None):
        if self._listbox is not None and self._popup is not None:
            self._listbox.focus_set()
            if self._listbox.size():
                self._listbox.selection_set(0)
        return "break"

    def _on_pick(self, _event=None):
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if sel:
            self.set(self._listbox.get(sel[0]))
            self.validate()
        self._close()
        self.widget.focus_set()
        self.widget.icursor(tk.END)

    def _on_focus_out(self, _event=None):
        self.after(150, self._close_if_unfocused)

    def _close_if_unfocused(self):
        try:
            focused = self.winfo_toplevel().focus_get()
            if focused not in (self._listbox, self.widget):
                self._close()
        except Exception:
            self._close()

    def _close(self):
        if self._popup is not None:
            try:
                self._popup.withdraw()
            except Exception:
                pass


class StatusPill(tk.Frame):
    """Точка + подпись состояния."""

    def __init__(self, parent, theme: Theme, text: str, color: str, **kw):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg, **kw)
        status_dot(self, theme, color).pack(side="left", padx=(0, theme.sp(2)))
        tk.Label(self, text=text, bg=bg, fg=theme.c("ink"),
                 font=theme.font("caption")).pack(side="left")


def section_title(parent, theme: Theme, text: str) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=theme.c("ink"),
                    font=theme.font("heading"), anchor="w")


def hint(parent, theme: Theme, text: str, **kw) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=theme.c("ink_faint"),
                    font=theme.font("caption"), justify="left", **kw)


def hbox(parent, theme: Theme, pady=0) -> tk.Frame:
    f = tk.Frame(parent, bg=parent.cget("bg"))
    f.pack(fill="x", pady=pady)
    return f
