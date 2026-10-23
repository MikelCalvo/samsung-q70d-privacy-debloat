# Source distribution and validation boundaries

This repository distributes original offline planners, the narrow visual-hook source and its inverse, portable synthetic tests, an explicit temporary-session adapter and staged documentation. It does not distribute private backups, captures, generated operation receipts, Samsung files or upstream payloads.

## What the evidence covers

- The reference changes were observed on one TQ55Q70DATXXC, Tizen 8 ARMv7, firmware T-PTMLDDEUC-1400.0.
- The public adaptations are tested offline. That does not make them newly hardware-tested.
- Automatic reapplication of the original visual hook was observed after a real new kernel boot. It does not guarantee blocking from the first instant of startup.
- Recovery assets and read-only admission were checked. Complete restoration was tested on synthetic fixtures, not performed on the TV.
- General owner acceptance is not a complete per-app/input playback matrix.
- Changed firmware, service definitions, metadata or access behavior requires a new review. Do not relax guards or disable security updates to retain compatibility.

## Reproduce the public checks

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tools/check_public_tree.py
```

The [offline workflow](.github/workflows/offline.yml) runs tests and packaging checks on Python 3.11 and 3.14. Check the GitHub Actions result for the exact commit you use; the existence of this file is not a CI success record. Pattern checks supplement manual review and do not prove the absence of every possible secret.

Original code, profile data and documentation use the MIT license. External dependencies retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md). Operator and assisting-agent checkpoints are in [reproduction](docs/reproduction.md), [recovery](docs/recovery.md) and [validation](docs/validation.md).
