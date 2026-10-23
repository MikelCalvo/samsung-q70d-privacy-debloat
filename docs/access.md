# Temporary access / Acceso temporal

This is an **explicit owner-operated root transport**, not a compatibility oracle
or a debloat installer. It executes the entire supplied script as root. Even a
read/check script needs `--authorize-root-session`: upstream `archive_root.probe`
performs root acquisition and temporary TV staging, not a read-only network probe.
No command runs at import or with `--help`.

The reference scope remains **TQ55Q70DATXXC, Q70D 55-inch, Tizen 8, ARMv7,
T-PTMLDDEUC-1400.0**. Verify the actual TV/build and obtain owner authorization
before using this adapter. It does not independently authenticate the marketing
model or firmware string. Do not force another build to match this profile.

## External dependency and build

Original adapter code is MIT. The separate
[chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root)
project is **Unlicense**, not vendored here. This adapter requires its exact commit:

```text
bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653
```

Do not substitute moving `master`, a different release, or an installed Python
package. Review the pinned source and build your own payloads in a separate
checkout. The adapter verifies Git HEAD, tracked changes, untracked **and ignored**
files under `src`, plus tracked changes to `payloads/common` and `Makefile`, before
importing `src/samsung_tv_root/archive_root.py`. In particular, remove stale
`src/**/__pycache__` directories yourself; they are refused, not silently used or
automatically deleted. Use `python -B` for manual upstream Python inspection.
This is an operator trust check, not protection against a malicious Git binary,
concurrent checkout modification, replaced build tools, or dishonest build output.
Keep the checkout private to the operator during a session.

Host requirements:

- **Linux only** for this adapter (owned worker process/session cleanup).
- Python **3.11+** for this repository's standard-library tools/tests. Upstream's
  own `pyproject.toml` and README declare **Python 3.12+**; use Python 3.12+ for
  live dependency operation, rather than treating our offline Python floor as
  upstream support.
