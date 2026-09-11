"""Durable issuance intent. Output failures remain recoverable after restart."""
import json
import logging
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
_OWNED_PHOTO_KEY = "_issuance_owned_photo"

logger = logging.getLogger(__name__)


def _is_owned_photo_path(path):
    try:
        root = os.path.normcase(os.path.abspath(config.PHOTO_DIR))
        candidate = os.path.normcase(os.path.abspath(path))
        return os.path.commonpath((root, candidate)) == root
    except (OSError, ValueError, TypeError):
        return False


def _remove_owned_photos(records):
    for record in records:
        if not record.get(_OWNED_PHOTO_KEY):
            continue
        path = record.get("photo_path")
        if not path or not _is_owned_photo_path(path):
            logger.warning("Пропущено удаление недоверенного пути служебного фото: %r", path)
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            logger.warning("Не удалось удалить служебную копию фото %s", path, exc_info=True)


def _prepare_records(records):
    prepared = []
    try:
        for original in records:
            record = dict(original)
            record.setdefault("id", uuid.uuid4().hex)
            if record.get("photo_path"):
                source = os.path.abspath(record["photo_path"])
                validate_photo(source)
                photo_root = os.path.abspath(config.PHOTO_DIR)
                if os.path.normcase(os.path.dirname(source)) != os.path.normcase(photo_root):
                    os.makedirs(photo_root, exist_ok=True)
                    destination_photo = os.path.join(
                        photo_root,
                        uuid.uuid4().hex + os.path.splitext(source)[1],
                    )
                    with atomic_output(destination_photo) as temporary:
                        shutil.copyfile(source, temporary)
                    record["photo_path"] = destination_photo
                    record[_OWNED_PHOTO_KEY] = True
            prepared.append(record)
    except BaseException:
        _remove_owned_photos(prepared)
        raise
    return prepared


def prepare(journal, records, destination):
    operation_id = uuid.uuid4().hex
    prepared = []
    conn = None
    try:
        prepared = _prepare_records(records)
        payload = json.dumps(prepared, ensure_ascii=False)
        conn = journal._connect()
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS issuance_jobs (
                id TEXT PRIMARY KEY, journal TEXT NOT NULL, records_json TEXT NOT NULL,
                destination TEXT NOT NULL, created_at TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'prepared')''')
            conn.execute(
                "INSERT INTO issuance_jobs (id, journal, records_json, destination, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    operation_id,
                    journal.schema.table,
                    payload,
                    destination,
                    datetime.now().astimezone().isoformat(),
                ),
            )
    except BaseException:
        _remove_owned_photos(prepared)
        raise
    finally:
        if conn is not None:
            conn.close()
    return operation_id


def cancel(journal, operation_id):
    """Mark a prepared issuance as cancelled so it cannot be confirmed later."""
    conn = journal._connect()
    records = []
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            job = conn.execute(
                "SELECT state, records_json FROM issuance_jobs WHERE id=? AND journal=?",
                (operation_id, journal.schema.table),
            ).fetchone()
            if job is None:
                raise ValueError("Операция не найдена")
            if job["state"] == STATE_CONFIRMED:
                raise ValueError("Подтверждённую выдачу нельзя отменить")
            records = json.loads(job["records_json"])
            if job["state"] != STATE_CANCELLED:
                if job["state"] != STATE_PREPARED:
                    raise ValueError(f"Недопустимое состояние операции: {job['state']}")
                conn.execute(
                    "UPDATE issuance_jobs SET state=? WHERE id=? AND journal=?",
                    (STATE_CANCELLED, operation_id, journal.schema.table),
                )
    finally:
        conn.close()
    _remove_owned_photos(records)


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
            if job["state"] != STATE_PREPARED:
                raise ValueError(f"Недопустимое состояние операции: {job['state']}")
            records = json.loads(job["records_json"])
            prepared = []
            for record in records:
                record.pop(_OWNED_PHOTO_KEY, None)
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
