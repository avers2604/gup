from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
    validate_vehicle_state,
)


def test_renderer_dict_normalizes_plate_and_driver_contract():
    data = VehiclePassData(
        num="100-01",
        plate="а111аа78",
        brand="Лада",
        model="Веста",
        vehicle_type="легковой",
        color="белый",
        driver_position="водитель",
        driver_name="Иванов И.И.",
        phone="+7 999 000-00-00",
        territory='ПТО "Шаврова"',
    )
    result = data.to_renderer_dict()
    assert result["num"] == "100-01"
    assert result["plate"] == "А111АА78"
    assert result["brand"] == "Лада"
    assert result["model"] == "Веста"
    assert result["type"] == "легковой"
    assert result["color"] == "белый"
    assert result["d_pos"] == "водитель"
    assert result["d_fio"] == "Иванов И.И."
    assert result["phone"] == "+7 999 000-00-00"
    assert result["driver_full"] == "водитель Иванов И.И."
    assert result["territory"] == 'ПТО "Шаврова"'


def test_preview_placeholder_matches_legacy_contract():
    result = VehiclePassData().to_renderer_dict(placeholder=True)
    assert result["num"] == "000-00"
    assert result["plate"] == "А 000 АА 00"
    assert result["driver_full"] == "Должность  Фамилия И.О."


def test_second_empty_pass_is_allowed_but_first_plate_is_required():
    state = VehiclePassState(first=VehiclePassData(), second=VehiclePassData())
    issues = validate_vehicle_state(state)
    assert [(issue.field, issue.message) for issue in issues] == [
        ("first.plate", "Укажите государственный регистрационный знак."),
    ]


def test_nonempty_second_pass_requires_plate():
    state = VehiclePassState(
        first=VehiclePassData(plate="А111АА78"),
        second=VehiclePassData(num="100-02", brand="Лада"),
    )
    assert any(issue.field == "second.plate" for issue in validate_vehicle_state(state))


def test_common_renderer_contract_uses_existing_keys():
    common = VehiclePassCommon(
        issue_date="12.09.2026",
        valid_until="12.09.2027",
        is_temporary=True,
        otb_post="Начальник ОТБ",
        otb_name="Петров П.П.",
    )
    assert common.to_renderer_dict() == {
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
        "is_temporary": True,
        "otb_post": "Начальник ОТБ",
        "otb_name": "Петров П.П.",
    }


def test_default_state_preserves_phase2_output_defaults():
    state = VehiclePassState()
    assert state.page_format == "a4"
    assert state.print_back is False
