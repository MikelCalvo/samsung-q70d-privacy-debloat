# Samsung Q70D privacy debloat

[Español](README.es.md) · [Workflow](docs/reproduction.md) · [Recovery](docs/recovery.md) · [Security](SECURITY.md)

A model-specific privacy workflow for the Samsung Q70D. It disables selected advertising, ACR and voice components without uninstalling the launcher or streaming apps. It includes offline plan generators, a narrow visual-recognition boot hook, inverse operations, synthetic tests and a temporary-access adapter.

This is privileged device work, not a one-click debloater. Read the procedure and recovery limits first. The original base changes were observed on one TV; its public adaptation has separate offline tests. The optional follow-up has its own [scope and verification boundaries](docs/privacy-extension.md).

## Tested reference

| Field | Value |
| --- | --- |
| Model | TQ55Q70DATXXC, Samsung Q70D 55-inch |
| OS / CPU | Tizen 8.0, ARMv7 32-bit |
| Firmware | T-PTMLDDEUC-1400.0 |
| Intended use | TDT/DTT, YouTube and Jellyfin |

Another Q70D, regional suffix, firmware or Tizen generation is not automatically compatible. Vendor hashes, unit definitions, metadata and access behavior must match. Do not change pins just to make a different build pass.

## Reference result

- 23 of 499 registry components: 8 advertising/ACR-related and 15 voice-related. Only their `app_disable`, `app_onboot` and `app_autorestart` text flags changed; the other 476 rows' flags and app-ID set were preserved.
- Three Boolean voice preferences set to false. Five condition-marker files supported six selected services.
- Two additional visual services, `contents-recognition-service.service` and `contents-ui-detector-service.service`, masked under `/run/systemd/system`. The existing `AT-HUB.service` boot entry invokes a wrapper that runs the preserved signed Samsung stock first, then reapplies the two masks and stops those services.
- Independent reads after a changed kernel boot identity found both visual units masked-runtime, inactive and MainPID=0, with no selected executable observed.
- The owner separately confirmed optional privacy consents rejected, the TV microphone switch off and HbbTV disabled in the menu. The TV switch is not proof of electrical isolation of the remote's separate microphone.
- A [second privacy pass](docs/privacy-extension.md) adds six voice/sensor flag triples, two markers and four discovery/remote-support masks while preserving the original profile. Installation and flags were independently checked, but the corrected extension still needs a real new-boot verification and family playback checks. See the [community assessment](docs/community-privacy-review.md) for evidence and trade-offs.

This is registry disabling, not package removal. Temporary maintenance root is separate from the intentional privileged blocking hook; no persistent remote-root service is installed. Home Assistant is not required.

## Start offline

Linux, Python 3.11 or newer, Bash, AWK and sqlite3. Fixture tests do not need a TV, root, internet access or Samsung files.

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public_tree.py
python3 tools/recognition.py --help
python3 tools/registry.py --help
python3 tools/tv_session.py --help
```

Never run generated device scripts on your computer. Keep every snapshot, before-state capture, generated plan and receipt outside the checkout.

## Tools and order

1. Read the [staged workflow](docs/reproduction.md), [validation](docs/validation.md) and [recovery](docs/recovery.md). Operators and assisting agents use the same checkpoints.
2. Obtain temporary access through the separately downloaded, pinned [upstream root project](https://github.com/chris-ritsen/samsung-tv-root). The [access guide](docs/access.md) covers explicit opt-in, required dependencies and cleanup limits. Root acquisition is a privileged operation, including when called a probe.
3. Capture a private consistent registry snapshot and actual before-state. The [registry planner](docs/registry-tool.md) generates selective flags, preferences, markers and their inverse. Historical values in the public profile are not portable rollback.
4. Review and authorize the separate [visual-recognition package](docs/recognition-tool.md). The generator includes installer, original-stock wrapper, two-service block, hook-only inverse and inactive-only activation. Installation and activation are distinct actions. Read the [mechanism](docs/recognition-persistence.md) first.
5. Apply each admitted stage once, independently read back the result and coordinate a real reboot when testing persistence. Do not reapply during verification.
6. Confirm picture, sound, navigation and every app/input you use, then close temporary access and retain the private recovery kit.

The [selected-component profile](profiles/tq55q70datxxc-tizen8-1400.0.json) records reference data, not executable deployment configuration or proof of compatibility by itself.

## Limits

- No zero-telemetry guarantee. Connected apps still communicate with their providers; this work does not prove all tracking stopped.
- No measured speed, RAM or free-space gains.
- Recognition may run before AT-HUB reaches the blocking hook during early boot. There is no first-frame capture guarantee.
- Restoration assets and read-only admission were checked. The complete hook roundtrip was tested offline on fixtures, not by performing a full restoration on the TV.
- General owner acceptance is not a complete documented TDT/YouTube/Jellyfin/HDMI playback matrix.
- No guarantee across updates. Review changed vendor bytes; do not disable security updates to preserve a modification.
- Native service calls and interrupted remote commands have no proven hard cancellation or crash-atomic recovery guarantee.

## Attribution and license

Original code, profile data and documentation are MIT licensed. The root technique and external access tooling come from chris-ritsen/samsung-tv-root and the work it credits, not from this project. See [THIRD_PARTY.md](THIRD_PARTY.md) and the [source ledger](docs/sources.md).

No personal network configuration, credentials, unique device identifiers, raw private evidence, Samsung binaries or original Samsung scripts belong in this repository. Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a model report or patch.