- Git, OpenSSL (`openssl` on PATH), and Samsung's `sdb` from a separately installed
  [Tizen Studio](https://developer.tizen.org/development/tizen-studio/download).
  Samsung files are not distributed by this repository.
- GNU Make and the **.NET 6 SDK** to build the common payloads from upstream source.
  Build/restore may require access to NuGet; that is a deliberate operator setup
  step, never something the adapter downloads automatically.

Example setup (choose external directories through your own variables):

```sh
git clone https://github.com/chris-ritsen/samsung-tv-root.git "$UPSTREAM"
git -C "$UPSTREAM" checkout --detach bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653
make -C "$UPSTREAM" common-payload
```

At the pinned Makefile, `common-payload` builds `SamsungTvRootAgent.csproj`,
`SamsungTvArchiveRoot.csproj`, and the common input/event agents into
`payloads/common/out`. This adapter only needs `SamsungTvArchiveRoot.dll` and
`SamsungTvRootAgent.dll`; upstream creates the session runtime configuration.
It pins payload directory environment variables to that external checkout,
ignoring inherited payload overrides. Build outputs are trusted operator inputs,
not independently reproducibly attested by this adapter.

Upstream also documents `make common31-payload` with SDK **6.0.428**, selected by
`payloads/common31/global.json`, restoring .NET 3.1 reference packages; it depends
on `common-payload`. That is not required for the reference 6.0.9 runtime.
Clang/LLD with ARMv7 support is required for upstream's **full**
`make payloads swu-preloads`/release build, not this archive-only common build.
Do not install a daemon or run a full release build just to use this adapter.

Authoritative dependency details at this pin:
[README](https://github.com/chris-ritsen/samsung-tv-root/blob/bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653/README.md),
[Makefile](https://github.com/chris-ritsen/samsung-tv-root/blob/bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653/Makefile),
[archive_root.py](https://github.com/chris-ritsen/samsung-tv-root/blob/bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653/src/samsung_tv_root/archive_root.py).

## Network topology and one explicit invocation

Prepare Developer Mode and its controller address manually using Samsung's
instructions. This tool does not discover, pair, enable Developer Mode, change
firewall policy, reboot, disable global UEP, install an agent service, or uninstall
anything. Owner approval for access is not approval for arbitrary mutation.
Review the exact generated script and its inverse first.

```text
controller 192.0.2.20  --TCP 26101/SDB--> TV 192.0.2.10
controller 192.0.2.20  <--TCP 38471------ TV (SDK command capture)
controller 192.0.2.20  <--TCP 38472------ TV (authenticated root agent)
```

Use actual owner-supplied addresses, not the documentation addresses. Both
callback listeners bind the exact `--controller` IPv4 address, not all interfaces.
Capture calls are serialized onto one fixed port; the authenticated agent checks
the selected TV peer and requires root identity. The SDK capture callback itself
is **not authenticated** by upstream; use a trusted isolated LAN, not an exposed
Internet listener. Ensure the TV can reach these controller ports through your
existing narrow policy. No broad firewall opening is supplied or performed.

Create a private output directory **outside this repository**. The adapter does
not pass script arguments. To run a generated registry readback, first compose a
single private input script with the required mode, then send that exact file:

```sh
umask 077
mkdir -p "$PRIVATE"
# PLAN is the controller-side directory generated by tools/registry.py.
# Use a new filename and refuse overwriting an earlier invocation.
(set -C; { printf '%s\n' 'set -- before'; cat "$PLAN/selected-readback.sh"; } > "$PRIVATE/readback-before.sh")
python3 -B tools/tv_session.py \
  --upstream "$UPSTREAM" \
  --host 192.0.2.10 --controller 192.0.2.20 \
  --sdb "$SDB" \
  --script "$PRIVATE/readback-before.sh" \
  --receipt "$PRIVATE/readback-session.json" \
  --authorize-root-session
```

`--script` is an explicit local user file, including a file generated by the
other tools. There is no implicit script selection or automatic reapply. The
receipt's parent must already exist; its destination must be new. Realpath
containment, including symlinked parent paths, rejects receipts in the repository.
Keep scripts, snapshots, preference captures and receipts outside the repository.

Ports can be selected with `--capture-port` / `--agent-port` (distinct ports in
1024–65535). Defaults are **38471/38472**. There is no automatic ephemeral-port
fallback or retry. If occupied, fix the topology or choose explicit ports; do not
open arbitrary inbound ranges.

## Serialization and runtime compatibility

The adapter sends exactly one root EXEC command. A top-level base64 envelope
contains the exact UTF-8 script bytes (gzip-compressed only above 32 KiB); only a
fixed ASCII shell expression and base64 alphabet reach upstream's C#
`ProcessStartInfo.Arguments` quoting. Literal backslashes, dollar signs, quotes
and newlines inside the script cannot be reinterpreted by that argv
serialization. Bash decodes/runs the script through stdin with `pipefail` around
the transport pipeline, so base64, gzip and script failures produce a nonzero
exit. The script runs in a new Bash, not sourced in an interactive session;
stdin is the script stream, and interactive input, externally supplied script
arguments and reliable `$0`-relative resource lookup are not supported. Compose
required positional parameters into the input with a safely shell-quoted
`set --` prefix, as above: `before`/`after` for readback, or `--authorize` and the
TV-side run directory for apply/inverse. Never interpolate an unquoted run path.

Input is limited to **1–131072 bytes (128 KiB)**, valid UTF-8 with no NUL; the
local file read is bounded to that limit plus one rejection byte. Scripts of
**at most 32768 bytes** retain the original uncompressed base64 envelope exactly.
Larger scripts use standard-library gzip with `mtime=0`, then base64, and are
accepted only if the **gzip payload is at most 32768 bytes (32 KiB before
base64)**. This is a payload/wire budget, not a guarantee that every 128 KiB
script fits. The complete ASCII command is under **60 KiB** (normally under
44 KiB), below upstream's 64 KiB EXEC limit and Linux single-argument limits.
Oversized input or compressed payloads are refused locally, not chunked,
uploaded or sent through additional EXEC calls.

The TV must already provide `/bin/bash`, `/usr/bin/base64`, and, **for scripts
above 32 KiB, `gzip` on PATH supporting `-d -c`**. The compressed envelope checks
for gzip before starting the decode/script pipeline; missing gzip exits nonzero
before any supplied script actions. This is a newly explicit dependency, **not
newly verified on the reference TV**. No package is installed automatically.
Decoding is streaming, not atomic validation: a corrupted stream can execute a
valid prefix before a later decoder error; `pipefail` prevents reporting success
but cannot undo those actions. Review private evidence before retrying.

Readback remains text: upstream decodes stdout/stderr with replacement and caps
each at 1 MiB; this is not a binary database backup transport.

Upstream's target checks remain intact: SDB package-name shell execution,
effective dotnet SETGID/SYS_ADMIN and launcher SETUID/SETGID capabilities,
supported runtime and tar `--to-command`. No capabilities are fabricated.
The only compatibility fallback catches upstream `ArchiveRootError` for the exact
`/usr/bin/dotnet --list-runtimes` command containing
`Unknown option --list-runtimes`. It then requires:

1. `readlink -f /usr/share/dotnet.tizen/netcoreapp` equals exactly
   `/usr/share/dotnet/shared/Microsoft.NETCore.App/6.0.9`;
2. the runtime directory listing contains `6.0.9` and every line is a numeric
   three-component version.

Only then is the ordinary runtime listing representation supplied back to
upstream. Other errors, changed links and malformed listings fail closed. This
fallback reflects the historically observed **6.0.9 apphost** behavior; it does not
claim broader runtime support. Upstream's normal successful runtime/capability
path is otherwise unchanged.

## Deadlines, receipt and cleanup

Defaults: SDB timeout **8 s**, root callback accept **20 s**, script command
**30 s**, whole worker deadline **240 s**. Flags are `--sdb-timeout` (0.1–60),
`--accept-timeout` (0.1–120), `--command-timeout` (0.1–300), and
`--session-timeout` (0.1–900), all finite. Upstream has additional bounded waits
for capture, ping, shutdown and cleanup; the outer worker deadline covers them.
A hard timeout terminates only the newly created worker/process group, with at
most two additional one-second termination joins. It never runs
` sdb kill-server` or disconnects unrelated sessions. A shared SDB server may
remain running; global ownership has not been established.

The new receipt is reserved mode **0600 before any root operation**. Raw upstream
stdout/stderr, exception details, actual returned command text/output/exit and
timeout fields, authenticated root identity, and cleanup observations are stored
only there. Terminal output is a fixed success/failure sentence: no device
addresses, private paths, command output or exception values are printed.
A local refusal before receipt reservation prints only failure, and may have no
receipt. A receipt write/storage failure also returns nonzero.

`root` is the authentic upstream result when upstream returns. Its documented
fields include `authenticated`, `uid/euid/gid/egid`, `cap_eff`, `smack`, `runtime`,
`preflight_capabilities`, `commands`, `staging_cleaned`, and
`system_files_unchanged`. Each command contains `command`, `exit_code`,
`timed_out`, `stdout`, `stderr`. `observations` journals actual identity,
command/shutdown/server-close and upstream `_cleanup` calls, preserving completed
command evidence even if upstream subsequently raises during cleanup.

Exit **0** requires authenticated UID/EUID/GID/EGID 0, the one command's actual
exit 0 and `timed_out == false`, unchanged upstream system-file hash checks,
staging cleanup true, shutdown acknowledgement and server close, normal worker
exit, and no recorded error. Every other outcome returns **1**. Unknown cleanup
is JSON `null`, never silently true; an upstream exception may mean `root: null`
while observations retain the completed command.

The upstream cleanup booleans cover the package staging/archive/signature and
its `/etc/passwd` / `/usr/share/sdbd/public.pem` before/after checks. They are not a
full filesystem or listener audit. Upstream capture staging scripts self-delete
when executed, but interrupted launch can leave files. Hard timeout, SIGKILL,
power loss or parent crash cannot guarantee a final receipt or remote cleanup.
No automatic cleanup retry or rollback is attempted: inspect state privately
before authorizing another operation. Root retains Samsung's SMACK restrictions;
UID 0 does not prove every security boundary is removed.

## Verification status

The released adapter is **offline/synthetically tested, not newly hardware-tested**.
Historical acceptance of the original private access implementation is not a
hardware test of this portable adaptation. Tests exercise the real public main
and worker, external synthetic upstream modules, metadata refusals, exact fallback,
fixed ports, serialization/decoder failure, exit/timeout/cleanup outcomes and
private output handling. The composed registry test retains real generation,
shell execution and SQLite, replacing only the existing native id/vconftool/
systemctl boundaries and relocating native paths into synthetic stock state.
It checks apply → selected readback → inverse and restoration through the real
session envelope. No TV/network/root operations are used:

```sh
python3 -B -m unittest discover -s tests -p 'test_tv_session.py' -v
python3 -B -m unittest discover -s tests -p 'test_transport_integration.py' -v
python3 -B -m unittest discover -s tests -v
python3 -B tools/tv_session.py --help
```

## Resumen en español

- **Sólo Linux y autorización explícita.** `--authorize-root-session` autoriza
  adquirir root **y ejecutar el script completo**; una comprobación también
  necesita esta autorización. No implica permiso para otras fases ni modelos.
- Dependencia externa Unlicense fijada al commit indicado; no contiene archivos
  Samsung. Use Python 3.12+ para upstream, Git, OpenSSL, SDB de Tizen Studio,
  Make y .NET 6 para `common-payload`. No se instala un demonio.
- Configure manualmente Developer Mode, ruta y cortafuegos. El controlador acepta
  conexiones de retorno en los dos puertos explícitos. No exponga SDB ni los
  callbacks a Internet; la captura SDK de upstream no está autenticada.
- Script local UTF-8, máximo **131072 bytes (128 KiB)**. Hasta 32768 bytes se
  mantiene el base64 original; por encima se usa gzip determinista, con carga
  comprimida de máximo **32768 bytes antes de base64**. Requiere `gzip -d -c` en
  PATH de la TV (dependencia **no comprobada de nuevo en hardware**); si falta,
  se rechaza antes de ejecutar el script. `pipefail` impide éxito falso, pero
  decodificar en flujo no revierte acciones anteriores a un error tardío.
  Bash ejecuta desde stdin; anteponga `set --` con argumentos correctamente
  entrecomillados para readback/apply/inverse. Sin interacción ni copias binarias
  de bases de datos. El fallback sólo admite el error apphost observado y el
  enlace exacto de runtime **6.0.9**.
- Recibo JSON nuevo **0600 fuera del repositorio**. Contiene salidas privadas,
  identidad root, resultados reales y limpieza. La consola no muestra secretos.
  Fallo, timeout, salida no cero o limpieza falsa/desconocida ⇒ salida **1**.
- Hay plazos finitos, pero cortar el proceso no garantiza limpieza remota. No se
  mata el servidor SDB global ni se reintenta. Revise el estado antes de actuar.
  Esta adaptación **no se ha vuelto a probar en hardware**.
