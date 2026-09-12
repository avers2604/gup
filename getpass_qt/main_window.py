from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.journal_viewmodel import JournalViewModel
from getpass_qt.viewmodels.main_viewmodel import ROUTES, MainViewModel
from getpass_qt.viewmodels.operations_viewmodel import OperationsViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.views.dashboard import DashboardPage
from getpass_qt.views.employee_badge import EmployeeBadgePage
from getpass_qt.views.journals import JournalsPage
from getpass_qt.views.migration_page import MigrationPage
from getpass_qt.views.operations import OperationsPage
from getpass_qt.views.vehicle_pass import VehiclePassPage
from getpass_qt.widgets.sidebar import ROUTE_LABELS, Sidebar

_REAL_ROUTES = frozenset({"dashboard", "vehicle", "employee", "journals", "operations"})
_MIGRATION_DESCRIPTIONS = {
    route: (
        "Этот рабочий сценарий переносится на PySide6. "
        "До завершения миграции полноценная производственная функция остаётся "
        "доступна в текущем Tkinter-приложении GET-Passes."
    )
    for route in ROUTES
    if route not in _REAL_ROUTES
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme_manager: ThemeManager,
        vehicle_viewmodel: VehiclePassViewModel,
        employee_badge_viewmodel: EmployeeBadgeViewModel,
        journal_viewmodel: JournalViewModel,
        operations_viewmodel: OperationsViewModel,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._viewmodel = MainViewModel()
        self._page_indexes: dict[str, int] = {}

        self.setWindowTitle("GET-Passes — PySide6 Preview")
        self.resize(1180, 760)

        shell = QWidget()
        shell.setObjectName("AppShell")
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(232)
        root.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 24)
        content_layout.setSpacing(16)
        root.addWidget(content, 1)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.section_title = QLabel(ROUTE_LABELS["dashboard"])
        header_layout.addWidget(self.section_title)
        header_layout.addStretch(1)
        self.theme_button = QPushButton()
        self.theme_button.clicked.connect(self._theme_manager.toggle)
        header_layout.addWidget(self.theme_button)
        content_layout.addWidget(header)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        self.dashboard = DashboardPage()
        self._add_page("dashboard", self.dashboard)

        self.vehicle_page = VehiclePassPage(vehicle_viewmodel)
        self._add_page("vehicle", self.vehicle_page)

        self.employee_page = EmployeeBadgePage(employee_badge_viewmodel)
        self._add_page("employee", self.employee_page)

        self.journals_page = JournalsPage(journal_viewmodel)
        self._add_page("journals", self.journals_page)

        self.operations_page = OperationsPage(operations_viewmodel)
        self._add_page("operations", self.operations_page)

        for route in ROUTES[1:]:
            if route in _REAL_ROUTES:
                continue
            page = MigrationPage(
                ROUTE_LABELS[route],
                _MIGRATION_DESCRIPTIONS[route],
            )
            self._add_page(route, page)

        self.sidebar.route_requested.connect(self._viewmodel.set_route)
        self.dashboard.vehicle_requested.connect(
            lambda: self._viewmodel.set_route("vehicle")
        )
        self.dashboard.employee_requested.connect(
            lambda: self._viewmodel.set_route("employee")
        )
        self.dashboard.batch_requested.connect(
            lambda: self._viewmodel.set_route("vehicle")
        )
        self._viewmodel.route_changed.connect(self._show_route)
        self._theme_manager.theme_changed.connect(self._update_theme_button)

        self._show_route(self._viewmodel.active_route)
        self._update_theme_button(self._theme_manager.current_theme)

    @property
    def active_route(self) -> str:
        return self._viewmodel.active_route

    def _add_page(self, route: str, page: QWidget) -> None:
        self._page_indexes[route] = self.stack.addWidget(page)

    def _show_route(self, route: str) -> None:
        self.stack.setCurrentIndex(self._page_indexes[route])
        self.sidebar.set_active(route)
        self.section_title.setText(ROUTE_LABELS[route])

    def _update_theme_button(self, theme: str) -> None:
        self.theme_button.setText(
            "Светлая тема" if theme == "dark" else "Тёмная тема"
        )
