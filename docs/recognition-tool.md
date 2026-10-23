# Visual-recognition persistence: offline generator

## English

**Supported reference only:** TQ55Q70DATXXC (Q70D 55-inch), Tizen 8,
ARMv7, firmware `T-PTMLDDEUC-1400.0`. Matching names are not enough: the
generated scripts pin the stock hook and all three relevant vendor unit files.
Never change the pins to force another television or firmware to match.
No Samsung script, firmware file or personal installation input is distributed.

### Generate, inspect, test

Python 3.11+ and its standard library suffice for generation. This command only
writes files; it never connects, pairs, opens a root session, installs, runs the
hook, calls systemctl or reboots anything:

```sh
OUT="$HOME/samsung-private/recognition-$(date +%Y%m%d-%H%M%S)"
python3 tools/recognition.py --output "$OUT"
python3 -m json.tool "$OUT/manifest.json"
for name in installer.sh inverse.sh block.sh activate.sh; do
    sh -n "$OUT/$name" && bash -n "$OUT/$name" || exit 1
done
# Parse the entire generated AWK without executing its BEGIN/system() actions:
printf 'BEGIN { exit 0 }\n' | awk -f - -f "$OUT/wrapper.awk"
```

`OUT` must be a **new directory outside the repository**. Realpath containment
also rejects a symlink alias into the repository. Existing directories, files
and dangling symlinks are refused, including an earlier successful output.
Choose a new name rather than overwriting evidence. The directory is created
with mode 0700; each of its six files has mode 0600. They are deliberately not
host-executable. Parent directories use the operating system's normal umask.
Creation is exclusive/no-clobber, **not** a crash-atomic multi-file transaction;
a write failure can leave an incomplete private output. Do not use that output.
Keep scripts, manifests, stock backups and receipts outside version control.

Files:

| File | Meaning |
| --- | --- |
| `installer.sh` | Validate the pinned vendor baseline, preserve stock, prepare the package and replace the hook; **does not execute the hook**. |
| `wrapper.awk` | Real AWK hook: authenticated stock runs first via bash; blocking runs only after its success. |
| `block.sh` | Authenticate metadata/unit pins, own two runtime masks and verify inactive/no-PID state. |
| `inverse.sh` | Authenticate the installed wrapper and saved stock; restore **only** the hook. |
| `activate.sh` | Check the exact generated wrapper SHA-256 and require successful, exactly `ActiveState=inactive` AT-HUB output before requesting its nonblocking start. |
| `manifest.json` | Model/build, fixed vendor pins, runtime paths, two-unit allowlist and SHA-256/byte-count/mode for the other five files. No self-hash. |

These are **target scripts**, not a host installer. Do not run `installer.sh`,
`activate.sh`, `block.sh`, the AWK hook or the inverse on your workstation.
Generation is session-independent; any later transfer/execution needs a separate,
explicitly authorized target session. This document does not authorize one.

### Preserved behavior and limits

The reviewed renderer is retained unchanged, including its historical fixed
runtime directory `/opt/usr/share/hermes-recognition-persistent-20261023` and
`/opt/etc/parseinfo.sh` hook. A pre-existing package is refused, not adopted.
Preserving that directory is deliberate compatibility, not a user path.
The release adds an offline CLI, exclusive private output, manifest and
wrapper-hash-derived activation. There is no CLI pin/path override.
The importable `render()` fixture parameters are test seams, not support for a
different target baseline.

The wrapper validates stock/block bytes and metadata before execution, invokes
stock first, and fails closed on stock failure. Only
`contents-recognition-service.service` and
`contents-ui-detector-service.service` are masked/stopped; AT-HUB is pinned and
used for explicit activation, not disabled. Both mask names are prevalidated
before either is created. Foreign masks or ownership records are refused.
UID/GID/mode/SMACK and directory-type guards retain the reviewed exact vendor
baseline rather than loosening globally writable directories.

The per-boot receipt starts as `status=started`; success requires successful
reload/stops, unique expected service properties, both masks, both inactive
states, `MainPID=0`, and successful lock release. Failed runs do not receive a
success receipt. The finite polling loop is not an instantaneous stop guarantee.
The activation's inactive check is a point-in-time check, not an atomic service
manager transaction or an automatic retry loop.

