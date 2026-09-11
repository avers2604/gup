from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


storage = Path("getpass_core/storage.py")
text = storage.read_text(encoding="utf-8")
for suffix in (
    "# nosec B608 -- identifiers come from validated JournalSchema",
    "# nosec B608 -- validated schema table",
    "# nosec B608 -- table is validated; ids remain parameterized",
    "# nosec B608 -- assignments are allowlisted schema keys",
):
    text = text.replace(suffix, "# nosec B608")

text = replace_once(
    text,
    '        \'  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\\n\'\n',
    '        \'  <Override PartName="/xl/workbook.xml" \'\n'
    '        \'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\\n\'\n',
    "workbook content type",
)
text = replace_once(
    text,
    '        \'  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\\n\'\n',
    '        \'  <Override PartName="/xl/worksheets/sheet1.xml" \'\n'
    '        \'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\\n\'\n',
    "worksheet content type",
)
text = replace_once(
    text,
    '        \'  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>\\n\'\n',
    '        \'  <Relationship Id="rId1" \'\n'
    '        \'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" \'\n'
    '        \'Target="xl/workbook.xml"/>\\n\'\n',
    "office document relationship",
)
text = replace_once(
    text,
    '        \'  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>\\n\'\n',
    '        \'  <Relationship Id="rId1" \'\n'
    '        \'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" \'\n'
    '        \'Target="worksheets/sheet1.xml"/>\\n\'\n',
    "worksheet relationship",
)
storage.write_text(text, encoding="utf-8")

app = Path("getpass_ui/app.py")
app_text = app.read_text(encoding="utf-8")
app_text = replace_once(
    app_text,
    '''            password = simpledialog.askstring(\n                "Пароль копии", "Не менее 12 символов. Сохраните пароль: без него восстановление невозможно.", show="*", parent=self.root)\n''',
    '''            password = simpledialog.askstring(\n                "Пароль копии",\n                "Не менее 12 символов. Сохраните пароль: без него восстановление невозможно.",\n                show="*",\n                parent=self.root,\n            )\n''',
    "backup password dialog",
)
app.write_text(app_text, encoding="utf-8")
