# Offline registry, voice and condition-marker planner

## Boundary and prerequisites

`tools/registry.py` **only reads local inputs and writes a private plan**. It makes no network/device calls, runs no generated script, uninstalls nothing and never reboots. Python 3.11+ standard library is sufficient for generation. Executing the reviewed shell output separately requires a trusted root session, POSIX `sh`, `awk`, `sqlite3`, `vconftool` and `systemctl` on the TV.

Only **TQ55Q70DATXXC / Q70D / 55 inches / Tizen 8.0 / ARMv7 32-bit / T-PTMLDDEUC-1400.0** is supported. Check model/firmware on screen and OS/CPU using the authorized session before capturing inputs. Identity in JSON is an operator attestation, not automatic hardware authentication. Another build means stop, not edit the profile to match. The exact 23 IDs, three text flag fields, three preferences and five markers/six consumers are fixed and checked against the repository profile. Historical `observed_before` values in that profile are **never** used as actual rollback data.

Voice assistants, wake-word operation and related voice features are deliberately lost. Obtain the owner's acceptance first. Accessibility/text-to-speech, launcher, streaming apps and other unselected rows are not targets. Registry flags do not terminate already-running processes. The scripts request one `systemctl stop` for the six authenticated marker-consumer units; no process killing, polling/stop loops or auto-start. A coordinated reboot remains a separate manual action. This release adaptation is offline-tested, **not newly hardware-tested**.

## Capture your own inputs privately

Use one stable maintenance interval with no other registry/preferences writer. Export a **consistent standalone SQLite backup**, not a raw copy of a database potentially using WAL. A reviewed read-only SQLite `.backup` of `/opt/dbspace/.pkgmgr_parser.db` is one way to obtain the snapshot. Transfer it privately, close the export and ensure no `-wal`, `-shm` or `-journal` sidecars accompany it. Never discard a real live WAL to make an inconsistent copy pass. The generator opens the snapshot read-only/immutable, checks integrity, rejects registry triggers, requires exactly one row for each selected ID and hashes before/after reading. This detects source movement; it cannot prove that an operator's original export was honest or simultaneous with preference capture.

For each preference, preserve the actual output of `vconftool get KEY`. Accepted native output is exactly `KEY, value = True (Boolean)` or `KEY, value = False (Boolean)`. Record the observed JSON Boolean, not `1`, a string or a copied historical default.

For **all five** paths, verify both `test ! -e PATH` and `test ! -L PATH`. A dangling symlink is not absence. For **all six** units, review `systemctl cat UNIT`, including drop-ins. This bounded tool supports exactly one `ConditionPathExists=!PATH` entry per unit, with the mapping below and no reset/additional positive conditions. Record the actual effective value as a one-item array; do not infer it from a package/unit name. Additional or uncertain conditions require separate review and are rejected by generated native checks.

Keep the raw observations, DB, `BEFORE.json`, generated files, hashes and receipts outside the repository. JSON may contain only the following exact fields. This is a **synthetic shape example**, not an attestation or default capture; replace each preference value with your actual typed observation and verify every condition/absence:

```json
{
  "schema_version": 1,
  "tested_identity": {
    "model": "TQ55Q70DATXXC",
    "family": "Q70D",
    "diagonal_inches": 55,
    "tizen": "8.0",
    "architecture": "ARMv7 32-bit",
    "firmware": "T-PTMLDDEUC-1400.0"
  },
  "preferences": [
    {"key": "db/menu/voice/voice_activated", "type": "Boolean", "value": true},
    {"key": "db/si_service/voice_recog_enable", "type": "Boolean", "value": false},
    {"key": "db/multi-assistant/prelaunch_mode", "type": "Boolean", "value": true}
  ],
  "markers": [
    {"path": "/opt/usr/share/systemd/system/pisa-service", "state": "absent"},
    {"path": "/opt/usr/share/systemd/system/canalysis-daemon", "state": "absent"},
    {"path": "/opt/usr/share/systemd/system/com.samsung.tv.bixby-prov", "state": "absent"},
    {"path": "/opt/usr/share/systemd/system/com.samsung.tv.ondevice-voice", "state": "absent"},
    {"path": "/opt/usr/share/systemd/system/com.samsung.tv.farfieldvoice", "state": "absent"}
  ],
  "unit_conditions": [
    {"unit": "pisa-service.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/pisa-service"]},
    {"unit": "adagent-service.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/pisa-service"]},
    {"unit": "canalysis-service.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/canalysis-daemon"]},
    {"unit": "com.samsung.tv.bixby-prov.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/com.samsung.tv.bixby-prov"]},
    {"unit": "com.samsung.tv.ondevice-voice.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/com.samsung.tv.ondevice-voice"]},
    {"unit": "com.samsung.tv.farfieldvoice.service", "ConditionPathExists": ["!/opt/usr/share/systemd/system/com.samsung.tv.farfieldvoice"]}
  ]
}
```

