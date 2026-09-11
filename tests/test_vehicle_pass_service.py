from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
)
from getpass_app.services.vehicle_pass_service import VehiclePassService


def make_service(**overrides):
    defaults = {
        "lookup": lambda plate: None,
        "zone_values": lambda: [],
        "brand_values": lambda: [],
        "render": lambda data, common: ("front", data["num"], data["plate"]),
        "render_back": lambda: "back",
        "build_a4": lambda first, second=None: ("sheet", first, second),
    }
    defaults.update(overrides)
    return VehiclePassService(**defaults)


def test_lookup_returns_only_vehicle_fields():
    service = make_service(
        lookup=lambda plate: {
            "brand": "Лада",
            "model": "Веста",
            "type": "легковой",
            "color": "белый",
            "d_fio": "СТАРЫЙ ВОДИТЕЛЬ",
            "d_phone": "123",
            "territory": "СТАРАЯ ЗОНА",
        }
    )

    assert service.lookup_vehicle("А111АА78") == {
        "brand": "Лада",
        "model": "Веста",
        "type": "легковой",
        "color": "белый",
    }


def test_lookup_none_stays_none():
    assert make_service().lookup_vehicle("А111АА78") is None


def test_zones_merge_defaults_and_history_without_duplicates():
    service = make_service(
        zone_values=lambda: ["Парковка", "Гостевая зона"],
        brand_values=lambda: ["Volvo", "Лада"],
    )

    assert service.zones() == (
        'ПТО "Шаврова"',
        "Парковка",
        'ПТО "Шаврова", Парковка',
        "Гостевая зона",
    )
    assert service.brands() == ("Volvo", "Лада")


def test_preview_uses_legacy_placeholder_renderer_contract():
    captured = []
    service = make_service(
        render=lambda data, common: captured.append((data, common)) or "preview"
    )

    result = service.render_preview(VehiclePassData(), VehiclePassCommon())

    assert result == "preview"
    assert captured[0][0]["num"] == "000-00"
    assert captured[0][0]["plate"] == "А 000 АА 00"
    assert captured[0][0]["driver_full"] == "Должность  Фамилия И.О."


def test_a4_builds_two_front_slots_and_matching_back_sheet():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02", plate="В222ВВ78"),
        print_back=True,
    )

    front, back = service.build_documents(state)

    assert front == (
        "sheet",
        ("front", "100-01", "А111АА78"),
        ("front", "100-02", "В222ВВ78"),
    )
    assert back == ("sheet", "back", "back")


def test_a4_empty_second_pass_uses_only_first_slot():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02"),
    )

    front, back = service.build_documents(state)

    assert front == ("sheet", ("front", "100-01", "А111АА78"), None)
    assert back is None


def test_a5_returns_single_existing_renderer_image_and_back():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02", plate="В222ВВ78"),
        page_format="a5",
        print_back=True,
    )

    front, back = service.build_documents(state)

    assert front == ("front", "100-01", "А111АА78")
    assert back == "back"
