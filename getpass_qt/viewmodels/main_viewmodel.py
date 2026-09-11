from PySide6.QtCore import QObject, Signal

ROUTES = (
    "dashboard",
    "vehicle",
    "employee",
    "journals",
    "operations",
    "backups",
    "diagnostics",
    "settings",
)


class MainViewModel(QObject):
    route_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.active_route = "dashboard"

    def set_route(self, route: str) -> None:
        if route not in ROUTES:
            raise ValueError(f"Unknown route: {route}")
        if route == self.active_route:
            return
        self.active_route = route
        self.route_changed.emit(route)
