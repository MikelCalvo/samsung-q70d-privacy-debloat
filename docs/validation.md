# Validation: readback, reboot identity and physical acceptance

[README](../README.md) · [Reproduction](reproduction.md) · [Recovery](recovery.md)

Commands below are **read-only checks for an already authorized session**. They do not authorize connecting, rooting, rebooting or changing anything. Opening a temporary privileged observation session may itself stage tools/access state; that must be scoped and cleaned up. Do not run an installer to “validate” its output.

## A. Identity and consistent backup

- Privately record on-screen model/firmware and tool-reported Tizen/architecture. Compare the exact reference identity, not just “Samsung/Q70D.”
- Verify the private snapshot's hash, extraction, schema, unique app IDs and `quick_check=ok` offline. Preserve original typed preferences, marker state, hook/unit bytes and metadata. No snapshot or inverse → STOP.
- Record all authorization boundaries and physical access/recovery prerequisites. An agent must not infer a write grant from a request for inspection.

## B. Registry and voice readback

Read-only examples on the TV, using the **observed** database path:

```sh
sqlite3 -readonly /opt/dbspace/.pkgmgr_parser.db 'PRAGMA quick_check;'
sqlite3 -readonly /opt/dbspace/.pkgmgr_parser.db 'SELECT count(*),count(DISTINCT app_id) FROM package_app_info;'
vconftool get db/menu/voice/voice_activated
vconftool get db/si_service/voice_recog_enable
vconftool get db/multi-assistant/prelaunch_mode
```

Expected reference results: `ok`, `499|499`, and each exact key with `value = False (Boolean)`. Counts are historical reference values, not permission to force another build to match.

Generate a read-only `SELECT app_id,app_disable,app_onboot,app_autorestart ... WHERE app_id IN (...) ORDER BY app_id` from the exact 23 allowlisted IDs in the [profile](../profiles/tq55q70datxxc-tizen8-1400.0.json), safely quoting values. Require each exactly once with text tuple `true,false,false`. Compare the whole private registry snapshot before/after: same IDs, no unplanned non-target flags/fields changed. A selected-row success alone does not prove non-target preservation. The reference recorded 8 advertising + 15 voice targets and 476 other rows unchanged (L1/L2/L4).

Verify all five markers by exact path, absence/presence transition and ownership/content/metadata, then inspect their six consumers' actual `ConditionPathExists` and state. In the accepted post-registry reboot observation the six were inactive/dead with the intended condition false. Markers and registry values are different evidence; neither alone proves all processes absent.

## C. Service masks, provider state and hook evidence

Read-only examples for the two additional visual services:

```sh
systemctl show contents-recognition-service.service contents-ui-detector-service.service -p Id -p LoadState -p ActiveState -p SubState -p MainPID -p FragmentPath -p UnitFileState
readlink /run/systemd/system/contents-recognition-service.service
readlink /run/systemd/system/contents-ui-detector-service.service
systemctl show AT-HUB.service -p Id -p ActiveState -p SubState -p ExecMainCode -p ExecMainStatus
systemctl show data-service.service com.samsung.tv.context-aware-service.service org.tizen.tv.sp-kpi.service -p Id -p ActiveState -p MainPID
```

