# GET-Passes 2.0 — physical workstation and printer acceptance

**Status:** NOT YET COMPLETED. This checklist cannot be completed by CI. It must be executed on the target Windows workstation with the real production database copy, configured printers and operator present.

**Release gate:** do **not** create/publish stable tag `v2.0.0` until every required item below is checked, TM5 Authenticode signing is trusted on the target workstation, and the final decision is recorded as `ACCEPTED`.

## Test environment

- Date/time: ____________________
- Operator: ____________________
- Reviewer: ____________________
- Workstation / inventory ID: ____________________
- Windows version/build: ____________________
- Display scaling tested: ____________________
- Production printer model: ____________________
- Printer driver/version: ____________________
- Card/CR80 printer model (if separate): ____________________
- Candidate commit / build: ____________________
- Installer SHA256: ____________________

## TM5 Private PKI trust precondition

The selected signing route for the internal v2.0 rollout is **TM5 Private PKI**. The public root is `certs/TM5-Root-CA.cer`.

Expected root SHA-256 fingerprint:

`86742AE7A08246595855655EB5961417BE75A553521947CD8A26933C0B55C95C`

- [ ] Before installing trust, verify the root SHA-256 fingerprint matches the value above.
- [ ] Install `TM5 Root CA` into `Trusted Root Certification Authorities` through GPO/Intune or `tools/install_tm5_root.ps1` from an elevated PowerShell session.
- [ ] Verify `TM5 Root CA` is present in `Cert:\LocalMachine\Root` and no unexpected replacement root with the same display name exists.
- [ ] Verify `GET-Passes.exe` returns `Status: Valid` from `Get-AuthenticodeSignature`.
- [ ] Verify `GET-Passes-Legacy.exe` returns `Status: Valid`.
- [ ] Verify `GET-Passes-Setup.exe` returns `Status: Valid`.
- [ ] Verify the signer leaf subject contains `CN=TM5` and its EKU is Code Signing.
- [ ] Record the signing certificate thumbprint/fingerprint used for this candidate: ____________________

**Do not** import `TM5-Root-CA-Backup.pfx` or any private key on a workstation. Only the public root `.cer` is deployed to clients.

## Preconditions

- [ ] A current encrypted backup of production data was created before testing.
- [ ] Acceptance uses a controlled copy of production data for destructive restore/recovery scenarios.
- [ ] `GET-Passes.exe` and `GET-Passes-Legacy.exe` come from the same candidate package.
- [ ] Candidate EXE and Setup.exe Authenticode signatures are valid and trusted on the workstation.
- [ ] No `v2.0.0` stable release has been published before this acceptance.

## Existing data compatibility

- [ ] Start `GET-Passes.exe` against an existing `gup.sqlite3` without conversion or schema prompt.
- [ ] Existing vehicle journal rows are visible and filterable.
- [ ] Existing employee badge rows are visible and filterable.
- [ ] Existing blacklist/settings are loaded correctly.
- [ ] Existing pending issuance operations are visible in «Незавершённые».

## Vehicle pass — real print/PDF

- [ ] A4: two vehicle passes render and print with correct scale/alignment/cut line.
- [ ] A5: one vehicle pass renders and prints with correct scale/alignment.
- [ ] PDF output visually matches the approved pre-cutover renderer output.
- [ ] One-sided print succeeds on the production printer.
- [ ] Duplex-capable path prints front/back in the correct orientation.
- [ ] Manual-flip path pauses, the operator flips/reloads the sheet, and the back prints correctly.
- [ ] Successful output confirms the issuance in the journal exactly once.
- [ ] Failed/cancelled output does not create a false confirmed issuance.

## Employee badge — real print/PDF

- [ ] CR80/card mode prints at the correct physical dimensions and orientation.
- [ ] A4 single-badge mode prints correctly.
- [ ] A4 3×3/grid mode prints nine badges with correct spacing.
- [ ] Photo crop/placement and typography match the approved pre-cutover renderer output.
- [ ] Successful output confirms the badge issuance exactly once.

## Batch printing

- [ ] Vehicle CSV template imports with `;` delimiter and UTF-8-SIG.
- [ ] A CP1251 vehicle CSV imports correctly.
- [ ] Employee badge CSV imports and resolves photos beside the CSV.
- [ ] Validation preview shows expected errors/warnings before generation.
- [ ] Generated vehicle batch PDF packs two passes per A4 page.
- [ ] Generated badge batch PDF packs a 3×3 grid.
- [ ] Cancel during generation leaves no false confirmed issuance.
- [ ] If PDF exists but journal confirm is interrupted, the operation remains recoverable.

## Recovery and journals

- [ ] Simulate an unfinished direct-print operation and confirm it from «Незавершённые».
- [ ] Cancel an unfinished operation and verify it disappears without journal confirmation.
- [ ] Open an existing generated file from «Незавершённые».
- [ ] Edit a journal record and verify history records the change.
- [ ] Revoke a record and optionally add it to blacklist.
- [ ] Export the current journal page to XLSX and open the file successfully.

## Backup/restore

- [ ] Create an encrypted `.gupbak` with a test password.
- [ ] Inspect the archive and verify checksum/integrity status before restore.
- [ ] Restore to the controlled test data set and verify SQLite integrity.
- [ ] Test a failed restore and confirm rollback leaves the previous database usable.
- [ ] Confirm unencrypted ZIP is visibly identified as containing potentially personal data.

## Display / DPI / interaction

- [ ] 100% Windows scaling: no clipped controls or unusable dialogs.
- [ ] 125% Windows scaling: no clipped controls or unusable dialogs.
- [ ] 150% Windows scaling: no clipped controls or unusable dialogs.
- [ ] 200% Windows scaling: no clipped controls or unusable dialogs.
- [ ] Light theme is readable.
- [ ] Dark theme is readable.
- [ ] Long-running batch/backup operations keep the GUI responsive and cancellation works.

## Packaging and rollback

- [ ] Install `GET-Passes-Setup.exe` successfully.
- [ ] Normal shortcuts launch `GET-Passes.exe` (PySide6), not the rollback executable.
- [ ] `GET-Passes.exe --self-test` exits with code 0 on the workstation.
- [ ] `GET-Passes-Legacy.exe --self-test` exits with code 0 on the workstation.
- [ ] Launch `GET-Passes-Legacy.exe` interactively and verify the Tkinter fallback can access the same existing data.
- [ ] Uninstall removes both executables while preserving user data according to the existing application policy.

## Final decision

- [ ] All mandatory checks above passed.
- [ ] No renderer/layout regression was observed on printed output.
- [ ] No data-loss/schema-compatibility issue was observed.
- [ ] Rollback path was demonstrated successfully.
- [ ] TM5 Root CA trust is deployed to the intended workstation population.
- [ ] Signed stable workflow is configured with the TM5 code-signing PFX secrets.

Decision: **PENDING / ACCEPTED / REJECTED**

Blocking observations / ticket links:

______________________________________________________________________________

______________________________________________________________________________

Operator signature: ____________________  Date: ____________________

Reviewer signature: ____________________  Date: ____________________