Unknown/missing/duplicate selected identifiers, duplicate JSON keys, different types/identity, a present marker, mismatched condition or non-text/non-Boolean database flags cause refusal before output creation. Other legitimate database rows remain present and are not treated as unknown targets. Inputs must be regular non-symlink files. Do not run the planner against a changing/live database or untrusted DB provided by someone else.

## Generate and inspect

Run from the repository, using private absolute paths in environment variables. The output parent must exist and `OUT` itself must not exist:

```sh
python3 tools/registry.py --snapshot "$SNAPSHOT" --before "$BEFORE" --output "$OUT"
```

The output is a new mode-0700 directory with mode-0600 files:

- `apply.sql`: all selected uniqueness/type/before guards, then 23 field-specific updates in one SQLite transaction.
- `inverse.sql`: checks that every selected tuple is either the captured tuple or desired tuple, then restores only the three captured fields. It is not a whole-database replacement.
- `apply.sh`: embeds its checked SQL and live guards, makes a private online SQLite backup and create-once stage receipts, changes preferences/markers with readback, stops only six exact units and publishes completion only after final verification.
- `inverse.sh`: validates the matching plan/run receipts and entire recovery set before writes; uses intents to recover ordinary partial application and readbacks every restored field/preference/marker.
- `selected-readback.sh`: verifies all selected tuples, typed preferences, exact consumer conditions and five marker states, using `before` or `after` mode.
- `manifest.json`: exact identity, actual selected before tuples/preferences/conditions, source digest, plan binding and generated-file hashes. This is **private**, not suitable for committing or attaching to an issue.

No personal snapshot path or historical private digest is embedded in public code. Generated private output necessarily contains the current owner's captured values/digest. Generation refuses output inside the repository after realpath resolution, including a symlink alias into it. Existing output is never overwritten. After an output I/O failure, preserve the incomplete private directory for diagnosis and use a different new output directory; do not treat partial output as a valid plan.

Review the manifest and all scripts/SQL before transport. Never replace native paths or weaken guards for a real TV. The test suite relocates those paths **only inside synthetic offline fixtures**. A trusted environment/PATH, exclusive maintenance interval and private, operator-controlled directory ancestors are prerequisites; this is not a hostile-local-root/concurrent-writer defense.

## Explicit native use (not performed by generation)

After a separately authorized transport/session has placed the reviewed scripts privately on the exact TV, these are the native command shapes. `PLAN` and `RUN` below are private absolute TV paths, not controller paths. `RUN` must be a new directory with an existing private parent. The scripts are intentionally non-executable files; invoke `sh` explicitly:

```sh
sh "$PLAN/selected-readback.sh" before
sh "$PLAN/apply.sh" --authorize "$RUN"
sh "$PLAN/selected-readback.sh" after
# Only if restoration is desired or ordinary apply failed:
sh "$PLAN/inverse.sh" --authorize "$RUN"
sh "$PLAN/selected-readback.sh" before
```

