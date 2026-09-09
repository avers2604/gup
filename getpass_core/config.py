"""Пути, каталог данных и настройки."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

APP_NAME = "GET-Passes"

# Базовый каталог приложения
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
    # В режиме PyInstaller --onefile ресурсы распаковываются в _MEIPASS
    BUNDLE_DIR = getattr(sys, "_MEIPASS", SCRIPT_DIR)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    SCRIPT_DIR = os.path.dirname(SCRIPT_DIR)  # подняться из getpass_core/
    BUNDLE_DIR = SCRIPT_DIR

_FONT_DIR_NAMES = ("fonts", "fronts")


def _resolve_fonts_dir() -> str:
    for base in (BUNDLE_DIR, SCRIPT_DIR):
        for name in _FONT_DIR_NAMES:
            candidate = os.path.join(base, name)
            if os.path.isdir(candidate):
                return candidate
    return os.path.join(SCRIPT_DIR, "fonts")


FONTS_DIR = _resolve_fonts_dir()
TEMPLATE_FILE = os.path.join(BUNDLE_DIR, "template.png")
if not os.path.exists(TEMPLATE_FILE):
    TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "template.png")

ICON_FILE = os.path.join(BUNDLE_DIR, "app_icon.ico")
if not os.path.exists(ICON_FILE):
    ICON_FILE = os.path.join(SCRIPT_DIR, "app_icon.ico")


def _is_writable(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".wtest", delete=True):
            return True
    except Exception:
        return False


def _user_data_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_NAME)


_LEGACY_NAMES = (
    "settings.json", "журнал_пропусков.csv", "журнал_пропусков.xlsx",
    "журнал_бейджей.csv", "журнал_бейджей.xlsx", "cars_database.json",
)


def resolve_data_dir() -> str:
    local_data = os.path.join(SCRIPT_DIR, "data")
    if os.path.isdir(local_data) and _is_writable(local_data):
        return local_data

    legacy_present = any(os.path.exists(os.path.join(SCRIPT_DIR, n)) for n in _LEGACY_NAMES)
    if legacy_present and _is_writable(SCRIPT_DIR):
        return SCRIPT_DIR

    if _is_writable(SCRIPT_DIR) and not legacy_present:
        try:
            os.makedirs(local_data, exist_ok=True)
            return local_data
        except Exception:
            pass

    user_dir = _user_data_dir()
    try:
        os.makedirs(user_dir, exist_ok=True)
    except Exception:
        return SCRIPT_DIR
    if legacy_present:
        for n in _LEGACY_NAMES:
            src, dst = os.path.join(SCRIPT_DIR, n), os.path.join(user_dir, n)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
    return user_dir


DATA_DIR = resolve_data_dir()
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")
DB_FILE = os.path.join(DATA_DIR, "gup.sqlite3")
LOG_CSV_FILE = os.path.join(DATA_DIR, "журнал_пропусков.csv")
LOG_XLSX_FILE = os.path.join(DATA_DIR, "журнал_пропусков.xlsx")
BADGE_LOG_CSV = os.path.join(DATA_DIR, "журнал_бейджей.csv")
BADGE_LOG_XLSX = os.path.join(DATA_DIR, "журнал_бейджей.xlsx")
CARS_CACHE_FILE = os.path.join(DATA_DIR, "cars_database.json")
CRASH_LOG_FILE = os.path.join(DATA_DIR, "crash.log")


def harden_data_dir() -> bool:
    marker = os.path.join(DATA_DIR, ".acl_applied")
    if os.path.exists(marker):
        return True
    ok = False
    try:
        if os.name == "nt":
            user = os.environ.get("USERNAME", "")
            if user:
                # *S-1-5-32-544 — универсальный SID группы встроенных Администраторов
                res = subprocess.run(
                    ["icacls", DATA_DIR, "/inheritance:r",
                     "/grant:r", f"{user}:(OI)(CI)F",
                     "/grant:r", "*S-1-5-32-544:(OI)(CI)F"],
                    creationflags=0x08000000, capture_output=True, timeout=15,
                )
                ok = (res.returncode == 0)
        else:
            os.chmod(DATA_DIR, 0o700)
            ok = True
    except Exception:
        ok = False

    if ok:
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass
    return ok


_PII_PATTERNS = (
    (re.compile(r"(\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"), "<телефон>"),
    (re.compile(r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\."), "<ФИО>"),
    (re.compile(r"\b[А-Я]\s?\d{3}\s?[А-Я]{2}\s?\d{2,3}\b"), "<госномер>"),
)


def redact_pii(text: str) -> str:
    for pattern, repl in _PII_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def write_crash_log(err_msg: str) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
            stamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            f.write(f"\n[{stamp}] CRASH:\n{redact_pii(err_msg)}\n")
    except Exception:
        pass


DEFAULT_SETTINGS = {
    "last_pass_num": "001-26",
    "territory": 'ПТО "Шаврова"',
    "otb_post": "", "otb_name": "",
    "valid_until": "31.12.2026",
    "is_temporary_car": False,
    "print_mode": "a4",
    "badge_park": "ОСП «Трамвайный парк № 8»",
    "badge_tab_num": "01035",
    "badge_print_mode": "card",
    "last_printer": "По умолчанию",
    "auto_preview_target": "1",
    "warn_duplicates": True,
    "theme": "light",
    "window_geometry": "",
    "active_tab": 0,
    "pass_paned_width": 0,
    "badge_paned_width": 0,
    "print_pass_back": False,
}


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                for key, value in stored.items():
                    if key in DEFAULT_SETTINGS and value is not None:
                        data[key] = value
        except Exception:
            pass
    data["issue_date"] = datetime.now().strftime("%d.%m.%Y")
    return data


def save_settings(values: dict) -> bool:
    payload = {k: v for k, v in values.items() if k in DEFAULT_SETTINGS}
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
        os.replace(tmp, CONFIG_FILE)
        return True
    except Exception:
        return False