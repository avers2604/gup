"""Общие технические утилиты интерфейса (не зависят от палитры)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


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
    """Модальный индикатор с отменой, оформленный текущей темой.

    Используется как контекстный менеджер: окно закрывается в любом случае,
    в том числе при исключении. Раньше упавшая генерация оставляла модальное
    окно с grab_set(), и программа блокировалась насмерть.
    """

    def __init__(self, parent, theme, title, total, first_text="Подготовка..."):
        self.parent = parent
        self.theme = theme
        self.total = max(1, total)
        self.cancelled = False
        th = theme
        self.win = th.toplevel(parent, title, resizable=(False, False))
        w, h = int(460 * th.scale), int(165 * th.scale)
        self.win.geometry(f"{w}x{h}")
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self._label = tk.Label(self.win, text=first_text, bg=th.c("ground"),
                               fg=th.c("ink"), font=th.font("body"))
        self._label.pack(pady=(th.sp(4), th.sp(2)))
        self._bar = ttk.Progressbar(self.win, length=th.px(380), mode="determinate")
        self._bar.pack(pady=th.sp(1))
        ttk.Button(self.win, text="Отмена", command=self.cancel,
                  style="Ghost.TButton").pack(pady=th.sp(2))
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
