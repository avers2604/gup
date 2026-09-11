from getpass_app.models.employee_badge import (
    EmployeeBadgeData,
    EmployeeBadgeState,
    validate_employee_badge,
)


def _valid_data(**changes):
    values = {
        "tab_num": "01035",
        "park": 'ОСП «Трамвайный парк № 5»',
        "role": "ВОДИТЕЛЬ",
        "surname": "ИВАНОВ",
        "name": "ИВАН",
        "patronymic": "ИВАНОВИЧ",
        "phone": "+79990000000",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2031",
        "photo_path": "photo.jpg",
    }
    values.update(changes)
    return EmployeeBadgeData(**values)


def test_renderer_contract_preserves_existing_badge_keys():
    result = _valid_data().to_renderer_dict()

    assert result["tab_num"] == "01035"
    assert result["park"] == 'ОСП «Трамвайный парк № 5»'
    assert result["role"] == "ВОДИТЕЛЬ"
    assert result["surname"] == "ИВАНОВ"
    assert result["name"] == "ИВАН"
    assert result["patronymic"] == "ИВАНОВИЧ"
    assert result["fio"] == "ИВАНОВ И.И."
    assert result["phone"] == "+79990000000"
    assert result["issue_date"] == "12.09.2026"
    assert result["valid_until"] == "12.09.2031"
    assert result["photo_path"] == "photo.jpg"


def test_preview_renderer_contract_has_safe_placeholders():
    result = EmployeeBadgeData().to_renderer_dict(placeholder=True)

    assert result["tab_num"] == "00000"
    assert result["role"] == "Должность"
    assert result["surname"] == "ФАМИЛИЯ"
    assert result["name"] == "ИМЯ"
    assert result["patronymic"] == "ОТЧЕСТВО"


def test_validation_requires_role_name_dates_and_photo():
    issues = validate_employee_badge(EmployeeBadgeState())
    fields = {issue.field for issue in issues}

    assert {
        "role",
        "surname",
        "name",
        "issue_date",
        "valid_until",
        "photo_path",
    } <= fields


def test_validation_rejects_invalid_issue_date():
    state = EmployeeBadgeState(data=_valid_data(issue_date="32.13.2026"))

    assert any(issue.field == "issue_date" for issue in validate_employee_badge(state))


def test_validation_rejects_invalid_valid_until_date():
    state = EmployeeBadgeState(data=_valid_data(valid_until="not-a-date"))

    assert any(issue.field == "valid_until" for issue in validate_employee_badge(state))


def test_validation_rejects_valid_until_before_issue_date():
    state = EmployeeBadgeState(
        data=_valid_data(issue_date="12.09.2026", valid_until="11.09.2026")
    )

    assert any(issue.field == "valid_until" for issue in validate_employee_badge(state))


def test_print_mode_defaults_to_card():
    assert EmployeeBadgeState().print_mode == "card"
