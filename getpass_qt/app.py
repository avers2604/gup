from __future__ import annotations

import argparse
import os

from PySide6.QtWidgets import QApplication

from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="GET-Passes Qt Preview")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication(["GET-Passes Qt Preview"])
    if args.self_test:
        settings = SettingsService(
            load=lambda: {"theme": "light"},
            save=lambda values: True,
        )
    else:
        settings = SettingsService()

    theme = ThemeManager(app, settings)
    theme.load()
    window = MainWindow(theme_manager=theme)

    if args.self_test:
        window.show()
        app.processEvents()
        assert window.active_route == "dashboard"
        assert window.stack.count() == 8
        window.close()
        app.processEvents()
        return 0

    window.show()
    return app.exec()
