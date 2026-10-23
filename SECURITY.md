# Security and privacy

These tools generate and transport privileged changes for a television that you own or administer with permission. Review the source and generated scripts. Keep physical access and a private, checked recovery kit. Do not use this on another model/build by changing pins until it passes an independent compatibility review.

## Keep private material out of this repository

Store snapshots, before-state captures, receipts, generated plans and backups outside the checkout. Generated files can contain an owner's app state and are not public templates. Never attach them to an issue without reducing them to a reviewed synthetic reproducer.

Do not post serials, MAC addresses, actual boot IDs, IP addresses from a personal network, authentication tokens, Wi-Fi settings, account details or original Samsung files. Use example addresses from the documentation ranges if needed. The repository's pattern checker is a supplementary check, not a guarantee that every kind of secret has been detected.

## Operational limits

- A successful root session does not bypass every Tizen security boundary.
- A reported command success does not prove physical picture/sound, all process termination or automatic boot execution.
- Registry changes, marker files, preferences and boot-hook installation are separate layers. A partial failure can leave some changes applied. Preserve the result and use the prepared inverse under the owner's decision; do not blindly replay.
- The blocking hook can run after recognition has already started during boot. It is not a first-frame capture guarantee.
- Native service calls do not have a proven hard end-to-end timeout. An interrupted transport does not prove a remote command was cancelled.
- Offline fixtures emulate service-manager and metadata behavior. They do not establish live restoration, new-build compatibility or crash/power-loss atomicity.
- Do not disable security updates to keep this modification working. A changed build or vendor file requires a fresh review.

## Reporting a problem

For a non-sensitive reproducible bug, open an issue with the public model/firmware, tool command with example paths/addresses, sanitized outcome and an offline synthetic test. Do not include raw session output or snapshots. For sensitive reports, use GitHub private vulnerability reporting if enabled; otherwise do not post the details publicly.
