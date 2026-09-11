"""Recovery and inspection of durable issuance operations."""
import os
from tkinter import ttk, messagebox
from getpass_core import issuance
from getpass_core.storage import PASS_JOURNAL, BADGE_JOURNAL


def open_operations(parent, theme):
    win = theme.toplevel(parent, "Незавершённые выдачи")
    win.geometry("1000x550")
    ttk.Label(win, text="Операции сохраняются до печати. Подтверждайте выдачу после проверки документа.").pack(pady=12)
    tree = ttk.Treeview(win, columns=("created", "journal", "destination"), show="headings")
    for key, label in (("created", "Создана"), ("journal", "Журнал"), ("destination", "Файл / принтер")):
        tree.heading(key, text=label)
        tree.column(key, width=250)
    tree.pack(fill="both", expand=True, padx=12)
    jobs = {}
    def refresh():
        tree.delete(*tree.get_children())
        jobs.clear()
        for journal in (PASS_JOURNAL, BADGE_JOURNAL):
            for job in issuance.pending(journal):
                jobs[job["id"]] = (journal, job)
                tree.insert("", "end", iid=job["id"], values=(job["created_at"], journal.schema.name, job["destination"]))
    def confirm():
        if not tree.selection():
            return
        if not messagebox.askyesno("Подтвердить выдачу", "Документы действительно выданы? Записать их в журнал?", parent=win):
            return
        try:
            for key in tree.selection():
                issuance.confirm(jobs[key][0], key)
            refresh()
        except Exception as exc:
            messagebox.showerror("Не удалось подтвердить", str(exc), parent=win)
    def open_file():
        if not tree.selection():
            return
        path = jobs[tree.selection()[0]][1]["destination"]
        if os.path.isfile(path) and path.lower().endswith((".pdf", ".jpg", ".png")):
            os.startfile(path)
        else:
            messagebox.showinfo("Файл недоступен", "Документ не сохранён. Повторите подготовку по данным операции.", parent=win)
    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=12, pady=12)
    ttk.Button(bar, text="Обновить", command=refresh).pack(side="left")
    ttk.Button(bar, text="Открыть документ", command=open_file).pack(side="left", padx=8)
    ttk.Button(bar, text="Подтвердить выдачу", command=confirm).pack(side="right")
    refresh()
