from pathlib import Path


def replace_once(path, old, new):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "getpass_core/storage.py",
    '''    def _read_legacy_csv(self) -> list[dict]:
        path = self.schema.csv_path
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f, delimiter=";"))
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ValueError(f"Не удалось перенести старый журнал: {path}") from exc
        if len(rows) < 2:
            return []
        header, body = rows[0], rows[1:]
        keys = self._keys_for(header)
        records = []
        for raw in body:
            if not any((c or "").strip() for c in raw):
                continue
            rec = {k: "" for k in self.schema.keys}
            layout = keys or self.schema.legacy_layouts.get(len(raw))
            if layout is None:
                layout = self.schema.keys
            for i, key in enumerate(layout):
                if key in rec and i < len(raw):
                    rec[key] = (raw[i] or "").strip()
            if not rec.get("id"):
                rec["id"] = new_id()
            if not rec.get("status"):
                rec["status"] = STATUS_ACTIVE
            records.append(rec)
        return records
''',
    '''    def _read_legacy_rows(self, path: str) -> list[list[str]]:
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                return list(csv.reader(f, delimiter=";"))
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ValueError(f"Не удалось перенести старый журнал: {path}") from exc

    @staticmethod
    def _legacy_row_has_values(raw) -> bool:
        return any((cell or "").strip() for cell in raw)

    def _legacy_layout(self, raw, keys):
        return keys or self.schema.legacy_layouts.get(len(raw)) or self.schema.keys

    def _legacy_record(self, raw, layout) -> dict:
        record = {key: "" for key in self.schema.keys}
        for index, key in enumerate(layout):
            if key in record and index < len(raw):
                record[key] = (raw[index] or "").strip()
        record["id"] = record.get("id") or new_id()
        record["status"] = record.get("status") or STATUS_ACTIVE
        return record

    def _read_legacy_csv(self) -> list[dict]:
        path = self.schema.csv_path
        if not os.path.exists(path):
            return []
        rows = self._read_legacy_rows(path)
        if len(rows) < 2:
            return []
        keys = self._keys_for(rows[0])
        return [
            self._legacy_record(raw, self._legacy_layout(raw, keys))
            for raw in rows[1:]
            if self._legacy_row_has_values(raw)
        ]
''',
)

