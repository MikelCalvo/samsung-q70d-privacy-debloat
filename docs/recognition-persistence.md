# Visual-recognition persistence: mechanism and evidence

[README](../README.md) · [Reproduction](reproduction.md) · [Recovery](recovery.md)

## Separate targets and authority

The 23 registry changes did **not** by themselves disable the generic visual-recognition services. A later separately authorized operation targeted only:

- `contents-recognition-service.service` — observed executable `/usr/bin/contents-recognition-service`.
- `contents-ui-detector-service.service` — observed executable `/usr/bin/contents-ui-detector-service`.

Shared `data-service.service`, `com.samsung.tv.context-aware-service.service` and `org.tizen.tv.sp-kpi.service` remained active in the accepted observation. Do not expand the block to those dependencies. A service's existence/name is not a measurement of the screen data it processed or transmitted.

## What the accepted private implementation did

This section describes the original implementation and authenticated local records (L3/L4). Follow the separate [tool instructions](recognition-tool.md) for the public adaptation:

1. The existing vendor `AT-HUB.service` already invoked `/opt/etc/parseinfo.sh` during boot through `starter.target`. Its ROM unit was not modified.
2. The installer preserved the exact original **805-byte signed Samsung script** privately. A reviewed AWK wrapper replaced the entry path only after its private stock/block/inverse were prepared and validated. It invoked the exact original stock first, then the narrow block; it did not patch the vendor signature or globally disable UEP.
3. Native interpreter/security-policy behavior mattered. The accepted design used the observed AWK entry, original signed stock via Bash, and the validated block through shell command text/dot sourcing. This cannot be safely replaced by “append some shell commands” or a guessed shebang. The existing AT-HUB argument and execution context were specifically tested privately.
4. The block validated hashes, regular-file/symlink status, owner/group/modes, path-specific SMACK/transmute rules, exact vendor unit pins and both runtime mask names. It created only the two owned runtime masks under `/run/systemd/system`, pointing to `/dev/null`; foreign/pre-existing masks were rejected rather than adopted.
5. It reloaded unit state, requested nonblocking stop of the UI detector then the provider, and checked finite rounds for exact unit identity, `LoadState=masked`, `ActiveState=inactive`, `MainPID=0`. A per-boot lock/ownership record constrained ordinary replay. A success receipt was published only after checks and ordinary lock release succeeded.
6. Installation, independent installation readback and activation were distinct steps. Installer success did not mean the hook had run. The private operator activated AT-HUB once, independently observed results, then verified a later actual reboot **without reinstalling or reactivating**.

The persistent component is a **privileged blocking hook**, not a new root-access service. Temporary root was used for maintenance/inspection and closed afterward.

### Original-stock identification (not redistribution)

The privately preserved original `/opt/etc/parseinfo.sh` had SHA-256:

`c6369e7dec69408e176daa252d436acf6f8e265f560504d8bd831c8023c71d61`

This nonsecret vendor-file digest identifies the tested bytes only. It does not prove compatibility on another TV and is not a substitute for a private backup or the corresponding source. No Samsung stock bytes are included here. The live modified hook is not expected to match that stock digest; restoration would be checked against the captured original.

## What demonstrated persistence

The final accepted local record (L4, 2026-10-23) distinguishes an earlier restart report that **did not change the kernel boot identity** from a later reboot that did:

- Before and after kernel `boot_id` differed; actual values remain private.
- A **fresh receipt tied to the new boot** reported `status=success masked=2 inactive=2 MainPID=0`.
- AT-HUB had `ExecMainCode=1`, `ExecMainStatus=0`, and no retained task lock. Here code 1 denotes normal exit; the status 0 is the successful exit status.
- Both exact services were `masked-runtime`, `inactive/dead`, `MainPID=0`, `FragmentPath=/dev/null`, with matching mask targets.
- Exact selected executable paths were absent. Incomplete `/proc` reads were classified as kernel threads or zombies; no unclassified live userspace process remained in that observation.
- Hook/stock/block/inverse and vendor-unit hashes/metadata matched accepted values. The prior 23 registry targets and three false preferences remained intact; shared units remained active.
- This verification submitted only target-state reads, **not installer, activation, stop, reload or inverse**.

A transport exit0, a successful asynchronous `start`, an old success receipt, unchanged boot identity or a mask symlink alone would not establish this result.

## Limitations retained even after that success

- **Eventual boot blocking:** no enforced early ordering before recognition. The services may run/capture before AT-HUB reaches the block. No first-frame/first-capture guarantee.
- Finite polls are not hard end-to-end timeouts: an individual native call can block.
- Host-cooperative drift detection, not resistance to another hostile root or complete TOCTOU protection.
- Preparation/rename is not a multi-file transaction or proven crash/power-loss durability. A failure after rename can leave an installed hook even when transport reports failure.
- Abrupt death can leave a lock or partial ownership record. Preserve it and reconcile; do not delete/adopt/replay automatically.
- Per-boot files accumulate without an automatic garbage-collection guarantee.
- One TV/build and one accepted new-boot observation are not update-survival or universal compatibility tests. Do not disable security updates; stop and review new bytes.
- Owner general functional acceptance is not a complete per-input/per-app matrix; no traffic-elimination or performance claim is made.

## Public source and historical observations

The original offline renderer, inverse and synthetic harness are included in [the recognition generator](recognition-tool.md). The public tool must be read alongside this mechanism description, its fixed vendor pins and the temporary-access requirements in [access](access.md). Having source does not establish compatibility or authorize installation.

The public adaptation and its portable tests are distinct from the historical native result above. Do not describe an offline success as a new TV installation or live restoration. Original stock must come from the operator's own checked backup; no Samsung bytes are distributed.

Before a device operation, require:

- exact vendor-file and unit hashes, metadata, interpreters and security-label behavior;
- the source, generated installer, inverse, wrapper, block, activation and their matching manifest;
- passing offline tests with clearly emulated metadata/service-manager boundaries;
- an explicitly authorized temporary-access path and independently verified cleanup;
- private consistent backups and physical access, with the hook-only inverse ready before installation;
- independent installation readback before activation, then new-boot observation without manual repair.

Do not substitute an unsigned appended script, relax pins, install a different generation's hook or upload the original stock to an issue. If any prerequisite cannot be verified, stop before installation.


## Sources

[1] https://github.com/chris-ritsen/samsung-tv-root
