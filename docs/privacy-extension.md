# Optional second privacy pass

[Assessment and trade-offs](community-privacy-review.md) · [Recovery](recovery.md)

`tools/privacy_extension.py` generates an additive, offline-only plan for the
exact already-installed visual wrapper and Q70D build. It does not contact a TV.
It refuses a stock hook, changed vendor pins or an existing output directory.
Do not run the original visual installer again to add this extension.

## Reference deployment status

On the reference Q70D, the extension's six flag triples and two markers were
applied once. Independent readback checked all 499 rows: only the six selected
triples changed, with the earlier profile and VIF preserved. The four additional
units were observed masked-runtime and inactive; the three service units had
MainPID=0. The preserved visual layer also completed successfully.

The first extension activation did not complete successfully: its checker
incorrectly required service-only MainPID on `wifi-presence.path`. That failure
was retained rather than relabeled as success. The correction accepts missing
MainPID only on that exact path unit and preserves strict PID checks elsewhere.
The corrected block, wrapper and hook inverse were installed through a separately
reviewed, fixed-file update, with independent hash/mode/SMACK readback. That
private migration is not a reason to rerun the create-once installer.

A requested normal systemd reboot was rejected because the reference firmware
has no `reboot.target`. No alternate forced reboot or repeated activation was
performed. The owner subsequently restarted the TV with the physical remote.
Independent read-only observation confirmed a changed kernel boot identity,
fresh successful receipts from both hook layers, released locks, all six runtime
masks and inactive targets. The five service units had MainPID=0; the `.path`
correctly omitted that service-only property. No selected voice, sensor,
discovery, remote-support or visual-recognition executable was observed. All
incomplete process reads were classified as kernel threads or zombies, with no
unclassified live user process.

The guarded extension readback passed. All 499 flag triples, four false
voice/sound-detection preferences, selected markers and approved hook/recovery
hashes and metadata were preserved. The selected shared services remained
active. Nothing was reinstalled or manually activated during verification.
Temporary access was closed and the TV was turned off through its existing local
control, corroborated by independent API PowerState=standby. Family
picture/audio/streaming/remote acceptance is separate and was not independently
observed. Prepared recovery and offline roundtrips are not an on-TV restoration.


## Selection

Six additional registry app IDs, with desired text flags `true,false,false`:

- `com.samsung.tv.tvsensor-iot-service`
- `org.tizen.voice-app`
- `org.tizen.voice-app-service`
- `org.tizen.voice-client`
- `org.tizen.voice-onboarding`
- `org.tizen.stt-client`

The existing 23-component profile is unchanged. Two owned markers use the actual
negative conditions of `org.tizen.voice-app.service` and
`org.tizen.voice-client.service`. Positive `AFTER_PRODUCTION` conditions remain
part of admission; the generator does not reset or remove them.

Four additional runtime masks are reapplied by the new hook:
`wifi-presence.path`, `wifi-presence.service`, `remote-management.service` and
`remote-shop-care-hub.service`. The `.path` is stopped before its service.

VIF, `remote-server`, `user-presence`, general sensors, audio, Bluetooth,
accessibility/TTS, DRM and streaming applications remain outside this selection.
See the assessment for residual surface and functional trade-offs. Voice control,
dictation and assistant speech can be lost. Sensor/Hue/connected-camera
functionality can be lost. This is not electrical microphone disconnection or a
guarantee against recording by every independent third-party application.

## Capture and generate privately

Capture an authentic standalone SQLite snapshot using SQLite backup, not a live
file copy. Validate integrity, unique selected rows and text flag types; retain
all other rows for independent preservation checks. Capture the exact current
AWK hook and its owner/mode/SMACK metadata, the four real unit hashes, both
launchers' complete conditions, absent markers and absent override masks. Do not
infer unit names from app IDs. Keep all captures outside this checkout.

The `--before` JSON must contain exactly:

- `schema_version`: integer `1`.
- `tested_identity`: the exact identity object from `tools.registry.IDENTITY`.
- `markers`: two `{path, state}` entries for the selected marker paths, each
  observed `absent`.
- `unit_conditions`: two `{unit, ConditionPathExists}` entries for the actual
  voice launcher units. Each value is the captured list containing its negative
  marker and, when present, its positive `AFTER_PRODUCTION` condition.

