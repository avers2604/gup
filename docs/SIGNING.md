# Цифровая подпись Windows-сборок

GET-Passes поддерживает два взаимоисключающих способа Authenticode-подписи в GitHub Actions. Если настроены оба, **Azure Key Vault имеет приоритет**, а PFX используется как fallback только при отсутствии Azure-настройки.

## Важно

Самоподписанный сертификат не решает задачу доверия Windows/SmartScreen и не считается production-подписью. Для эксплуатации нужен доверенный code-signing сертификат организации либо сервис доверенной подписи, выдающий Authenticode-подпись.

Без signing secrets workflow продолжает собирать и тестировать приложение, но шаги подписи имеют статус `skipped`. Такой артефакт является **UNSIGNED**.

## Вариант A — Azure Key Vault

Repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_KEY_VAULT_NAME`
- `AZURE_SIGN_CERT_NAME`
- `AZURE_SIGN_CERT_PASSWORD`

`AZURE_SIGN_CERT_NAME` должен указывать на секрет Key Vault, содержащий PFX в base64. GitHub OIDC service principal должен иметь минимально необходимые права на чтение этого секрета.

Workflow выполняет `azure/login`, скачивает PFX во временный каталог runner, подписывает SHA-256 с RFC3161 timestamp `http://timestamp.digicert.com` и проверяет результат через `Get-AuthenticodeSignature`.

## Вариант B — PFX в GitHub Secrets

Repository secrets:

- `WINDOWS_SIGN_CERT_BASE64`
- `WINDOWS_SIGN_CERT_PASSWORD`

PowerShell для подготовки base64 из доверенного PFX **локально**:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("codesign.pfx")) | Set-Clipboard
```

Содержимое буфера помещается в `WINDOWS_SIGN_CERT_BASE64`, пароль PFX — в `WINDOWS_SIGN_CERT_PASSWORD`.

Не коммитьте PFX, пароль или base64 в репозиторий.

## Что подписывается

Production pipeline подписывает в таком порядке:

1. `GET-Passes.exe` — до сборки установщика;
2. Inno Setup включает уже подписанный EXE в `GET-Passes-Setup.exe`;
3. подписывается сам `GET-Passes-Setup.exe`;
4. обе подписи проверяются через `Get-AuthenticodeSignature`.

Это важно: подпись только внешнего установщика недостаточна — установленный EXE тоже должен иметь валидную Authenticode-подпись.

## Проверка локально

```powershell
Get-AuthenticodeSignature .\GET-Passes.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Setup.exe | Format-List Status,StatusMessage,SignerCertificate
```

Для production release ожидается `Status: Valid` у обоих файлов.

## Stable release

Workflow `.github/workflows/release.yml` предназначен для versioned tags (`v1.1.0`, `v1.2.0`, ...). Он проверяет соответствие тега версии в `pyproject.toml` и **не должен использоваться как подтверждение физической приёмки принтера**. Versioned stable tag создаётся только после выполнения ручной части `docs/ACCEPTANCE.md`.
