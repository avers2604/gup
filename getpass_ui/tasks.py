"""Worker execution; all Tk calls and completion handling stay on the UI thread."""
import queue
import threading
from tkinter import ttk


class _TaskState:
    def __init__(self, work, confirm):
        self.work = work
        self.confirm = confirm
        self.messages = queue.Queue()
        self.reply = queue.Queue()
        self.outcome = []

    def ask(self):
        self.messages.put(("confirm", None))
        return self.reply.get()

    def worker(self):
        try:
            value = self.work(self.ask) if self.confirm else self.work()
            self.messages.put(("done", value))
        except BaseException as exc:
            self.messages.put(("error", exc))

    def handle(self, kind, value, window, bar) -> bool:
        if kind == "confirm":
            try:
                self.reply.put(bool(self.confirm()))
            except Exception:
                self.reply.put(False)
            return False
        self.outcome.append((kind, value))
        bar.stop()
        window.grab_release()
        window.destroy()
        return True

    def poll(self, window, bar):
        try:
            kind, value = self.messages.get_nowait()
        except queue.Empty:
            window.after(50, lambda: self.poll(window, bar))
            return
        if not self.handle(kind, value, window, bar):
            window.after(50, lambda: self.poll(window, bar))


def _build_task_window(parent, title):
    import tkinter as tk

    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)
    ttk.Label(window, text=title, padding=20).pack()
    bar = ttk.Progressbar(window, mode="indeterminate", length=320)
    bar.pack(padx=20, pady=20)
    bar.start()
    window.protocol("WM_DELETE_WINDOW", lambda: None)
    return window, bar


def _configure_cancellation(window, cancelled):
    if cancelled is None:
        return
    button = ttk.Button(window, text="Отмена")

    def cancel():
        cancelled.set()
        button.configure(state="disabled", text="Отмена запрошена…")

    button.configure(command=cancel)
    button.pack(pady=10)
    window.protocol("WM_DELETE_WINDOW", cancel)


def _task_result(outcome):
    if not outcome:
        raise RuntimeError("Окно закрыто до завершения операции")
    kind, value = outcome[0]
    if kind == "error":
        raise value
    return value


def run_task(parent, work, title="Выполнение операции", confirm=None, cancelled=None):
    window, bar = _build_task_window(parent, title)
    _configure_cancellation(window, cancelled)
    window.grab_set()

    state = _TaskState(work, confirm)
    threading.Thread(target=state.worker, daemon=False).start()
    window.after(50, lambda: state.poll(window, bar))
    parent.wait_window(window)
    return _task_result(state.outcome)
