# Цифровая подпись Windows-сборок

GET-Passes поддерживает три способа Authenticode-подписи в GitHub Actions. Приоритет: **Azure Artifact Signing → Azure Key Vault PFX → PFX в GitHub Secrets**.

## Важно

Самоподписанный сертификат не решает задачу доверия Windows/SmartScreen и не считается production-подписью. Доверенный издатель появляется только после подключения реального code-signing сертификата или управляемого сервиса подписи.

Если ни один набор signing secrets не настроен, workflow продолжает собирать и тестировать приложение, но шаги подписи имеют статус `skipped`. Такой артефакт явно маркируется **UNSIGNED**.

## Вариант A — Azure Artifact Signing (рекомендуется)

Это основной вариант для доверенной подписи без хранения и выгрузки закрытого ключа в GitHub Actions. Нужны Azure Artifact Signing Account и Certificate Profile.

Repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_ARTIFACT_SIGNING_ENDPOINT`
- `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`
- `AZURE_ARTIFACT_SIGNING_CERTIFICATE_PROFILE`

App Registration, используемая GitHub OIDC, должна иметь роль **Artifact Signing Certificate Profile Signer** для нужного certificate profile.

Пример значения endpoint зависит от региона созданного signing account, например `https://eus.codesigning.azure.net/`. Используйте endpoint, указанный для вашего ресурса Azure Artifact Signing.

Workflow выполняет `azure/login` через OIDC, затем вызывает официальный `azure/artifact-signing-action`, подписывает SHA-256 и добавляет RFC3161 timestamp через Azure timestamp service. Закрытый ключ при этом не передаётся в репозиторий или GitHub Secrets.

## Вариант B — доверенный PFX в Azure Key Vault

Repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_KEY_VAULT_NAME`
- `AZURE_SIGN_CERT_NAME`
- `AZURE_SIGN_CERT_PASSWORD`

`AZURE_SIGN_CERT_NAME` должен указывать на секрет Key Vault, содержащий доверенный PFX в base64. GitHub OIDC service principal должен иметь минимально необходимые права на чтение этого секрета.

Workflow скачивает PFX во временный каталог runner, подписывает через `signtool` SHA-256 с RFC3161 timestamp и после сборки удаляет runner вместе с временным ключом.

## Вариант C — PFX в GitHub Secrets

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

Для Azure Artifact Signing оба файла подписываются через managed certificate profile. Если этот способ не настроен, используется Key Vault PFX, затем обычный PFX fallback.

## Проверка локально

```powershell
Get-AuthenticodeSignature .\GET-Passes.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Setup.exe | Format-List Status,StatusMessage,SignerCertificate
```

Для production release ожидается `Status: Valid` у обоих файлов.

## Почему код сам по себе не может сделать подпись доверенной

GitHub Actions может выполнить Authenticode-подпись, но не может сам выпустить организации публично доверенный code-signing сертификат. Для статуса `Valid` должен быть заранее создан Azure Artifact Signing certificate profile либо предоставлен доверенный PFX. Пока внешняя инфраструктура не настроена, `latest-build` останется `UNSIGNED` — это намеренное безопасное поведение.

## Stable release

Workflow `.github/workflows/release.yml` предназначен для versioned tags (`v1.1.0`, `v1.2.0`, ...). Он проверяет соответствие тега версии в `pyproject.toml` и отказывается публиковать stable release, если не настроен ни один доверенный способ подписи. Versioned stable tag создаётся только после выполнения ручной части `docs/ACCEPTANCE.md`.
