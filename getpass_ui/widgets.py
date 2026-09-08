"""Общие элементы интерфейса."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from getpass_core.fonts import ui_family

CLR_NAVY = "#0A2540"
CLR_TEAL = "#009FA0"
CLR_RED = "#D6204B"
CLR_BG = "#EEF2F6"
CLR_CARD = "#FFFFFF"


def F(size, bold=False, italic=False):
    style = (("bold " if bold else "") + ("italic" if italic else "")).strip()
    family = ui_family()
    return (family, size, style) if style else (family, size)


def make_scrollable(parent, bg_color):
    """Прокручиваемая область: рамка -> холст -> внутренняя рамка с формой."""
    wrapper = tk.Frame(parent, bg=bg_color)
    # ВАЖНО: без этого wrapper остаётся неуправляемым (1x1, не отображён),
    # и вся форма внутри холста не видна на экране
    wrapper.pack(fill="both", expand=True)
    canvas = tk.Canvas(wrapper, bg=bg_color, highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=bg_color)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_resize(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_resize(event):
        # внутренняя рамка должна занимать всю ширину холста, иначе поля,
        # разложенные через fill="x", схлопываются до собственной ширины
        canvas.itemconfigure(window_id, width=event.width)
        canvas.configure(scrollregion=canvas.bbox("all"))

    inner.bind("<Configure>", _on_inner_resize)
    canvas.bind("<Configure>", _on_canvas_resize)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return wrapper, canvas, inner


class Debouncer:
    """Откладывает вызов, схлопывая частые события (ввод, перерисовку)."""

    def __init__(self, widget, callback, default_delay=150):
        self._widget = widget
        self._callback = callback
        self._delay = default_delay
        self._job = None
        self._alive = True
        # без этого отложенный вызов срабатывает уже после закрытия окна
        # и Tk ругается «invalid command name»
        try:
            widget.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self._widget:
            return
        self._alive = False
        self.cancel()

    def schedule(self, *_args, delay=None):
        if not self._alive:
            return
        try:
            if self._job is not None:
                self._widget.after_cancel(self._job)
            self._job = self._widget.after(delay or self._delay, self._fire)
        except Exception:
            self._job = None

    def _fire(self):
        self._job = None
        if not self._alive:
            return
        try:
            self._callback()
        except Exception:
            pass

    def cancel(self):
        if self._job is not None:
            try:
                self._widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


class ProgressDialog:
    """Модальный индикатор с отменой.

    Используется как контекстный менеджер: окно закрывается в любом случае,
    в том числе при исключении. Раньше упавшая генерация оставляла модальное
    окно с grab_set(), и программа блокировалась насмерть.
    """

    def __init__(self, parent, title, total, first_text="Подготовка..."):
        self.parent = parent
        self.total = max(1, total)
        self.cancelled = False
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("460x165")
        self.win.transient(parent)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self._label = ttk.Label(self.win, text=first_text, font=F(10))
        self._label.pack(pady=(16, 8))
        self._bar = ttk.Progressbar(self.win, length=380, mode="determinate")
        self._bar.pack(pady=4)
        self._btn = tk.Button(self.win, text="Отмена", command=self.cancel,
                              bg="#B0BEC5", relief="flat", padx=16, pady=4,
                              cursor="hand2", font=F(9))
        self._btn.pack(pady=8)
        try:
            self.win.grab_set()
        except Exception:
            pass
        self.win.update()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def cancel(self):
        self.cancelled = True
        self._label.config(text="Прерывание...")
        try:
            self.win.update_idletasks()
        except Exception:
            pass

    def step(self, done, text=""):
        self._bar["value"] = min(100.0, (done / self.total) * 100)
        if text:
            self._label.config(text=text)
        try:
            # update_idletasks вместо update(): перерисовка без повторного
            # входа в обработчики, иначе клик по кнопке запускал вложенную
            # генерацию поверх текущей
            self.win.update_idletasks()
            self.win.update()
        except Exception:
            pass

    def close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


def styled_button(parent, text, command, bg, fg="white", font=None, **kw):
    opts = dict(bg=bg, fg=fg, relief="flat", cursor="hand2",
                font=font or F(9, True))
    opts.update(kw)
    return tk.Button(parent, text=text, command=command, **opts)
