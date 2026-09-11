"""Built-in and extension navigation actions, registered independently of App."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    open: object


class Navigation:
    def __init__(self):
        self.sections = {}

    def register(self, section):
        if section.key in self.sections:
            raise ValueError(f"Duplicate section: {section.key}")
        self.sections[section.key] = section

    def populate(self, menu):
        for section in self.sections.values():
            menu.add_command(label=section.title, command=section.open)


def create_navigation(app):
    from .operations import open_operations
    from .diagnostics import open_diagnostics
    navigation = Navigation()
    for section in (
        Section("passes", "Журнал ТС", app.open_pass_journal),
        Section("badges", "Журнал работников", app.open_badge_journal),
        Section("backup", "Резервная копия", app.backup_database),
        Section("restore", "Восстановить из копии", app.restore_database),
        Section("operations", "Незавершённые выдачи", lambda: open_operations(app.root, app.theme)),
        Section("diagnostics", "Диагностика", lambda: open_diagnostics(app.root, app.theme)),
    ):
        navigation.register(section)
    return navigation
