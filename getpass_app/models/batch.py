from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BatchKind = Literal["pass", "badge"]


@dataclass(frozen=True)
class BatchTemplate:
    kind: BatchKind
    header: tuple[str, ...]
    sample: tuple[str, ...]
    filename: str


@dataclass(frozen=True)
class BatchReviewRow:
    row_number: int
    number: str
    person: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def result(self) -> str:
        return "; ".join((*self.errors, *self.warnings)) or "Готово"

    @property
    def state(self) -> str:
        if self.errors:
            return "error"
        if self.warnings:
            return "warning"
        return "ready"


@dataclass(frozen=True)
class BatchReview:
    kind: BatchKind
    rows: tuple[BatchReviewRow, ...]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def error_count(self) -> int:
        return sum(bool(row.errors) for row in self.rows)

    @property
    def warning_count(self) -> int:
        return sum(bool(row.warnings) for row in self.rows)

    @property
    def can_generate(self) -> bool:
        return bool(self.rows) and self.error_count == 0