The runtime DB is fixed at `/opt/dbspace/.pkgmgr_parser.db`. Both generation output and native run paths must stay private/outside any repository. `apply.sh` creates `RUN`, its `plan.bound` receipt, consistent `before.db` backup and finite stage `*.intent` / `*.complete` files. Each receipt contains the current plan binding. A second apply to the same run refuses. Completion receipt existence alone is not a substitute for a fresh readback or proof of feature/boot acceptance. Preserve the original plan and run together; a new snapshot-derived plan is not interchangeable with an older run's inverse.

On ordinary setter failure, including a setter that changed state and then returned nonzero, apply exits nonzero and leaves no `apply.complete`. The inverse admits only captured/desired values, checks stage ownership and restores preferences whose setter intent was recorded. Missing/foreign/changed markers are never blindly deleted. The three SQL fields are restored without reverting unrelated fields/rows. Database rollback does not restart services. Inverse **never starts** any unit and does not reconstruct prior running state; coordinate a separate manual reboot and physical validation if appropriate.

This is **not crash-atomic** across SQLite, preferences, marker files and receipts. No `fsync` durability/power-loss guarantee, automatic rollback, concurrency lock or arbitrary-corruption repair is claimed. Intents allow bounded ordinary-failure recovery, not a promise that every possible interruption is recoverable. Drift, foreign marker content, an unowned run, unknown intermediate data or a failed inverse requires stopping and reviewing private evidence; do not rerun apply, replace the DB wholesale or force guards. Each command returns failure if its own setter/readback fails; a transport must also honor the real child exit. Readback does not prove zero network tracking or termination of every running process.

## Offline verification

```sh
python3 -m unittest discover -s tests -p 'test_registry.py' -v
python3 tools/registry.py --help
```

Tests use a real synthetic SQLite database with the 23 selected IDs plus a preserved non-target, mixed before tuples and mixed true/false preferences. They execute generated SQL and real `sh` scripts through apply → readback → inverse, relocating only native filesystem paths and faking only root identity/`vconftool`/`systemctl`. They check all 69 field drifts and each of 23 missing rows, non-target preservation, invalid captures, readback drift, create-once output, foreign markers and partial setter failure. They contact no TV/network and require no root. Local `sqlite3` and `sh` are required for the generated-shell tests.

## Español: límites y uso

El generador es **sin conexión** y no instala ni ejecuta nada en el televisor. Solo admite la identidad exacta indicada arriba. Las preferencias y tuplas anteriores proceden de **tu propia captura coherente**, nunca de los valores históricos del perfil público. No copies los valores de ejemplo como si fueran observaciones reales.

Obtén una copia SQLite consistente y autónoma, captura los tres valores Boolean reales con `vconftool get`, comprueba ausencia de los cinco marcadores (también ausencia de enlaces simbólicos) y revisa las condiciones reales de los seis consumidores. `BEFORE.json` debe seguir exactamente el esquema completo anterior. Guarda todos los datos y resultados fuera del repositorio.

Genera con `python3 tools/registry.py --snapshot "$SNAPSHOT" --before "$BEFORE" --output "$OUT"`. Revisa los seis archivos producidos. La ejecución es una decisión posterior y explícita: `selected-readback.sh before`, `apply.sh --authorize "$RUN"`, `selected-readback.sh after`; para recuperar, `inverse.sh --authorize "$RUN"` y una nueva lectura `before`, siempre mediante `sh` en la sesión autorizada y con rutas privadas del televisor.

Se deshabilitan deliberadamente funciones de voz. No hay desinstalación, señales a procesos, bucles de parada, arranque automático ni reinicio automático. Solo se solicita parar las seis unidades exactas; no se promete que todas las aplicaciones ya en ejecución desaparezcan. La recuperación restaura exclusivamente los tres campos seleccionados, los valores Boolean capturados y la ausencia autenticada de marcadores. No restaura el estado de ejecución de los servicios y **no es atómica ante cortes de alimentación**. Ante deriva, marcadores ajenos o fallos, conserva las pruebas privadas y detente; no fuerces las comprobaciones. La adaptación publicada está probada con fixtures locales, no mediante una nueva instalación física.
