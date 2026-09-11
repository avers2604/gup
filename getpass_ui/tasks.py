"""Worker execution; all Tk calls and completion handling stay on the UI thread."""
import queue
import threading
from tkinter import ttk


def run_task(parent, work, title="Выполнение операции", confirm=None, cancelled=None):
    import tkinter as tk
    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)
    ttk.Label(window, text=title, padding=20).pack()
    bar = ttk.Progressbar(window, mode="indeterminate", length=320)
    bar.pack(padx=20, pady=20)
    bar.start()
    window.protocol("WM_DELETE_WINDOW", lambda: None)
    if cancelled is not None:
        def cancel():
            cancelled.set()
            button.configure(state="disabled", text="Отмена запрошена…")
        button = ttk.Button(window, text="Отмена", command=cancel)
        button.pack(pady=10)
        window.protocol("WM_DELETE_WINDOW", cancel)
    window.grab_set()
    messages = queue.Queue()
    reply = queue.Queue()
    outcome = []

    def ask():
        messages.put(("confirm", None))
        return reply.get()

    def worker():
        try:
            value = work(ask) if confirm else work()
            messages.put(("done", value))
        except BaseException as exc:
            messages.put(("error", exc))

    def poll():
        try:
            kind, value = messages.get_nowait()
        except queue.Empty:
            window.after(50, poll)
            return
        if kind == "confirm":
            try:
                reply.put(bool(confirm()))
            except Exception:
                reply.put(False)
            window.after(50, poll)
            return
        outcome.append((kind, value))
        bar.stop()
        window.grab_release()
        window.destroy()

    threading.Thread(target=worker, daemon=False).start()
    window.after(50, poll)
    parent.wait_window(window)
    if not outcome:
        raise RuntimeError("Окно закрыто до завершения операции")
    kind, value = outcome[0]
    if kind == "error":
        raise value
    return value