Never fabricate BEFORE from these instructions. The CLI pins the native prior
hook and units; it provides no path/pin override. The Python renderer's overrides
exist for synthetic tests only, not for forcing hardware compatibility.

```sh
python3 -B tools/privacy_extension.py \
  --snapshot /private/captured.db \
  --before /private/captured-before.json \
  --previous-hook /private/captured-previous.awk \
  --output /private/new-extension-plan
```

The output parent must already exist. Eleven private files are generated:
`manifest.json`, `previous.awk`, `apply.sql`, `inverse.sql`, `app-apply.sh`,
`app-inverse.sh`, `hook-install.sh`, `hook-inverse.sh`, `block.sh`, `wrapper.awk`
and `selected-readback.sh`. Review their exact bytes and hashes before use.
Generation is create-once, not an atomic multi-file publication.

## Separate installation, application and activation

1. Review the complete transport and recovery closure. Native Bash, AWK, base64,
   gzip for large envelopes, SQLite and the exact factory metadata must match.
   Prepare temporary administrator access and finite cleanup without opening
   the rest of the LAN.
2. Under explicit installation authority, submit `hook-install.sh` once. It
   saves a native database backup, both inverses and the exact previous AWK in
   `/opt/usr/share/hermes-privacy-extension-v1`, then stages and replaces the
   hook. It does not activate the hook or stop processes. Independently verify
   installed files, hashes, metadata and the unchanged prior visual package.
3. Under explicit app-change authority, submit `app-apply.sh` once. It captures
   another native backup, changes only the six selected flag triples and creates
   the two owned markers. It does not terminate already-running applications.
4. Only after current-state checks and separate activation authority, use the
   existing `AT-HUB.service` consumer. `tools.recognition.activation()` accepts
   the generated wrapper hash and checks an exact successful `inactive` state
   before its one nonblocking start. Verify terminal service exit and both the
   old two-unit and new four-unit per-boot receipts independently.
5. Observe selected fields, exact mask ownership, inactive state for all four
   units and MainPID=0 for the three services, plus target process absence.
   The pinned `.path` unit has no service-only MainPID property on Tizen;
   absence is accepted only there, while any reported PID must be uniquely zero.
   Existing processes can survive flag
   changes; do not broad-kill by names or a shared loader. Coordinate a real
   restart when necessary, then require a changed kernel boot ID, fresh success
   receipts and process absence without replaying install/apply/activation.
6. Check normal TDT, YouTube, streaming, audio, remote and HA behavior. API
   reachability is not audiovisual playback acceptance.

For stdin-fed transport, preserve positional arguments inside the encoded script:

```python
from pathlib import Path
from tools.tv_session import envelope
command = envelope(b"set -- --authorize\n" + Path("/private/new-extension-plan/hook-install.sh").read_bytes())
```

The same `--authorize` argument is required by app apply and both inverses.
`selected-readback.sh` takes `before` or `after`, not `--authorize`; include that
argument in its encoded bytes too. Readback requires the installed extension
directory. The `after` mode additionally checks the new hook hash, successful
current-boot receipt, released lock, four inode-owned masks and unique
systemctl properties. Reconcile failures from saved results rather than renaming
an output directory to repeat a consumed operation.

## Split recovery

`hook-inverse.sh` restores the exact previous AWK hook, mode 755. It deliberately
retains current runtime masks and neither reloads nor starts services. A later
coordinated restart removes the new volatile masks; the original visual hook
continues to apply its original two masks.

`app-inverse.sh` restores only the six captured flag triples and removes only
owned new markers. It does not overwrite the whole database or start apps.
Each inverse is explicit and one-shot; an interrupted inverse requires manual
reconciliation. Do not execute recovery merely to test it if that would
reactivate unwanted microphone functionality. Restore the extension hook before
considering recovery of the older visual hook: the two layers have different
ownership and guards.

## Verification boundaries

Synthetic tests exercise actual generated transport envelopes, shell, AWK,
SQLite and files, with UID/SMACK, service-manager effects and native paths
doubled/relocated. They include preservation, replay, drift, foreign masks,
ordinary failures and split inverse behavior. They are not hardware tests.

The model assumes a cooperative administrator, not hostile root. There is a
possible early-boot window. Native calls have no hard per-call deadline. There
is no promise of crash/power-loss atomicity, zero telemetry, electrical microphone
isolation, measured speed gains or survival of firmware updates. Changed bytes
or metadata require review, not weakened guards.
