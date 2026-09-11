"""Ordered schema migrations, committed together with journal initialization."""
from datetime import datetime

SCHEMA_VERSION = 3


def migrate(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise ValueError("База создана более новой версией программы")
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    if version < 1:
        conn.execute('''CREATE TABLE IF NOT EXISTS journal_events (
            event_id INTEGER PRIMARY KEY, journal TEXT NOT NULL, record_id TEXT NOT NULL,
            action TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL,
            before_json TEXT NOT NULL, after_json TEXT NOT NULL)''')
    if version < 2:
        for operation in ("UPDATE", "DELETE"):
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS events_no_{operation.lower()}
                BEFORE {operation} ON journal_events BEGIN
                SELECT RAISE(ABORT, 'Journal events are immutable'); END''')
    if version < 3:
        conn.execute('''CREATE TABLE IF NOT EXISTS issuance_jobs (
            id TEXT PRIMARY KEY, journal TEXT NOT NULL, records_json TEXT NOT NULL,
            destination TEXT NOT NULL, created_at TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'prepared')''')
        conn.execute("CREATE INDEX IF NOT EXISTS issuance_pending ON issuance_jobs(journal, state, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS events_record ON journal_events(journal, record_id, event_id)")
    for number in range(version + 1, SCHEMA_VERSION + 1):
        conn.execute("INSERT INTO schema_migrations VALUES (?, ?)",
                     (number, datetime.now().astimezone().isoformat()))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
