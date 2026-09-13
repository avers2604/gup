from dataclasses import dataclass


@dataclass(frozen=True)
class BlacklistEntry:
    id: str
    plate: str
    fio: str
    incident: str
    created_at: str

    @classmethod
    def from_mapping(cls, value: dict) -> "BlacklistEntry":
        return cls(
            id=str(value.get("id", "")),
            plate=str(value.get("plate", "")),
            fio=str(value.get("fio", "")),
            incident=str(value.get("incident", "")),
            created_at=str(value.get("created_at", "")),
        )