For **each** exact visual unit require unique expected properties: `LoadState=masked`, `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `FragmentPath=/dev/null`, `UnitFileState=masked-runtime`; mask targets `/dev/null`. Require the three named shared units still active. Reject duplicated/missing fields rather than accepting whichever line a loose grep finds.

AT-HUB's successful historical completion was `ExecMainCode=1`, `ExecMainStatus=0`, inactive/dead. Asynchronous start exit0 only means a request was accepted. Independently verify the current hook/stock/block/inverse hashes, metadata and security labels against the approved **private** manifest, along with the new-boot receipt and absent lock. Do not publish those receipts or actual boot IDs. A file saying `success` without independent state checks is insufficient.

## D. Process absence is its own check

Enumerate `/proc` and compare exact resolved `/proc/<pid>/exe` paths and relevant UIDs, not process-name substrings. Check the two visual executable paths in the profile and the **snapshot-derived** selected native advertising/voice executable allowlist. A package ID is not necessarily an executable pathname; shared loaders must not be killed or counted by package-name inference.

For permission-denied, disappeared, unreadable or empty executable links, classify the process with available metadata. Do not count an incomplete read as “not running.” Repeat a bounded observation if a race is unresolved; unclassified live userspace candidates mean **inconclusive**. The accepted visual readback had no selected executable and classified all incomplete reads as kernel threads or zombies (L4); that is a point-in-time observation, not continuous monitoring.

`app_launcher -t` reporting “not available” and earlier TERM success did not prove absence. Some targets respawned before the registry reboot. Never replay a mutation to make a process check pass.

## E. Demonstrate a real new boot, without helping it pass

Privately capture this before and after an owner-authorized reboot:

```sh
cat /proc/sys/kernel/random/boot_id
```

Require **inequality**. Keep actual values private. Standby, UI restart, an old receipt or an owner saying “restarted” is not enough by itself. The reference first restart report had unchanged boot identity; a later one produced a changed kernel boot and a fresh successful hook receipt.

After the new boot, perform only independent target-state reads: do **not** install again, start AT-HUB, stop services, reload units, write preferences or execute inverse. Require fresh receipt tied to this boot, both exact masked/inactive/PID0 services, no selected executables, absent lock, approved hashes/metadata, 23 flags and 3 preferences still correct. This is the distinction between **automatic reapplication observed** and manually repairing state after reboot.

## F. Physical acceptance — ask, do not infer

Record a baseline and post-change result **per row**, with `pass / fail / not tested`, date/build and who observed it. Owner general acceptance is useful but not interchangeable with these tests.

| Test | Future acceptance criterion | Reference evidence boundary |
| --- | --- | --- |
| TDT/DTT picture and sound | Tune a normal channel; watch/listen; change channel | Picture/sound and general usability accepted, no complete standardized playback receipt |
| YouTube | Launch, play a chosen video, sound, seek, exit | Intended use; no complete independently documented per-app playback matrix |
| Jellyfin | Launch, browse, play chosen content, sound, seek, exit | Intended use; no complete independently documented per-app playback matrix |
| HDMI / external sources | Select each source actually used; picture, sound, remote navigation | No exhaustive post-change matrix |
| Standby / resume / reboot | Owner confirms physical use after each distinct transition | A new kernel boot was technically proven; not every transition/app tested |
| Accessibility / TTS | Required owner features remain usable | Components intentionally preserved; full functionality not established |
| Voice/wake word | Owner accepts intended loss of assistant/mic features | Disabled preferences/components; not electrical isolation of the remote mic |
| Optional consent / TV mic switch | Inspect real menu/switch, record human confirmation | Owner confirmed rejected options and TV mic off |
| HbbTV | Owner accepts loss of interactive features; separately test conventional TDT | Owner later confirmed menu off; full TDT/HbbTV matrix not documented |

If a required function regresses, stop and assess the narrow inverse under new permission. Do not call the whole TV “fully tested” because one channel works.

## G. Cleanup and claim gate

Require temporary root/staging closed, owned access tool/listeners gone, temporary access exceptions reconciled by the access workflow, and no persistent remote-root access agent. The intentional persistent block hook is a different object. A cleanup failure makes the run incomplete, even if target flags look right.

A report should say **what was observed, when and with which limitations**. Never substitute “zero tracking,” “faster,” “RAM saved,” “never captures,” “restoration tested on TV” or “all Samsung models” for the checks above.

## H. Public-tool checks are not new device tests

Local checks cover the selected-ID profile, internal links, public-file allowlist, privacy patterns, generators and synthetic script execution with external device boundaries emulated. They cannot prove TV playback, future compatibility, telemetry absence or successful live recovery. Public-source adaptations are labeled separately from the original on-TV result. Official-document URLs were not fetched again for this release; related GitHub repositories and the pinned dependency commit were checked separately.
