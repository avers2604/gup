from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from getpass_app.models.employee_badge import (
    EmployeeBadgeData,
    EmployeeBadgeState,
    validate_employee_badge,
)
from getpass_core import blacklist, config, issuance, printing
from getpass_core import render as R
from getpass_core.domain import next_number
from getpass_core.storage import BADGE_JOURNAL


@dataclass(frozen=True)
class EmployeeBadgeWarnings:
    duplicates: tuple[dict, ...] = ()
    blacklist: tuple[dict, ...] = ()


@dataclass(frozen=True)
class EmployeeBadgeDocument:
    image: Image.Image
    prefix: str
    mode: str


@dataclass(frozen=True)
class EmployeeBadgeOutputResult:
    next_tab_num: str
    overflowed: bool = False


class EmployeeBadgeOutputError(RuntimeError):
    pass


class EmployeeBadgeService:
    def __init__(
        self,
        *,
        journal=BADGE_JOURNAL,
        blacklist_lookup=blacklist.find,
        printer_values=printing.get_available_printers,
        render=R.render_single_badge_image,
        build_grid=R.build_badge_a4_grid,
        build_single=R.build_badge_a4_single,
        prepare=issuance.prepare,
        confirm=issuance.confirm,
        cancel=issuance.cancel,
        save_document=printing.save_document,
        print_one=printing.send_image_to_printer,
        photo_dir=config.PHOTO_DIR,
        file_exists=os.path.exists,
    ) -> None:
        self._journal = journal
        self._blacklist_lookup = blacklist_lookup
        self._printer_values = printer_values
        self._render = render
        self._build_grid = build_grid
        self._build_single = build_single
        self._prepare = prepare
        self._confirm = confirm
        self._cancel = cancel
        self._save_document = save_document
        self._print_one = print_one
        self._photo_dir = Path(photo_dir)
        self._file_exists = file_exists

    def roles(self) -> tuple[str, ...]:
        return tuple(self._journal.distinct("role"))

    def printers(self) -> tuple[str, ...]:
        return tuple(self._printer_values())

    def warnings(self, state: EmployeeBadgeState) -> EmployeeBadgeWarnings:
        record = state.data.to_renderer_dict()
        duplicates = tuple(self._journal.find_duplicates(record["tab_num"]))
        incidents = tuple(self._blacklist_lookup(fio=record["fio"]))
        return EmployeeBadgeWarnings(duplicates=duplicates, blacklist=incidents)

    def render_preview(self, data: EmployeeBadgeData):
        return self._render(data.to_renderer_dict(placeholder=True))

    def store_photo(self, cropped: Image.Image, tab_num: str) -> str:
        self._photo_dir.mkdir(parents=True, exist_ok=True)
        clean_tab = "".join(ch for ch in (tab_num or "") if ch.isalnum()) or "badge"
        path = self._photo_dir / f"badge_{clean_tab}_{uuid.uuid4().hex}.jpg"
        image = cropped if cropped.mode == "RGB" else cropped.convert("RGB")
        image.save(path, "JPEG", quality=95, dpi=(300, 300))
        return str(path)

    def build_document(self, state: EmployeeBadgeState) -> EmployeeBadgeDocument:
        data = state.data.to_renderer_dict()
        badge = self._render(data)
        tab_num = data["tab_num"]
        surname = data["surname"]

        if state.print_mode == "card":
            return EmployeeBadgeDocument(
                image=badge,
                prefix=f"Пропуск_{tab_num}_{surname}_CR80",
                mode="card",
            )
        if state.print_mode == "a4_grid":
            return EmployeeBadgeDocument(
                image=self._build_grid([badge] * 9),
                prefix=f"Пропуска_{tab_num}_9шт_А4",
                mode="a4_grid",
            )
        return EmployeeBadgeDocument(
            image=self._build_single(badge),
            prefix=f"Пропуск_{tab_num}_1шт_А4",
            mode="a4_single",
        )

    def save_pdf(self, state: EmployeeBadgeState, path: str) -> EmployeeBadgeOutputResult:
        record = self._validated_record(state)
        operation_id = self._prepare(self._journal, [record], path)
        confirmed = False
        try:
            document = self.build_document(state)
            self._save_document(document.image, path)
            self._confirm(self._journal, operation_id)
            confirmed = True
        except BaseException as exc:
            if not confirmed:
                self._try_cancel(operation_id)
            if isinstance(exc, EmployeeBadgeOutputError):
                raise
            raise EmployeeBadgeOutputError(str(exc)) from exc
        return self._next_result(record["tab_num"])

    def print_badge(
        self,
        state: EmployeeBadgeState,
        printer: str,
    ) -> EmployeeBadgeOutputResult:
        record = self._validated_record(state)
        operation_id = self._prepare(self._journal, [record], printer)
        confirmed = False
        try:
            document = self.build_document(state)
            ok, error = self._print_one(document.image, printer)
            if not ok:
                raise EmployeeBadgeOutputError(error or "Не удалось напечатать бейдж.")
            self._confirm(self._journal, operation_id)
            confirmed = True
        except BaseException as exc:
            if not confirmed:
                self._try_cancel(operation_id)
            if isinstance(exc, EmployeeBadgeOutputError):
                raise
            raise EmployeeBadgeOutputError(str(exc)) from exc
        return self._next_result(record["tab_num"])

    def _validated_record(self, state: EmployeeBadgeState) -> dict[str, object]:
        issues = validate_employee_badge(state)
        if issues:
            raise EmployeeBadgeOutputError(issues[0].message)

        photo_path = state.data.photo_path.strip()
        if not self._file_exists(photo_path):
            raise EmployeeBadgeOutputError(
                "Файл фотографии сотрудника не найден. Выберите фотографию заново."
            )
        return state.data.to_renderer_dict()

    @staticmethod
    def _next_result(tab_num: object) -> EmployeeBadgeOutputResult:
        result = next_number(str(tab_num or ""))
        return EmployeeBadgeOutputResult(
            next_tab_num=result.value,
            overflowed=result.overflowed,
        )

    def _try_cancel(self, operation_id: str) -> None:
        try:
            self._cancel(self._journal, operation_id)
        except Exception:
            pass