The inverse refuses a foreign/changed hook, authenticates saved stock, and
restores its original 0777 mode without starting any service. Runtime masks,
package evidence and receipts are intentionally retained; a reboot is required
for the normal runtime reset. **Hook restoration is not full uninstall or a
service restart.** No firmware, bootloader, global UEP or maintenance daemon is
changed by this package.

### Portable offline verification

On Linux with `sh`, `bash`, `awk`, Python 3.11+ and normal coreutils:

```sh
python3 -B -m unittest discover -s tests -p 'test_recognition.py' -v
python3 -B -m unittest discover -s tests -p 'test_activation.py' -v
```

Run as a normal unprivileged user, without a device or network. Tests use
`tempfile` (honoring `TMPDIR` when set), synthetic stock/unit bytes, fake
UID/GID/SMACK observations and a fake service manager. All target data paths
are relocated before execution; real shells, AWK, files, permissions and inode
checks remain real. The full install → real-AWK stock → two masks → hook-only
inverse roundtrip checks unchanged mask inodes and no inverse manager calls.
Generated native paths are **only parsed**, never executed, in CLI syntax tests.
A generation test denies network and child-process creation with a Python audit
hook. The proprietary stock-input test was replaced by constant vendor-pin
assertions plus synthetic execution; no personal installation is required.

The existing renderer tests are **characterization**, including a replay on the
unchanged reviewed source. New CLI output/refusal tests were observed failing
before implementation. Activation behavior is characterized against the
reviewed six-line contract and the newly bound producer; missing producer API
failures prove absence, not historical semantic regressions.
Historical hardware acceptance belongs to the original implementation. This
public adaptation is verified offline and has **not** been newly TV-tested.

## Español

Referencia exclusiva: **TQ55Q70DATXXC, Tizen 8, ARMv7,
T-PTMLDDEUC-1400.0**. No cambies los hashes para aceptar otro modelo o firmware.
No se distribuyen archivos Samsung ni datos de una instalación personal.

```sh
OUT="$HOME/samsung-private/recognition-$(date +%Y%m%d-%H%M%S)"
python3 tools/recognition.py --output "$OUT"
python3 -B -m unittest discover -s tests -p 'test_recognition.py' -v
python3 -B -m unittest discover -s tests -p 'test_activation.py' -v
```

La generación es completamente local: no conecta, empareja, instala, ejecuta el
hook ni llama a systemctl. Exige un directorio nuevo fuera del repositorio,
resuelve enlaces simbólicos y no sobrescribe salidas existentes. Crea el
directorio con 0700 y los seis archivos con 0600. Los archivos generados son
privados y **no deben ejecutarse en el ordenador**. No hay garantía de
publicación atómica del conjunto: una escritura fallida puede dejar una salida
incompleta que debe descartarse.

`installer.sh` conserva el hook original, prepara y reemplaza, sin ejecutarlo.
`wrapper.awk` valida stock/bloque y ejecuta primero el stock con bash; si falla,
no aplica el bloqueo. `block.sh` limita las máscaras y paradas a las dos unidades
`contents-recognition-service.service` y
`contents-ui-detector-service.service`. Conserva las validaciones de hashes,
propiedad, modos, SMACK, máscaras ajenas y bloqueo por arranque.
Solo escribe éxito cuando ambas unidades están enmascaradas, inactivas, sin PID
y se ha liberado correctamente el bloqueo.

`activate.sh` vincula el hash al wrapper generado y solo solicita el inicio de
AT-HUB si la consulta ha terminado correctamente y devuelve exactamente
`ActiveState=inactive`. Es una comprobación puntual, no una transacción atómica.
`inverse.sh` restaura **solo el hook**, no inicia servicios y conserva las
máscaras de ejecución, el paquete y los recibos; necesita un reinicio para el
restablecimiento normal del estado de ejecución. No equivale a desinstalar.
`manifest.json` recoge hashes, tamaños y modos de los cinco archivos restantes.

Se conserva el renderer revisado y su ruta histórica fija por compatibilidad;
las novedades son el CLI offline, las salidas exclusivas, el manifiesto y la
activación vinculada al hash real. Los tests ejecutan bash/AWK/archivos reales
únicamente en un árbol temporal con stock sintético y gestor falso; no usan
root, TV, red ni archivos de una instalación personal. Distinguen la
caracterización existente de las pruebas causales nuevas del CLI. La aceptación
histórica en hardware corresponde al código original; **esta adaptación pública
solo se ha probado offline**, no nuevamente en un televisor.
