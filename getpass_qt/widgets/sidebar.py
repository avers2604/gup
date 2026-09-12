from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from getpass_qt.viewmodels.main_viewmodel import ROUTES

ROUTE_LABELS = {
    "dashboard": "Главная",
    "vehicle": "Пропуск ТС",
    "employee": "Пропуск работника",
    "batch": "Массовая печать",
    "journals": "Журналы",
    "operations": "Незавершённые",
    "backups": "Резервные копии",
    "diagnostics": "Диагностика",
    "settings": "Настройки",
}


class Sidebar(QFrame):
    route_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(6)

        brand = QLabel("GET-Passes")
        brand.setObjectName("SidebarBrand")
        layout.addWidget(brand)
        layout.addSpacing(18)

        for route in ROUTES:
            button = QPushButton(ROUTE_LABELS[route])
            button.setCheckable(True)
            button.setProperty("role", "nav")
            button.clicked.connect(
                lambda checked=False, value=route: self.request_route(value)
            )
            self.buttons[route] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.set_active("dashboard")

    def request_route(self, route: str) -> None:
        self.route_requested.emit(route)

    def set_active(self, route: str) -> None:
        for key, button in self.buttons.items():
            button.setChecked(key == route)
