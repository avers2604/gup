from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from getpass_core.domain import parse_date, split_fio

DEFAULT_BADGE_PARK = 'ОСП «Трамвайный парк № 8»'


@dataclass(frozen=True)
class EmployeeBadgeData:
    tab_num: str = ""
    park: str = ""
    role: str = ""
    surname: str = ""
    name: str = ""
    patronymic: str = ""
    phone: str = ""
    issue_date: str = ""
    valid_until: str = ""
    photo_path: str = ""

    def to_renderer_dict(self, *, placeholder: bool = False) -> dict[str, object]:
        surname = self.surname.strip()
        name = self.name.strip()
        patronymic = self.patronymic.strip()
        if placeholder:
            surname = surname or "ФАМИЛИЯ"
            name = name or "ИМЯ"
            patronymic = patronymic or "ОТЧЕСТВО"

        tab_num = self.tab_num.strip()
        if not tab_num:
            tab_num = "00000" if placeholder else "00001"

        role = self.role.strip()
        if not role:
            role = "Должность" if placeholder else "Сотрудник"

        return {
            "tab_num": tab_num,
            "park": self.park.strip() or DEFAULT_BADGE_PARK,
            "role": role,
            "surname": surname,
            "name": name,
            "patronymic": patronymic,
            "fio": split_fio(surname, name, patronymic),
            "phone": self.phone.strip(),
            "issue_date": self.issue_date.strip(),
            "valid_until": self.valid_until.strip(),
            "photo_path": self.photo_path.strip() or None,
        }


@dataclass(frozen=True)
class EmployeeBadgeState:
    data: EmployeeBadgeData = field(default_factory=EmployeeBadgeData)
    print_mode: Literal["card", "a4_grid", "a4_single"] = "card"


@dataclass(frozen=True)
class BadgeValidationIssue:
    field: str
    message: str


def validate_employee_badge(
    state: EmployeeBadgeState,
) -> tuple[BadgeValidationIssue, ...]:
    data = state.data
    issues: list[BadgeValidationIssue] = []

    required = (
        ("role", data.role, "Укажите должность сотрудника."),
        ("surname", data.surname, "Укажите фамилию сотрудника."),
        ("name", data.name, "Укажите имя сотрудника."),
        ("issue_date", data.issue_date, "Укажите дату выдачи."),
        ("valid_until", data.valid_until, "Укажите дату окончания."),
        ("photo_path", data.photo_path, "Выберите фотографию сотрудника."),
    )
    for field_name, value, message in required:
        if not (value or "").strip():
            issues.append(BadgeValidationIssue(field_name, message))

    issue_date = parse_date(data.issue_date)
    valid_until = parse_date(data.valid_until)

    if data.issue_date.strip() and issue_date is None:
        issues.append(
            BadgeValidationIssue(
                "issue_date",
                "Дата выдачи должна быть в формате ДД.ММ.ГГГГ.",
            )
        )
    if data.valid_until.strip() and valid_until is None:
        issues.append(
            BadgeValidationIssue(
                "valid_until",
                "Дата окончания должна быть в формате ДД.ММ.ГГГГ.",
            )
        )
    if issue_date is not None and valid_until is not None and valid_until < issue_date:
        issues.append(
            BadgeValidationIssue(
                "valid_until",
                "Дата окончания не может быть раньше даты выдачи.",
            )
        )

    return tuple(issues)
