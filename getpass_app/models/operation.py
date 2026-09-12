from dataclasses import dataclass


@dataclass(frozen=True)
class PendingOperation:
    id: str
    journal_key: str
    journal_name: str
    created_at: str
    destination: str
    document_status: str
    document_path: str = ""