replace_once(
    "getpass_ui/journal.py",
    '''    def apply_filter(self, *_args):
        if _args:
            self.page = 0
        query = self.search_var.get().lower().strip()
        mode = self.filter_var.get()
        d_from = parse_date(self.date_from.get())
        d_to = parse_date(self.date_to.get())
        extras = {k: w.get().strip() for k, w in self._extra_widgets.items()}
        today = datetime.now().date()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for rec in self.records:
            if query and not any(query in str(v).lower() for v in rec.values()):
                continue
            state = self._state_of(rec, today)
            if mode != "all" and state != mode:
                continue
            issue = parse_date(rec.get("issue_date"))
            if d_from and (issue is None or issue.date() < d_from.date()):
                continue
            if d_to and (issue is None or issue.date() > d_to.date()):
                continue
            skip = False
            for key, val in extras.items():
                if not val:
                    continue
                cell = (rec.get(key) or "")
                kind = _EXTRA_FILTERS[key][0]
                if kind == "combobox":
                    if cell != val:
                        skip = True
                        break
                elif val.lower() not in cell.lower():
                    skip = True
                    break
            if skip:
                continue
            values = [self._display(rec, f.key, state) for f in self.visible_fields]
            if self.page * self.page_size <= shown < (self.page + 1) * self.page_size:
                self.tree.insert("", "end", iid=rec["id"], values=values, tags=(state,))
            shown += 1
        self.filtered_count = shown
        self.status.config(
            text=f"Показано: {shown} из {len(self.records)}   "
                 f"(журнал: {self.schema.name})")
''',
    '''    def _matches_extra_filters(self, rec, extras) -> bool:
        for key, value in extras.items():
            if not value:
                continue
            cell = rec.get(key) or ""
            kind = _EXTRA_FILTERS[key][0]
            if kind == "combobox" and cell != value:
                return False
            if kind != "combobox" and value.lower() not in cell.lower():
                return False
        return True

    def _matches_record(self, rec, query, mode, d_from, d_to, extras, today):
        if query and not any(query in str(value).lower() for value in rec.values()):
            return False, None
        state = self._state_of(rec, today)
        if mode != "all" and state != mode:
            return False, state
        issue = parse_date(rec.get("issue_date"))
        if d_from and (issue is None or issue.date() < d_from.date()):
            return False, state
        if d_to and (issue is None or issue.date() > d_to.date()):
            return False, state
        return self._matches_extra_filters(rec, extras), state

    def _insert_filtered_record(self, rec, state, shown):
        start = self.page * self.page_size
        if not start <= shown < start + self.page_size:
            return
        values = [self._display(rec, field.key, state) for field in self.visible_fields]
        self.tree.insert("", "end", iid=rec["id"], values=values, tags=(state,))

    def apply_filter(self, *_args):
        if _args:
            self.page = 0
        query = self.search_var.get().lower().strip()
        mode = self.filter_var.get()
        d_from = parse_date(self.date_from.get())
        d_to = parse_date(self.date_to.get())
        extras = {key: widget.get().strip() for key, widget in self._extra_widgets.items()}
        today = datetime.now().date()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for rec in self.records:
            matches, state = self._matches_record(
                rec, query, mode, d_from, d_to, extras, today
            )
            if not matches:
                continue
            self._insert_filtered_record(rec, state, shown)
            shown += 1
        self.filtered_count = shown
        self.status.config(
            text=f"Показано: {shown} из {len(self.records)}   "
                 f"(журнал: {self.schema.name})")
''',
)

