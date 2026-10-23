# Reproduction workflow and stop gates

[README](../README.md) · [Persistence](recognition-persistence.md) · [Recovery](recovery.md) · [Validation](validation.md)

These are staged instructions for an explicitly authorized operator. The repository provides offline generators and a temporary-session adapter, but neither reading this guide nor generating a plan authorizes connecting or making a change. The public profile is reference data, not a device execution plan.

## 0. Agree on the scope

Record separate owner decisions for: temporary privileged access; the 8 advertising registry targets; the 15 voice targets and three preferences; the five verified service-condition markers; the persistent two-service recognition hook; activation; a real reboot; and any restoration. A grant for one stage does not authorize the next. No unattended reboot or restoration “just to test.”

Tell the owner that voice assistants/wake-word features are deliberately disabled. Preserve launcher, streaming apps, text-to-speech/accessibility and shared dependencies. No blanket uninstall or global service blacklist. No firmware/bootloader changes or global UEP disabling. Maintenance access must close; persistent blocking is not persistent remote-root access.

**Checkpoint:** exact requested features, excluded features, allowed side effects, physical operator availability, backup location and stop conditions are agreed privately.

## 1. Identify the actual TV and access prerequisites

Compare the on-screen About TV information with the access tool's OS/CPU capabilities. The reference identity is **TQ55Q70DATXXC / Q70D 55-inch / Tizen 8.0 / ARMv7 32-bit / T-PTMLDDEUC-1400.0**. Do not publish the serial, MAC, unique IDs, actual boot IDs or account data.

Use Samsung's developer-mode instructions as the official access-setup reference; menu labels vary and must be checked on the actual TV.[4] Use the **chris-ritsen/samsung-tv-root** project for its own access requirements, compatibility statements, source/release verification and cleanup behavior.[1] The historical local access used version 0.0.9-era tooling; this release does not claim that an unpinned current release is identical, nor redistribute its binaries or repeat exploit instructions. Review the chosen revision/license, verify downloads, follow upstream compatibility gates and obtain explicit root-access permission. Do not guess a route when requirements fail.

Even the same model string is insufficient if firmware bytes, schema, unit definitions, interpreter behavior, filesystem labels or access behavior differ. **Different model/build or unknown compatibility → STOP and create a separately reviewed profile**, not a relaxed allowlist. Do not downgrade or disable security updates to force compatibility.

## 2. Capture a private, consistent before-state

Do this **before the first mutation**, and retain an off-TV copy in durable private storage:

- A SQLite-consistent snapshot of `/opt/dbspace/.pkgmgr_parser.db` using SQLite's backup mechanism, not a casual live-file copy. Record `PRAGMA quick_check;` and require `ok`. Preserve relevant journal/WAL state consistently; never delete a sidecar to make a validator pass.
- Database schema and all registry rows for a local diff. The reference table is `package_app_info`, key `app_id`, with text-valued `app_disable`, `app_onboot`, `app_autorestart`. Record counts and uniqueness; **499 was observed, not a universal schema constant**.
- Exact before values **and Boolean types** of the three preference keys in the profile.
- Presence/absence, symlink status, bytes and metadata of the **five exact marker paths**; full definitions and state of their six consumer units, including `.path`/dependency activation routes.
- Hashes, modes, UID/GID, SMACK/transmute metadata, symlink status and original bytes for the existing hook, relevant vendor units and intended parent directories. Preserve the signed Samsung stock privately; do not put it in a public repository.
- Selected executable paths/UIDs and service states, private kernel `boot_id`, requested physical baseline tests and integrity/hash manifests.

Extract and verify the backup on the controller without running any recovered executable. A file with a familiar name is not a verified backup. Keep a written route for obtaining authorized temporary access again after reboot, plus physical access if software access fails. No verified backup or no plausible recovery access → **STOP**.

## 3. Generate the registry plan and inverse from that snapshot

Reference selection: [23 proven app IDs and observed before flags](../profiles/tq55q70datxxc-tizen8-1400.0.json). The selection was reconstructed from authentic apply guards and matching field-specific inverse SQL (L1/L2), then checked against accepted postboot readback (L4). **Do not execute the historical before flags as your inverse.**

