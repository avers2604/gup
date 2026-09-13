# Цифровая подпись Windows-сборок

GET-Passes 2.0 поддерживает собственную корпоративную подпись **TM5 Private PKI** и внешние публично доверенные варианты. Для текущего внутреннего сценария приоритет в workflow такой:

1. **TM5 Private PKI**;
2. Azure Artifact Signing Public Trust;
3. Azure Key Vault PFX;
4. обычный PFX fallback.

## TM5 Private PKI — текущий вариант

Цепочка состоит из двух сертификатов:

- **TM5 Root CA** — собственный корневой центр сертификации;
- **TM5 Code Signing** — leaf-сертификат с subject `CN=TM5, O=TM5` и EKU Code Signing `1.3.6.1.5.5.7.3.3`.

Поэтому на машине, где `TM5 Root CA` добавлен в Trusted Root Certification Authorities, Windows проверяет подпись как доверенную и издатель leaf-сертификата отображается как **TM5**.

Важно: эта цепочка **не является публично доверенной** для произвольного Windows-компьютера. Доверие появляется только после установки публичного `TM5 Root CA` на конкретную машину или после централизованного распространения через GPO/Intune/другую систему управления устройствами. Microsoft рекомендует управлять доверенными корнями централизованно через Group Policy для доменных компьютеров.

Публичный root хранится в репозитории:

`certs/TM5-Root-CA.cer`

Его SHA-256 fingerprint:

`86742AE7A08246595855655EB5961417BE75A553521947CD8A26933C0B55C95C`

Приватный ключ root **никогда не должен попадать** в GitHub, CI, installer или на рабочие станции.

### Готовый signing certificate

Для созданной текущей цепочки используются два приватных файла:

- `TM5-CodeSigning.pfx` — только для подписи сборок;
- `TM5-Root-CA-Backup.pfx` — офлайн-резерв root private key для будущего перевыпуска leaf-сертификатов.

Root backup храните отдельно и офлайн. В GitHub Actions загружается только `TM5-CodeSigning.pfx`.

### GitHub Actions secrets

Нужны два repository secrets:

- `TM5_SIGN_CERT_BASE64` — base64 содержимого `TM5-CodeSigning.pfx`;
- `TM5_SIGN_CERT_PASSWORD` — пароль signing PFX.

Получить base64 локально:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("TM5-CodeSigning.pfx")) | Set-Clipboard
```

Если эти два secrets настроены, `.github/workflows/build-exe.yml` и `.github/workflows/release.yml` выбирают TM5 Private PKI раньше остальных способов подписи. Hosted runner импортирует **только публичный** `certs\TM5-Root-CA.cer` во временное хранилище `Cert:\CurrentUser\Root`, подписывает SHA-256 через `signtool`, добавляет RFC3161 timestamp и проверяет `Get-AuthenticodeSignature`.

Приватный PFX создаётся во временном каталоге runner и исчезает вместе с runner после job.

### Доверие на рабочих компьютерах

Предпочтительно раздавать root через **GPO**:

`Computer Configuration → Policies → Windows Settings → Security Settings → Public Key Policies → Trusted Root Certification Authorities → Import`

Импортируется только `TM5-Root-CA.cer`. После применения политики можно выполнить `gpupdate /force` или перезагрузить компьютер.

Для одиночного ПК есть административный helper:

```powershell
pwsh -File .\tools\install_tm5_root.ps1
```

Скрипт проверяет subject и зафиксированный SHA-256 fingerprint перед импортом в `Cert:\LocalMachine\Root`.

**Не устанавливайте root автоматически из GET-Passes Setup.exe.** Установщик приложения не должен самостоятельно расширять системное корневое доверие. Root разворачивается отдельным административным каналом.

### Перевыпуск собственной PKI

Скрипт для создания новой двухуровневой цепочки:

```powershell
pwsh -File .\tools\create_tm5_private_pki.ps1
```

Он создаёт `TM5 Root CA`, leaf `CN=TM5` с friendly name `TM5 Code Signing`, экспортирует публичные `.cer`, signing PFX и отдельный root-backup PFX. Пароли вводятся интерактивно.

Если root когда-либо перевыпускается, необходимо одновременно:

1. заменить `certs/TM5-Root-CA.cer`;
2. обновить fingerprint в `tools/install_tm5_root.ps1`;
3. заново распространить новый root на все доверенные рабочие станции;
4. заменить `TM5_SIGN_CERT_BASE64` и `TM5_SIGN_CERT_PASSWORD`.

Поэтому обычное продление делается выпуском нового leaf от существующего офлайн root, а сам root без необходимости не меняется.

## Что подписывается TM5

Production pipeline подписывает:

1. `GET-Passes.exe` — основной PySide6 production candidate;
2. `GET-Passes-Legacy.exe` — временный Tkinter rollback;
3. `GET-Passes-Setup.exe` — Inno Setup installer.

Для подписи используется SHA-256 и RFC3161 timestamp. Актуальный SignTool требует явно указывать digest (`/fd`) и timestamp digest (`/td`); в workflow оба заданы как SHA256.

Проверка на доверенной рабочей станции:

```powershell
Get-AuthenticodeSignature .\GET-Passes.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Legacy.exe | Format-List Status,StatusMessage,SignerCertificate
Get-AuthenticodeSignature .\GET-Passes-Setup.exe | Format-List Status,StatusMessage,SignerCertificate
```

Ожидается `Status: Valid` и subject leaf-сертификата `CN=TM5`.

## Публичная доверенность — опциональная альтернатива

Если в будущем GET-Passes нужно будет распространять на произвольные компьютеры вне управляемого контура, собственный root недостаточен. Тогда нужен публично доверенный code-signing сертификат или Azure Artifact Signing Public Trust.

В репозитории сохранён готовый Azure путь с техническим profile `TM5-CodeSign`. Публичное имя издателя там зависит от identity, подтверждённой Microsoft, и не может быть произвольным.

### Azure Artifact Signing

Repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_ARTIFACT_SIGNING_ENDPOINT`
- `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`

Provisioning helper:

```powershell
pwsh -File .\tools\provision_tm5_artifact_signing.ps1 `
  -SubscriptionId "<subscription-id>" `
  -IdentityValidationId "<identity-validation-id>"
```

### Azure Key Vault PFX

Fallback secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_KEY_VAULT_NAME`
- `AZURE_SIGN_CERT_NAME`
- `AZURE_SIGN_CERT_PASSWORD`

### Generic PFX fallback

Fallback secrets:

- `WINDOWS_SIGN_CERT_BASE64`
- `WINDOWS_SIGN_CERT_PASSWORD`

Не коммитьте PFX, пароли или base64 приватных ключей в репозиторий.

## Stable release

`release.yml` допускает подписанный stable release при наличии TM5 Private PKI или одного из внешних signing-вариантов. При использовании собственной PKI stable build является доверенным **внутри контура, где установлен TM5 Root CA**, а не глобально в интернете.

`v2.0.0` всё равно создаётся только после физической приёмки `docs/PHYSICAL_ACCEPTANCE_2_0.md` и проверки `Status: Valid` на целевой рабочей станции.
