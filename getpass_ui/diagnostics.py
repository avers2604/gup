"""Диагностическое окно для оператора и поддержки."""
from __future__ import annotations

import os
import sqlite3
import sys
import tkinter as tk
from contextlib import closing
from tkinter import ttk

from getpass_core import config


def open_diagnostics(parent, theme):
    win = theme.toplevel(parent, "Диагностика", resizable=(True, True))
    win.geometry("760x520")
    text = tk.Text(win, wrap="word", padx=12, pady=12)
    text.pack(fill="both", expand=True)
    rows = [
        ("Версия Python", sys.version.split()[0]),
        ("Каталог данных", config.DATA_DIR),
        ("База данных", config.DB_FILE),
        ("Резервные копии", config.BACKUP_DIR),
        ("Размер БД", f"{os.path.getsize(config.DB_FILE) // 1024} КБ" if os.path.exists(config.DB_FILE) else "нет"),
    ]
    try:
        with closing(sqlite3.connect(config.DB_FILE, timeout=3)) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        rows.append(("Проверка SQLite", result))
    except Exception as exc:
        rows.append(("Проверка SQLite", f"ошибка: {exc}"))
    for key, value in rows:
        text.insert("end", f"{key}: {value}\n")
    text.insert("end", "\nПоследние резервные копии:\n")
    if os.path.isdir(config.BACKUP_DIR):
        names = sorted((n for n in os.listdir(config.BACKUP_DIR) if n.startswith("backup_")), reverse=True)
        text.insert("end", "\n".join(names[:10]) or "нет файлов")
    else:
        text.insert("end", "каталог ещё не создан")
    text.configure(state="disabled")
    ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=8)