The historical changes used two separate groups (8 advertising, then 15 voice). The public planner deliberately bundles all 23 targets, three preferences and five markers into one admitted plan. Obtain approval for the complete bundle; partial/group-only operation is not supported by this CLI. For that plan:

1. Require each exact selected `app_id` once. Missing/duplicate rows, unexpected types/values, extra IDs or schema drift must abort before writes. Do not select by a substring such as “voice” or “ad.”
2. Generate `apply.sql` and `inverse.sql` in private storage from the same immutable snapshot. Apply changes only the three selected fields to the text tuple `('true','false','false')`. Inverse restores **each row's recorded values**, not “enable everything.”
3. Each plan uses a transaction (`BEGIN IMMEDIATE`) and checked assertions for the complete expected before-state **before any update**. Use a fail-fast SQLite client/driver; the historical operations used `sqlite3 -bail`. A SQL CHECK error alone is **not** a portable guarantee that a caller stops, rolls back or never continues to COMMIT. On any exception, roll back and verify unchanged data. Do not ship/reuse SQL without testing the exact execution path.
4. Use the generated selected-state readback and independently capture an all-row before/after diff. The tool does not generate that full-database diff. Preserve all non-target fields and IDs; do not replace the database with the old snapshot as routine rollback.
5. Independently review the exact files and freeze hashes before obtaining write permission.

### Required offline tests, on copies only

- Apply touches exactly the selected rows and three fields; all other data and IDs match.
- Apply → inverse returns the original registry values exactly.
- For **every target**, change each expected before field, remove the row, and simulate a duplicate row in a suitable fixture. Each must reject with no partial changes. Preserve the real schema in normal tests; use an explicitly altered fixture only to exercise duplicates where a unique constraint otherwise prevents them.
- Repeat the apply and inverse; create-once guards must reject replay rather than quietly accept uncertain state.
- Exercise the actual client's error/rollback behavior, not only the SQL statements in isolation.

A host SQLite fixture test proves the tested fixture/driver behavior, **not** the TV's full runtime or application behavior. Use [tools/registry.py](registry-tool.md) for the snapshot-derived planner and its documented input schema. Inspect and test the generated output; it is not an unattended deployment.

## 4. Verify service conditions; do not invent marker files

The historical workflow also used existing `ConditionPathExists=!<path>` checks. Registry flags alone were not the whole block. The five marker basenames and consumers were:

| Under `/opt/usr/share/systemd/system/` | Existing consumer units |
| --- | --- |
| `pisa-service` | `pisa-service.service`, `adagent-service.service` |
| `canalysis-daemon` | `canalysis-service.service` |
| `com.samsung.tv.bixby-prov` | `com.samsung.tv.bixby-prov.service` |
| `com.samsung.tv.ondevice-voice` | `com.samsung.tv.ondevice-voice.service` |
| `com.samsung.tv.farfieldvoice` | `com.samsung.tv.farfieldvoice.service` |

**Read the actual unit definitions first.** Require the exact negative condition and verify every target path absent, not a symlink or foreign file. Capture that before-state and a narrow inverse before creating anything. Do not create markers because their names “look right,” overwrite an existing marker, or remove a file not created by your operation. These markers are **not** the visual services' runtime masks.

## 5. Apply and inspect each authorized registry/voice stage once

Use only the frozen reviewed plan and its create-once intent/receipt protocol. After approval of the complete public bundle, run it once and independently observe all 23 targets, three preferences and five markers. Do not attempt to split the generated SQL or reuse its receipts for group-only changes. Voice preferences are:

| Key | Reference before | Desired |
| --- | --- | --- |
| `db/menu/voice/voice_activated` | `True (Boolean)` | `False (Boolean)` |
| `db/si_service/voice_recog_enable` | `True (Boolean)` | `False (Boolean)` |
| `db/multi-assistant/prelaunch_mode` | `True (Boolean)` | `False (Boolean)` |

The historical native setter used `vconftool`'s Boolean type with false value `0`; that describes the observation, **not an instruction to write unverified keys**. Require the exact before output/type, fresh authorization and inverse. Leave unknown keys such as `wakeupless_status` alone.

