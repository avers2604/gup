from __future__ import annotations

import argparse
import os

from PySide6.QtWidgets import QApplication

from getpass_app.services.settings_service import SettingsService
from getpass_app.services.vehicle_pass_service import VehiclePassService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="GET-Passes Qt Preview")
    parser.add_argument("--self-test", action="store_true")
    return parser


def _vehicle_viewmodel(*, self_test: bool) -> VehiclePassViewModel:
    if self_test:
        service = VehiclePassService(
            lookup=lambda plate: None,
            zone_values=lambda: (),
            brand_values=lambda: (),
            printer_values=lambda: ("По умолчанию",),
        )
    else:
        service = VehiclePassService()
    return VehiclePassViewModel(service)


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
    window = MainWindow(
        theme_manager=theme,
        vehicle_viewmodel=_vehicle_viewmodel(self_test=args.self_test),
    )

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
