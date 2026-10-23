# Recovery: separate the layers and the evidence

[README](../README.md) · [Reproduction](reproduction.md) · [Validation](validation.md)

**A rollback changes device state and can re-enable recognition or voice features. Obtain approval for the exact layer.** Do not run an inverse as a harmless test. The tools provide source and generated inverse operations, not the owner's private stock/backup or an emergency unbrick route.

## What was actually ready or tested

| Layer / claim | Recorded evidence | Not established |
| --- | --- | --- |
| Registry inverse | Snapshot-derived field-specific inverse for 8 + 15 targets, exact offline roundtrip and negative tests | A live full registry restoration on the TV |
| Voice/marker inverse | Original preferences and marker absence captured; private inverse prepared before writes | Reversible user experience across every function/build |
| Boot-hook recovery assets | Exact private stock and inverse retained on TV and in a durable off-TV runtime, not just prunable scratch | That retained tools will always regain access after a future update/fault |
| Native inverse admission | **Read-only prefix** checked actual intent/stock/current-hook pins and metadata without creating restore intent or restoring | Execution of the inverse's write path on the TV |
| Hook roundtrip | Complete installer → hook → inverse succeeded **offline on fixtures**, retaining runtime masks | Actual TV restoration, real reboot after restoration or emergency recovery |
| Current reference state | Hook remains installed and its boot blocking was observed | TV returned to factory/stock behavior |

These are deliberately separate claims (L1–L4 in [sources](sources.md#local-evidence-ledger)). No fresh restoration or device contact was performed while preparing this public release.

## Before authorizing any recovery

1. Identify the exact current TV/build again. Match the intended operation's private intent/receipt, snapshot, stock, inverse and current modified bytes/metadata. Do not substitute someone else's JSON before-values.
2. Verify private backups off-device, integrity, hashes, ownership/mode/security labels and required dependencies. Retained files without a usable access route are not recovery readiness.
3. Confirm a way to obtain **temporary authorized privileged access again** and a physical operator. Recovery readiness is not a guarantee that a boot-failing set can be repaired through the same tool. If access is lost, do not improvise firmware/bootloader/service-menu recovery.
4. Specify which layers to undo, whether runtime services should remain stopped, and whether a reboot/reactivation is permitted. They are not one all-or-nothing action.
5. Preserve unknown/partial state before acting. A timeout or transport failure never proves no change occurred.

## Registry / preferences / condition markers

- Use the inverse generated from **this TV's consistent before snapshot** and exact selected fields. Guard the expected current modified state before any write and use fail-fast transaction/rollback behavior already tested offline.
- Routine inverse should not overwrite the whole live database with an old snapshot: that can discard unrelated newer app state.
- Restore the three preferences to the captured values/types, not an assumed universal `True`.
- Remove only marker files whose creation and identity are established by this operation and whose original state was absent. Never delete foreign/pre-existing condition markers.
- Recheck integrity, selected and non-target rows, preferences, marker identity and actual service/process state. Restoring registry flags alone does not prove any application has restarted correctly.

## Boot hook: what the retained private inverse does

The accepted inverse is **hook-only**. It checks the exact installed wrapper, intent, original stock and metadata/security labels, stages the preserved original, then restores `/opt/etc/parseinfo.sh` to its original bytes and original metadata (observed stock mode `0777` on this build). That observed mode is **not advice to chmod arbitrary scripts or relax other builds**.

It intentionally **does not** remove runtime masks, reload systemd, start either recognition service, remove the private task directory or reboot. This avoids silently adopting foreign masks or re-enabling recognition as a side effect. Original signed stock remains private; do not download a supposedly matching stock file from an unrelated TV.

After a successful authorized inverse:

1. Independently verify stock bytes, hash, ownership/mode/SMACK and the expected restored entry path. The inverse's exit status is not the only check.
2. Expect the existing volatile masks/services to remain as before in that running kernel. Do not declare recognition restored or start it without separate permission.
3. Coordinate a separately authorized real reboot if returning to stock boot behavior is intended. Runtime masks normally disappear with a new boot; prove actual boot identity change and inspect for **other** masks/overrides rather than assuming they vanished.
4. Independently verify vendor units, actual masks, states and executable paths plus physical functions. “Stock entry restored” is not proof that every service has started.

**None of these live inverse/write/reboot steps was rehearsed on the reference TV.** Offline fixture success and native read-only admission are the actual evidence boundary.

## Partial result / access failure

Stop controls. Preserve original receipts and current hashes, filenames, masks and lock state privately. Do not replay the installer/inverse with a new output directory, delete locks/intents or run broad unmask/start commands. Ask for an independently reviewed reconciliation plan and fresh permission. A factory reset is not documented here as a guaranteed hook undo; do not use it as an unproven substitute for the inverse.

## Minimum private recovery kit

- Consistent snapshot, generated inverse SQL and original typed preference/marker state.
- Exact original signed hook, metadata and vendor-unit baselines.
- Same reviewed hook inverse and source/transport/dependency closure; authenticated hashes/manifests and offline test report.
- Actual temporary-access prerequisites and cleanup checks, physical recovery contact and explicit stop criteria.
- A plain statement of which tests were offline, which native reads passed, and which real restoration steps remain untested.

Use [the hook generator](recognition-tool.md) for the source, inverse and portable fixture harness, and [the registry planner](registry-tool.md) for snapshot-derived plans. These tools do not provide the owner's private backups or an emergency unbrick route. Keep your own exact stock, before-state, generated manifest and receipts outside the checkout. If that recovery kit or access path is incomplete, do not install persistence.
