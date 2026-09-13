import pytest

from getpass_app.models.blacklist import BlacklistEntry
from getpass_app.services.blacklist_service import BlacklistService


def test_blacklist_service_projects_loaded_entries():
    service = BlacklistService(
        load=lambda: [
            {
                "id": "entry-1",
                "plate": "А111АА78",
                "fio": "ИВАНОВ ИВАН ИВАНОВИЧ",
                "incident": "Нарушение",
                "created_at": "13.09.2026 20:00",
            }
        ],
        add=lambda **kwargs: {},
        remove=lambda entry_id: None,
    )

    assert service.list_entries() == (
        BlacklistEntry(
            id="entry-1",
            plate="А111АА78",
            fio="ИВАНОВ ИВАН ИВАНОВИЧ",
            incident="Нарушение",
            created_at="13.09.2026 20:00",
        ),
    )


def test_blacklist_service_adds_through_core_and_returns_projection():
    calls = []

    def add(**kwargs):
        calls.append(kwargs)
        return {
            "id": "entry-2",
            "plate": "О777ТВ198",
            "fio": "ПЕТРОВ ПЕТР ПЕТРОВИЧ",
            "incident": "ДТП в парке",
            "created_at": "13.09.2026 20:10",
        }

    service = BlacklistService(load=lambda: [], add=add, remove=lambda entry_id: None)

    result = service.add_entry(
        plate="о 777 тв 198",
        fio="Петров Петр Петрович",
        incident="  ДТП в парке  ",
    )

    assert calls == [{
        "plate": "о 777 тв 198",
        "fio": "Петров Петр Петрович",
        "incident": "ДТП в парке",
    }]
    assert result.plate == "О777ТВ198"
    assert result.fio == "ПЕТРОВ ПЕТР ПЕТРОВИЧ"
    assert result.incident == "ДТП в парке"


def test_blacklist_service_requires_plate_or_fio():
    service = BlacklistService(load=lambda: [], add=lambda **kwargs: {}, remove=lambda entry_id: None)

    with pytest.raises(ValueError, match="госномер или ФИО"):
        service.add_entry(plate=" ", fio=" ", incident="Нарушение")


def test_blacklist_service_requires_incident():
    service = BlacklistService(load=lambda: [], add=lambda **kwargs: {}, remove=lambda entry_id: None)

    with pytest.raises(ValueError, match="инцидент"):
        service.add_entry(plate="А111АА78", fio="", incident=" ")


def test_blacklist_service_removes_by_id():
    calls = []
    service = BlacklistService(
        load=lambda: [],
        add=lambda **kwargs: {},
        remove=lambda entry_id: calls.append(entry_id),
    )

    service.remove_entry("entry-3")

    assert calls == ["entry-3"]
