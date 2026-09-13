# Цифровая подпись Windows-сборок

GET-Passes поддерживает три способа Authenticode-подписи в GitHub Actions. Приоритет: **Azure Artifact Signing Public Trust → Azure Key Vault PFX → PFX в GitHub Secrets**.

## Важно

Самоподписанный сертификат не решает задачу доверия Windows/SmartScreen и не считается production-подписью. Доверенный издатель появляется только после подключения реального публично доверенного code-signing сертификата или управляемого сервиса подписи.

Если ни один набор signing secrets не настроен, workflow продолжает собирать и тестировать приложение, но шаги подписи имеют статус `skipped`. Такой артефакт явно маркируется **UNSIGNED**.

## TM5 — production profile

Для GET-Passes 2.0 имя Azure Artifact Signing certificate profile закреплено в workflow как **`TM5`**. Оно не хранится в GitHub Secrets и не может быть случайно подменено конфигурацией релиза.

Важно различать **имя profile** и **имя издателя в Windows**. Microsoft Artifact Signing Public Trust не разрешает произвольные `CN`/`O`: subject сертификата формируется из проверенной публичной идентичности. Поэтому Windows покажет `TM5` как издателя только если Microsoft подтвердит `TM5` как допустимую юридическую/DBA-идентичность. Если проверенная организация имеет другое юридическое имя, именно оно будет показано в свойствах цифровой подписи.

## Вариант A — Azure Artifact Signing Public Trust (рекомендуется)

Это основной вариант для публично доверенной подписи без хранения и выгрузки закрытого ключа в GitHub Actions. Сертификаты Public Trust выпускаются через Microsoft-managed PKI; закрытый ключ остаётся в управляемой инфраструктуре сервиса.

### 1. Единственный ручной шаг — identity validation

Microsoft требует пройти Public identity validation в Azure Portal. Этот шаг нельзя завершить через Azure CLI/API, потому что он включает проверку личности/организации. После завершения скопируйте **Identity validation Id**.

Если требуется, чтобы пользователь Windows видел издателя `TM5`, сама идентичность `TM5` должна быть подтверждена Microsoft как организация/DBA. Простое имя profile `TM5` не меняет subject сертификата.

### 2. Создание account + Public Trust profile TM5

После `az login` выполните:

```powershell
pwsh -File .\tools\provision_tm5_artifact_signing.ps1 `
  -SubscriptionId "<subscription-id>" `
  -IdentityValidationId "<identity-validation-id>"
```

Скрипт:

- регистрирует `Microsoft.CodeSigning`;
- устанавливает/обновляет Azure CLI extension `artifact-signing`;
- создаёт resource group, если его ещё нет;
- создаёт Artifact Signing account Basic SKU, если его ещё нет;
- создаёт certificate profile **`TM5`** типа **`PublicTrust`**;
- выводит endpoint и account name, которые нужны GitHub Actions.

Параметры `-ResourceGroup`, `-Location` и `-AccountName` можно переопределить. Если `-AccountName` не задан, скрипт формирует стабильное уникальное имя из subscription ID.

### 3. GitHub OIDC

Repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_ARTIFACT_SIGNING_ENDPOINT`
- `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`

Отдельный secret для имени certificate profile **не нужен**: production/release workflows жёстко используют `TM5`.

App Registration, используемая GitHub OIDC, должна иметь роль **Artifact Signing Certificate Profile Signer** для profile `TM5`.

Пример endpoint зависит от региона signing account, например `https://weu.codesigning.azure.net/` для West Europe. Используйте `accountUri`, который выводит provisioning-скрипт.

Workflow выполняет `azure/login` через OIDC, затем вызывает официальный `azure/artifact-signing-action`, подписывает SHA-256 и добавляет RFC3161 timestamp через Azure timestamp service. Закрытый ключ не передаётся в репозиторий или GitHub Secrets.

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

1. `GET-Passes.exe` — основной PySide6 production candidate;
2. `GET-Passes-Legacy.exe` — временный Tkinter rollback;
3. Inno Setup включает уже подписанные EXE в `GET-Passes-Setup.exe`;
4. подписывается сам `GET-Passes-Setup.exe`;
5. все подписи проверяются через `Get-AuthenticodeSignature`.

Для Azure Artifact Signing все три файла подписываются profile `TM5`. Если этот способ не настроен, используется Key Vault PFX, затем обычный PFX fallback.

## Проверка локально

```powershell
Get-AuthenticodeSignature .\GET-Passes.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Legacy.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Setup.exe | Format-List Status,StatusMessage,SignerCertificate
```

Для production release ожидается `Status: Valid` у всех файлов.

Даже валидная новая подпись не гарантирует мгновенное отсутствие предупреждения SmartScreen: репутация нового файла/издателя может накапливаться со временем. Важны стабильная проверенная identity и последовательная подпись всех последующих версий.

## Почему код сам по себе не может сделать подпись публично доверенной

GitHub Actions может выполнить Authenticode-подпись, но не может сам назначить себе доверие Windows. Корневое доверие контролируется Microsoft Root Certificate Program/публичными CA. Поэтому локально созданный self-signed `TM5` не является заменой Public Trust и намеренно не используется в production pipeline.

## Stable release

Workflow `.github/workflows/release.yml` предназначен для versioned tags (`v2.0.0`, `v2.0.1`, ...). Он проверяет соответствие тега версии в `pyproject.toml` и отказывается публиковать stable release, если не настроен ни один доверенный способ подписи. `v2.0.0` создаётся только после физической приёмки из `docs/PHYSICAL_ACCEPTANCE_2_0.md` и проверки доверенной подписи.