After each stage, require integrity `ok`, exact selected tuples, unchanged non-target rows/fields, exact typed preference readback and marker identity. Registry flags do not terminate running processes. In this case ACR/targeted-ad and some voice executables reappeared after TERM; repeating the SQL was not a fix. `app_launcher -t` reporting “not available” was **not** proof of absence.

If process termination is separately authorized, first identify exact executable, UID and current PID; recheck identity immediately before signaling. Never `killall`, partial-match a process name, or kill shared .NET loaders. Prefer an owner-coordinated reboot and observation rather than escalating a stop/restart fight. The recorded native allowlist is not a cross-build guarantee.

**Unknown result, timeout or cleanup failure:** retain the original output and independently inspect state. Do not rename the output directory, delete the intent or reapply to obtain a nicer result.

## 6. Prove registry persistence with a real boot

With owner approval, record before `boot_id`, let the owner perform a full reboot, then obtain read-only target-state checks without reapplying SQL, preferences or service controls. A changed `/proc/sys/kernel/random/boot_id` is required; standby or an interface restart is not proof of kernel reboot.

Require 23 selected tuples intact, unchanged non-target set, all three preferences false, relevant conditions/markers intact and selected executables absent with incomplete `/proc` reads classified. Ask for picture and sound, plus the named use-case tests in [validation](validation.md). The historical first registry reboot passed these selected checks; general acceptance must not be inflated into app playback coverage.

## 7. Visual-recognition persistence

The generic visual provider and UI detector are a separate decision, not silently included with the 23 registry flags. Read [the mechanism](recognition-persistence.md), [the generator instructions](recognition-tool.md) and [recovery](recovery.md). Generate the pinned package offline, inspect its manifest and inverse, and complete the stated native prerequisites before authorizing installation. The portable public adaptation has offline coverage, not a new hardware installation.

## 8. Optional owner-operated privacy controls

- Optional viewing-information/ACR consent and interest-based advertising consent are separate controls in Samsung's notices.[5][6] Inspect the actual menu. Declining optional choices is not a reason to reset Smart Hub or revoke required terms. It does not remove every ad or control third-party app practices.
- A later European e-manual documents Terms & Privacy / Privacy Choices, but does not prove the exact labels on this firmware.[7]
- The quick-start guide covering Q7*D describes a TV microphone switch at the bottom or lower rear; locate it safely on the actual set without guessing its exact position/direction.[8] Turning it off can disable microphone-dependent voice/sound functions. The remote has a separate microphone; do not claim its electrical isolation.
- HbbTV can be turned off manually if the owner does not want interactive broadcast features. Terrestrial picture/sound and interactive HbbTV are different tests. Do not write a numeric configuration value copied from another TV; the recorded menu change is not a portable Boolean API.

The reference owner confirmed these controls, but future operators must check their own screen. Record human confirmation as human evidence, not remote measurement.

## 9. Close access and preserve a reviewable record

Close the temporary root/staging session and owned access tools; verify no unexpected task listener or persistent access agent remains. Reconcile any temporary controller-side access allowance only through the access workflow's reviewed cleanup; this guide provides no network configuration. Persistent hook blocking, if separately approved and installed, must be distinguished from maintenance access.

Keep private: original backup, exact plan/inverse, hashes, authorization, real exit statuses, selected readback, process classifications, changed-boot comparison, physical results and cleanup outcome. Publicly share only a reviewed sanitized projection.

## Sources

[1] https://github.com/chris-ritsen/samsung-tv-root
[4] https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/tv-device.html
[5] https://smarthub.termsnprivacy.com/terms/ES_es/viewing/viewing_20260430.json
[6] https://smarthub.termsnprivacy.com/terms/ES_es/syncplus/syncplus_20260629.json
[7] https://downloadcenter.samsung.com/content/UM/202511/20251123111143001/BN81-27185C-660_EUG_ROPDVBEUF_EU_ENG_250804.0.pdf
[8] https://downloadcenter.samsung.com/content/EM/202601/20260128035857001/BN68-19260E-03_SUG_Y24%20QLED%20UHD%20QD%20LS03_XC_L09_260123.0.pdf