replace_once(
    "getpass_ui/app.py",
    '''    def __init__(self):
        setup_ui_font()
        self.settings = config.load_settings()
        config.harden_data_dir()

        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("СПб ГУП «Горэлектротранс» — Система выпуска пропусков и бейджей")

        self.scale = apply_scaling(self.root)
        default_w, default_h = scaled(1500, self.scale), scaled(920, self.scale)
        saved_w, saved_h = self._parse_geometry(self.settings.get("window_geometry", ""))
        win_w, win_h = fit_to_screen(self.root, saved_w or default_w, saved_h or default_h)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(min(win_w, scaled(1000, self.scale)),
                          min(win_h, scaled(660, self.scale)))
        if os.path.exists(config.ICON_FILE):
            try:
                self.root.iconbitmap(config.ICON_FILE)
            except Exception:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.report_callback_exception = self._on_callback_exception

        palette = self.settings.get("theme", "light")
        self.theme = Theme(self.root, palette, self.scale)
        set_titlebar_theme(self.root, self.theme.is_dark)
        verify_ui_family(self.root)
        self.theme.apply_window(self.root)

        self._build_header()
        self._build_system_bar()

        self.main_frame = tk.Frame(self.root, bg=self.theme.c("ground"))
        self.main_frame.pack(fill="both", expand=True, padx=self.theme.sp(3),
                             pady=(0, self.theme.sp(3)))
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.preview = Debouncer(self.root, self._render_preview, 150)
        self._build_pass_tab()
        self.badge = BadgePanel(self.notebook, self.settings, self.root, self.theme)
        self.badge.bind_app(self)
        draft = self.settings.get("draft")
        if isinstance(draft, dict):
            for name in ("p1", "p2"):
                if isinstance(draft.get(name), dict):
                    getattr(self, name).restore(draft[name])
            badge = draft.get("badge", {})
            if isinstance(badge, dict) and badge:
                self.badge.tab_num.set(badge.get("tab_num", ""))
                for var, key in ((self.badge.sur_var, "surname"), (self.badge.nam_var, "name"),
                                 (self.badge.pat_var, "patronymic")):
                    var.set(badge.get(key, ""))
                for field, key in ((self.badge.role, "role"), (self.badge.phone, "phone"),
                                   (self.badge.issue, "issue_date"), (self.badge.valid, "valid_until")):
                    field.set(badge.get(key, ""))
                self.badge.photo_path = badge.get("photo_path")
                self.badge._on_crop_cancel()

        self._bind_hotkeys()
        self.navigation = create_navigation(self)
        self.root.bind_all("<MouseWheel>", self._global_mousewheel)
        self.update_tab_states()
        self.root.after(200, self._startup_checks)
        self.root.after(250, self._initial_previews)
        self.root.after(30000, self._autosave)
        self.root.after(86400000, self._scheduled_backup)
        active_tab = self.settings.get("active_tab", 0)
        if active_tab in (0, 1):
            try:
                self.notebook.select(active_tab)
            except Exception:
                pass
        if self.notebook.index(self.notebook.select()) == 0:
            self.p1.plate.focus()
''',
    '''    def __init__(self):
        setup_ui_font()
        self.settings = config.load_settings()
        config.harden_data_dir()
        self._initialize_root()
        self._initialize_theme()
        self._build_main_content()
        self._restore_draft_state()
        self._initialize_runtime()

    def _initialize_root(self):
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("СПб ГУП «Горэлектротранс» — Система выпуска пропусков и бейджей")
        self.scale = apply_scaling(self.root)
        default_w, default_h = scaled(1500, self.scale), scaled(920, self.scale)
        saved_w, saved_h = self._parse_geometry(self.settings.get("window_geometry", ""))
        win_w, win_h = fit_to_screen(self.root, saved_w or default_w, saved_h or default_h)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(min(win_w, scaled(1000, self.scale)),
                          min(win_h, scaled(660, self.scale)))
        self._set_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.report_callback_exception = self._on_callback_exception

    def _set_window_icon(self):
        if not os.path.exists(config.ICON_FILE):
            return
        try:
            self.root.iconbitmap(config.ICON_FILE)
        except Exception:
            pass

    def _initialize_theme(self):
        palette = self.settings.get("theme", "light")
        self.theme = Theme(self.root, palette, self.scale)
        set_titlebar_theme(self.root, self.theme.is_dark)
        verify_ui_family(self.root)
        self.theme.apply_window(self.root)

    def _build_main_content(self):
        self._build_header()
        self._build_system_bar()
        self.main_frame = tk.Frame(self.root, bg=self.theme.c("ground"))
        self.main_frame.pack(fill="both", expand=True, padx=self.theme.sp(3),
                             pady=(0, self.theme.sp(3)))
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)
        self.preview = Debouncer(self.root, self._render_preview, 150)
        self._build_pass_tab()
        self.badge = BadgePanel(self.notebook, self.settings, self.root, self.theme)
        self.badge.bind_app(self)

    def _restore_draft_state(self):
        draft = self.settings.get("draft")
        if not isinstance(draft, dict):
            return
        for name in ("p1", "p2"):
            if isinstance(draft.get(name), dict):
                getattr(self, name).restore(draft[name])
        badge = draft.get("badge", {})
        if not isinstance(badge, dict) or not badge:
            return
        self.badge.tab_num.set(badge.get("tab_num", ""))
        for var, key in ((self.badge.sur_var, "surname"), (self.badge.nam_var, "name"),
                         (self.badge.pat_var, "patronymic")):
            var.set(badge.get(key, ""))
        for field, key in ((self.badge.role, "role"), (self.badge.phone, "phone"),
                           (self.badge.issue, "issue_date"), (self.badge.valid, "valid_until")):
            field.set(badge.get(key, ""))
        self.badge.photo_path = badge.get("photo_path")
        self.badge._on_crop_cancel()

    def _initialize_runtime(self):
        self._bind_hotkeys()
        self.navigation = create_navigation(self)
        self.root.bind_all("<MouseWheel>", self._global_mousewheel)
        self.update_tab_states()
        self.root.after(200, self._startup_checks)
        self.root.after(250, self._initial_previews)
        self.root.after(30000, self._autosave)
        self.root.after(86400000, self._scheduled_backup)
        active_tab = self.settings.get("active_tab", 0)
        if active_tab in (0, 1):
            try:
                self.notebook.select(active_tab)
            except Exception:
                pass
        if self.notebook.index(self.notebook.select()) == 0:
            self.p1.plate.focus()
''',
)

