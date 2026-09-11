from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _FieldStub:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def insert(self, _index, value):
        self.value = value

    def set(self, value):
        self.value = value


class _VarStub:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_pass_autocomplete_reuses_only_vehicle_fields(monkeypatch):
    """История госномера не должна переносить персональные данные старого пропуска."""
    from getpass_ui import pass_tab

    old = {
        "brand": "ГАЗ",
        "model": "Газель NEXT",
        "type": "Служебный",
        "color": "Белый",
        "d_pos": "Старый водитель",
        "d_fio": "Иванов И.И.",
        "d_phone": "+7 999 111-22-33",
        "territory": "Старая зона",
    }
    monkeypatch.setattr(pass_tab, "lookup_car", lambda _plate: old)

    form = pass_tab.PassForm.__new__(pass_tab.PassForm)
    form.plate_var = _VarStub("О777ТВ198")
    form.brand = _FieldStub()
    form.model = _FieldStub()
    form.type = _FieldStub()
    form.color = _FieldStub()
    form.d_pos = _FieldStub()
    form.d_fio = _FieldStub()
    form.d_phone = _FieldStub()
    form.territory = _FieldStub()
    changes = []
    form.on_change = lambda *_args: changes.append(True)

    form.autocomplete()

    assert form.brand.get() == "ГАЗ"
    assert form.model.get() == "Газель NEXT"
    assert form.type.get() == "Служебный"
    assert form.color.get() == "Белый"
    assert form.d_pos.get() == ""
    assert form.d_fio.get() == ""
    assert form.d_phone.get() == ""
    assert form.territory.get() == ""
    assert changes == [True]


def test_pass_restore_ignores_legacy_vehicle_draft():
    """Сохранённый ранее draft ТС не должен заполнять новый пропуск при старте."""
    from getpass_ui.pass_tab import PassForm

    form = PassForm.__new__(PassForm)
    form.plate_var = _VarStub("")
    form.brand = _FieldStub()
    form.model = _FieldStub()
    form.type = _FieldStub()
    form.color = _FieldStub()
    form.d_pos = _FieldStub()
    form.d_fio = _FieldStub()
    form.d_phone = _FieldStub()
    form.territory = _FieldStub()

    form.restore({
        "plate": "А111АА78",
        "brand": "Старая марка",
        "d_fio": "Старый водитель",
        "phone": "+7 999 111-22-33",
        "territory": "Старая зона",
    })

    assert form.plate_var.get() == ""
    assert form.brand.get() == ""
    assert form.d_fio.get() == ""
    assert form.d_phone.get() == ""
    assert form.territory.get() == ""


def test_otb_signature_captions_are_close_to_the_line(monkeypatch):
    """Подписи трёх строк ОТБ должны быть чуть ниже линии, а не заметно съезжать вниз."""
    from getpass_core import blank

    seen = {}
    original = blank._caption

    def capture(draw, x, y, text, size=32):
        if text in {"Должность", "Подпись", "Расшифровка"}:
            seen[text] = y
        return original(draw, x, y, text, size=size)

    blank.reset_cache()
    monkeypatch.setattr(blank, "_caption", capture)
    blank.build_pass_blank()

    assert seen == {
        "Должность": 1434,
        "Подпись": 1434,
        "Расшифровка": 1434,
    }


def test_release_workflows_support_azure_artifact_signing():
    """Доверенная Azure-подпись должна идти через Artifact Signing, а не только через PFX."""
    for name in ("build-exe.yml", "release.yml"):
        workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "HAS_ARTIFACT_SIGNING_SECRETS" in workflow
        assert "azure/artifact-signing-action@" in workflow
        assert "AZURE_ARTIFACT_SIGNING_ENDPOINT" in workflow
        assert "AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME" in workflow
        assert "AZURE_ARTIFACT_SIGNING_CERTIFICATE_PROFILE" in workflow
        assert "signing-account-name:" in workflow
        assert "certificate-profile-name:" in workflow
