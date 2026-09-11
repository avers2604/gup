import sqlite3
import threading
import os

import pytest

from getpass_core.migrations import migrate, SCHEMA_VERSION
from getpass_ui.navigation import Navigation, Section


def test_migrations_are_idempotent_and_create_pending_index():
    conn = sqlite3.connect(":memory:")
    try:
        with conn:
            migrate(conn)
        with conn:
            migrate(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 3
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='issuance_pending'").fetchone()
    finally:
        conn.close()


def test_future_database_not_modified(journal):
    from getpass_core import config
    conn = sqlite3.connect(config.DB_FILE)
    conn.execute("PRAGMA user_version=100")
    conn.close()
    with pytest.raises(ValueError, match="новой"):
        journal.read()
    conn = sqlite3.connect(config.DB_FILE)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 100
    assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
    conn.close()


def test_navigation_extension_without_app_change():
    nav = Navigation()
    called = []
    nav.register(Section("new", "Новый раздел", lambda: called.append(True)))

    class Menu:
        def add_command(self, **kwargs):
            kwargs["command"]()
    nav.populate(Menu())
    assert called == [True]
    with pytest.raises(ValueError):
        nav.register(Section("new", "Другой", lambda: None))


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="GUI display required")
def test_task_keeps_confirmation_on_ui_thread():
    import tkinter as tk
    from getpass_ui.tasks import run_task
    root = tk.Tk()
    root.withdraw()
    ui_thread = threading.get_ident()
    confirmations = []
    try:
        def work(ask):
            assert threading.get_ident() != ui_thread
            return ask()

        def confirm():
            confirmations.append(threading.get_ident())
            return True
        assert run_task(root, work, confirm=confirm)
        assert confirmations == [ui_thread]

        def fail():
            raise ValueError("worker error")
        with pytest.raises(ValueError, match="worker error"):
            run_task(root, fail)
    finally:
        root.destroy()