replace_once(
    "getpass_ui/app.py",
    '''    def direct_print_pass(self):
        built = self.build_documents()
        if not built:
            return
        document, back_document, prefix, records, next_num = built
        try:
            self._issuance_id = issuance.prepare(PASS_JOURNAL, records, self.printer_var.get())
        except Exception as exc:
            messagebox.showerror("Выдача не начата", str(exc))
            return
        if back_document is not None:
            printer = self.printer_var.get()
            ok, err = run_task(self.root, lambda ask: printing.print_pass_two_sided(
                document, back_document, printer, confirm_flip=ask),
                "Двусторонняя печать", confirm=self._confirm_flip_for_back_side)
        else:
            printer = self.printer_var.get()
            ok, err = run_task(self.root, lambda: printing.send_image_to_printer(document, printer), "Печать")
        if ok:
            if not self._finish_pass(records, next_num):
                return
            messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
            return
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
        try:
            if back_document is not None:
                printing.save_pdf_pages([document, back_document], temp_pdf)
            else:
                printing.save_document(document, temp_pdf)
            os.startfile(temp_pdf)  # noqa: Windows only
            opened = True
        except Exception:
            opened = False
        if messagebox.askyesno(
                "Принтер не ответил",
                f"Не удалось напечатать напрямую.\n{err or ''}\n\n"
                + ("Документ открыт — напечатайте вручную (Ctrl+P).\n\n" if opened else "")
                + "Считать пропуск выданным и записать в журнал?"):
            self._finish_pass(records, next_num)
''',
    '''    def _send_pass_to_printer(self, document, back_document, printer):
        if back_document is not None:
            return run_task(
                self.root,
                lambda ask: printing.print_pass_two_sided(
                    document, back_document, printer, confirm_flip=ask
                ),
                "Двусторонняя печать",
                confirm=self._confirm_flip_for_back_side,
            )
        return run_task(
            self.root,
            lambda: printing.send_image_to_printer(document, printer),
            "Печать",
        )

    @staticmethod
    def _open_manual_print_copy(document, back_document, prefix):
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
        try:
            if back_document is not None:
                printing.save_pdf_pages([document, back_document], temp_pdf)
            else:
                printing.save_document(document, temp_pdf)
            os.startfile(temp_pdf)  # noqa: Windows only
            return True
        except Exception:
            return False

    @staticmethod
    def _confirm_manual_issuance(err, opened):
        opened_note = "Документ открыт — напечатайте вручную (Ctrl+P).\n\n" if opened else ""
        return messagebox.askyesno(
            "Принтер не ответил",
            f"Не удалось напечатать напрямую.\n{err or ''}\n\n"
            + opened_note
            + "Считать пропуск выданным и записать в журнал?",
        )

    def direct_print_pass(self):
        built = self.build_documents()
        if not built:
            return
        document, back_document, prefix, records, next_num = built
        printer = self.printer_var.get()
        try:
            self._issuance_id = issuance.prepare(PASS_JOURNAL, records, printer)
        except Exception as exc:
            messagebox.showerror("Выдача не начата", str(exc))
            return
        ok, err = self._send_pass_to_printer(document, back_document, printer)
        if ok:
            if not self._finish_pass(records, next_num):
                return
            messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
            return
        opened = self._open_manual_print_copy(document, back_document, prefix)
        if self._confirm_manual_issuance(err, opened):
            self._finish_pass(records, next_num)
''',
)
