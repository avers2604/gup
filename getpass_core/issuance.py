"""Durable issuance intent. Output failures remain recoverable after restart."""
import json
import os
import shutil
import uuid
from datetime import datetime

from . import config
from .atomic import atomic_output
from .importing import validate_photo

STATE_PREPARED = "prepared"
STATE_CONFIRMED = "confirmed"
STATE_CANCELLED = "cancelled"


def prepare(journal, records, destination):
    operation_id = uuid.uuid4().hex
    conn = journal._connect()
    try:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS issuance_jobs (
                id TEXT PRIMARY KEY, journal TEXT NOT NULL, records_json TEXT NOT NULL,
                destination TEXT NOT NULL, created_at TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'prepared')''')
            for record in records:
                record.setdefault("id", uuid.uuid4().hex)
                if record.get("photo_path"):
                    source = os.path.abspath(record["photo_path"])
                    validate_photo(source)
                    photo_root = os.path.abspath(config.PHOTO_DIR)
                    if os.path.dirname(source) != photo_root:
                        os.makedirs(photo_root, exist_ok=True)
                        destination_photo = os.path.join(
                            photo_root,
                            uuid.uuid4().hex + os.path.splitext(source)[1],
                        )
                        with atomic_output(destination_photo) as temporary:
                            shutil.copyfile(source, temporary)
                        record["photo_path"] = destination_photo
            conn.execute(
                "INSERT INTO issuance_jobs (id, journal, records_json, destination, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    operation_id,
                    journal.schema.table,
                    json.dumps(records, ensure_ascii=False),
                    destination,
                    datetime.now().astimezone().isoformat(),
                ),
            )
    finally:
        conn.close()
    return operation_id


def cancel(journal, operation_id):
    """Mark a prepared issuance as cancelled so it cannot be confirmed later."""
    conn = journal._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            job = conn.execute(
                "SELECT state FROM issuance_jobs WHERE id=? AND journal=?",
                (operation_id, journal.schema.table),
            ).fetchone()
            if job is None:
                raise ValueError("Операция не найдена")
            if job["state"] == STATE_CANCELLED:
                return
            if job["state"] == STATE_CONFIRMED:
                raise ValueError("Подтверждённую выдачу нельзя отменить")
            conn.execute(
                "UPDATE issuance_jobs SET state=? WHERE id=? AND journal=?",
                (STATE_CANCELLED, operation_id, journal.schema.table),
            )
    finally:
        conn.close()


def confirm(journal, operation_id):
    conn = journal._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            job = conn.execute(
                "SELECT * FROM issuance_jobs WHERE id=? AND journal=?",
                (operation_id, journal.schema.table),
            ).fetchone()
            if job is None:
                raise ValueError("Операция не найдена")
            if job["state"] == STATE_CONFIRMED:
                return
            if job["state"] == STATE_CANCELLED:
                raise ValueError("Операция отменена и не может быть подтверждена")
            records = json.loads(job["records_json"])
            prepared = []
            for record in records:
                record["status"] = "действует"
                if "plate" in journal.schema.keys:
                    record["zone"] = (
                        record.get("territory")
                        or record.get("zone")
                        or "Основная (Без зоны)"
                    )
                    record["driver"] = record.get(
                        "driver_full", record.get("driver", "")
                    )
                prepared.append(record)
            journal._insert_all(conn, prepared)
            for record in prepared:
                journal._event(conn, "issued", {}, record)
            conn.execute(
                "UPDATE issuance_jobs SET state=? WHERE id=?",
                (STATE_CONFIRMED, operation_id),
            )
    finally:
        conn.close()


def pending(journal):
    conn = journal._connect()
    try:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='issuance_jobs'"
        ).fetchone():
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM issuance_jobs WHERE journal=? AND state=? ORDER BY created_at",
                (journal.schema.table, STATE_PREPARED),
            )
        ]
    finally:
        conn.close()
