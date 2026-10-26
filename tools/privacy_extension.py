#!/usr/bin/env python3
"""Offline Q70D extension: --snapshot --before --previous-hook --output.

Generation never connects, installs, activates, kills processes or restores a TV.
Native scripts require separate explicit authorization. Install hook first (does
not activate it), then apply apps; invoke the hook only under separate authority.
Hook inverse restores ONLY the prior hook, retaining runtime masks. App inverse
restores ONLY captured selected fields and owned markers, never starts services.
Cooperative administrator model; not crash atomic, no hard native-call timeout,
possible early boot window, and marker/flag changes do not prove process absence.
"""
import argparse
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys

if __package__:
    from . import registry as reg, recognition
else:
    import registry as reg
    import recognition

D = '/opt/usr/share/hermes-privacy-extension-v1'
HOOK = '/opt/etc/parseinfo.sh'
PREVIOUS_SHA = 'c9a3ea4dbdbcf06a262dcc6f7c87f71f6a15cb31ce554ab5e029dff0cdb10e40'
IDS = ('com.samsung.tv.tvsensor-iot-service',
       'org.tizen.voice-app', 'org.tizen.voice-app-service', 'org.tizen.voice-client',
       'org.tizen.voice-onboarding', 'org.tizen.stt-client')
UNITS = ('wifi-presence.path', 'wifi-presence.service', 'remote-management.service',
         'remote-shop-care-hub.service')
PINS = {
    'wifi-presence.service': 'a2f4f11950f547507675522bd92a90b2a56902906b66fd54a262a1a967baf2e7',
    'wifi-presence.path': '03caae12e4fe516057da6d919d7e987953c991c5ad5add19e2a73697652bcd34',
    'remote-management.service': '20a53a5c7f2a53185e228f622e980d90fb4ea71220909fa0c3296e38172cfabd',
    'remote-shop-care-hub.service': 'e9a53a363a9d5a7e725ac25d8ef07b01cd409a3a507dad39d7859203a6e03302',
}
MARKERS = ('/opt/usr/share/systemd/system/org.tizen.voice-app',
           '/opt/usr/share/systemd/system/org.tizen.voice-client')
ROOT = Path(__file__).resolve().parents[1]
Q = shlex.quote
require = reg.require


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def validate_before(before):
    require(type(before) is dict and set(before) == {'schema_version', 'tested_identity', 'markers', 'unit_conditions'}, 'Unexpected BEFORE schema')
    require(type(before['schema_version']) is int and before['schema_version'] == 1
            and before['tested_identity'] == reg.IDENTITY
            and type(before['tested_identity'].get('diagonal_inches')) is int, 'Unsupported identity')
    markers = reg.entries(before['markers'], ('path', 'state'), 'path', MARKERS)
    require(all(r['state'] == 'absent' for r in markers.values()), 'Markers must be observed absent')
    consumers = {p.rsplit('/', 1)[1]+'.service': p for p in MARKERS}
    conditions = reg.entries(before['unit_conditions'], ('unit', 'ConditionPathExists'), 'unit', consumers)
    for unit, path in consumers.items():
        values = conditions[unit]['ConditionPathExists']
        require(type(values) is list and all(type(v) is str for v in values)
                and len(values) == len(set(values)) and '!'+path in values, 'Missing negative marker condition')
        # Retain the captured positive AFTER_PRODUCTION condition, never reset it.
        require(all(v == '!'+path or re.fullmatch(r'/[A-Za-z0-9_./-]*/AFTER_PRODUCTION', v)
                    for v in values), 'Unreviewed condition')
    return conditions


def validate_rows(rows):
    selected = reg.entries(rows, ('app_id',)+reg.FIELDS, 'app_id', IDS)
    require(all(type(r[f]) is str and r[f] in ('true', 'false') for r in rows for f in reg.FIELDS), 'Text Boolean flags required')
    return [selected[a] for a in IDS]


def read_snapshot(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Regular standalone snapshot required')
    path = path.resolve(strict=True)
    reg.no_sidecars(path)
    digest = sha(path.read_bytes())
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)) as con:
        require(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Snapshot integrity')
        require(con.execute("SELECT type FROM sqlite_master WHERE name='package_app_info'").fetchall() == [('table',)], 'Registry table')
        require(not con.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name='package_app_info'").fetchall(), 'Registry trigger')
        rows = []
        for app in IDS:
            found = con.execute('SELECT app_disable,app_onboot,app_autorestart FROM package_app_info WHERE app_id=?', (app,)).fetchall()
            require(len(found) == 1, 'Missing or duplicate selected row')
            rows.append(dict(zip(('app_id',)+reg.FIELDS, (app,)+found[0])))
    rows = validate_rows(rows)
    reg.no_sidecars(path)
    require(sha(path.read_bytes()) == digest, 'Snapshot changed')
    return rows, digest


def render(rows, before, previous, *, previous_sha=PREVIOUS_SHA, unit_pins=None, transform=lambda s: s):
    """Pure renderer. Override pins/transform ONLY for synthetic offline fixtures.

    The public CLI has no pin/path override and always requires the native pins.
    """
    rows = validate_rows(rows)
    conditions = validate_before(before)
    pins = PINS if unit_pins is None else unit_pins
    require(type(previous) is bytes and previous.startswith(b'#!/usr/bin/awk -f\n')
            and sha(previous) == previous_sha
            and re.fullmatch('[0-9a-f]{64}', previous_sha), 'Exact prior AWK bytes required')
    previous_text = previous.decode('utf-8')
    require(set(pins) == set(UNITS) and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in pins.values()), 'Exact unit pin allowlist required')
    token = 'q70d-privacy-extension-'+sha(json.dumps({'rows': rows, 'before': before, 'previous': previous_sha, 'pins': pins}, sort_keys=True))
    def metadata(text):
        return text.replace('chown 0:0', transform('chown 0:0'))
    common = recognition.COMMON.replace('/opt|/opt/usr|/opt/usr/share)', '/opt|/opt/usr|/opt/usr/share|/opt/usr/share/systemd/system)')
    base = transform('#!/bin/sh\n'+common+f'D={D}\nH={HOOK}\nDB={reg.DB}\nTOKEN={token}\n')
    base += '''absent() { test ! -e "$1" && test ! -L "$1"; }
receipt() {
 (set -C; printf '%s\\n' "$TOKEN" > "$R/$1") || fail receipt
 chown 0:0 "$R/$1"; chmod 600 "$R/$1"
 chsmack -a _ "$R/$1" || fail receipt-label
 owned "$1"
}
owned() { regular "$R/$1" 600; label "$R/$1"; test "$(cat "$R/$1")" = "$TOKEN" || fail receipt-owner; }
marker() { regular "$1" 600; label "$1"; test "$(cat "$1")" = "$TOKEN" || fail marker-owner; }
'''
    dirs = transform('for p in /opt /opt/etc /opt/usr /opt/usr/share /opt/usr/share/systemd/system; do secure_dir "$p"; done\n')
    checks = ''
    for unit in UNITS:
        path = '/usr/lib/systemd/system/'+unit
        checks += f'test -f {path} && test ! -L {path} || fail unit-type\ntest "$(hash {path})" = {pins[unit]} || fail unit-pin\n'
    checks = transform(checks)
    condition_shell = 'conditions() {\n'
    for unit in sorted(conditions):
        expected = '\n'.join(sorted('ConditionPathExists='+v for v in conditions[unit]['ConditionPathExists']))
        condition_shell += 'raw=$(systemctl cat '+Q(unit)+') || fail condition-command\n'
        condition_shell += '''actual=$(printf '%s\\n' "$raw" | awk '/^[[:space:]]*ConditionPathExists[[:space:]]*=/ {sub(/^[[:space:]]*/, ""); print}' | sort)
'''
        condition_shell += 'test "$actual" = '+Q(expected)+' || fail condition-drift\n'
    condition_shell += '}\n'
    appbase = base+dirs+transform(condition_shell)+'''secure_dir "$D"
regular "$D/intent" 600; label "$D/intent"
test "$(cat "$D/intent")" = "$TOKEN" || fail plan-owner
test -f "$DB" && test ! -L "$DB" || fail database-type
test "$(sqlite3 -readonly "$DB" 'PRAGMA quick_check;')" = ok || fail database-integrity
'''
    registry_functions = ''
    for mode in ('before', 'after', 'either'):
        queries = '\n'.join(reg.guard_queries(rows, mode))
        registry_functions += 'registry_'+mode+'() {\nresult=$(\n'+reg.heredoc('sqlite3 -readonly -bail "$DB"', queries, 'READ_REGISTRY')+')\n'
        registry_functions += 'test "$result" = '+Q('\n'.join(['1']*(1+2*len(rows))))+' || fail registry-drift\n}\n'
    appbase += registry_functions
    markers_before = ''.join('absent '+Q(p)+' || fail marker-present\n' for p in MARKERS)
    markers_after = ''.join('marker '+Q(p)+'\n' for p in MARKERS)
    auth = 'test "$#" = 1 && test "$1" = --authorize || fail explicit-authorization-required\n'
    apply_sql, inverse_sql = reg.sql_plan(rows), reg.sql_plan(rows, inverse=True)
    appapply = appbase+auth+'conditions\nregistry_before\n'+transform(markers_before)+'''R="$D/apps"
mkdir -m 700 "$R" || fail apply-replay
chown 0:0 "$R"; chsmack -a _ "$R"
receipt plan.bound
(cd "$R"; sqlite3 -readonly -bail "$DB" '.backup before.db')
test "$(sqlite3 -readonly "$R/before.db" 'PRAGMA quick_check;')" = ok || fail backup-integrity
receipt backup.complete
receipt registry.intent
'''+reg.heredoc('sqlite3 -bail "$DB"', apply_sql, 'APPLY_REGISTRY')+'registry_after\nreceipt registry.complete\n'
    for i, p in enumerate(MARKERS):
        appapply += transform(f'''receipt marker-{i}.intent
(set -C; printf '%s\\n' "$TOKEN" > {Q(p)}) || fail marker-create
chown 0:0 {Q(p)}; chmod 600 {Q(p)}; chsmack -a _ {Q(p)}
marker {Q(p)}
receipt marker-{i}.complete
''')
    appapply += 'registry_after\nconditions\nreceipt apply.complete\n'
    appinverse = appbase+auth+'''R="$D/apps"
secure_dir "$R"
owned plan.bound
absent "$R/inverse.intent" && absent "$R/inverse.complete" || fail inverse-replay
registry_either
'''
    for i, p in enumerate(MARKERS):
        appinverse += transform(f'if ! absent {Q(p)}; then owned marker-{i}.intent; marker {Q(p)}; fi\n')
    appinverse += '''if ! absent "$R/registry.intent"; then owned registry.intent; owned backup.complete; else registry_before; fi
receipt inverse.intent
if ! absent "$R/registry.intent"; then
'''+reg.heredoc('sqlite3 -bail "$DB"', inverse_sql, 'INVERSE_REGISTRY')+'fi\nregistry_before\n'
    for p in MARKERS:
        appinverse += transform(f'if ! absent {Q(p)}; then marker {Q(p)}; rm {Q(p)}; fi\n')
    appinverse += 'receipt inverse.complete\n'
    readback = appbase+'''test "$#" = 1 || fail readback-argument
conditions
case "$1" in
before) registry_before
'''+transform(markers_before)+''';;
after) registry_after
'''+transform(markers_after)+''';;
*) fail readback-argument;;
esac
'''
    units = ' '.join(UNITS)
    block = base+dirs+checks+'''secure_dir "$D"
'''+transform('for p in /run/systemd /run/systemd/system; do secure_dir "$p"; done\n')+'''BOOT=$(cat '''+Q(transform('/proc/sys/kernel/random/boot_id'))+''')
case "$BOOT" in ''|*[!a-zA-Z0-9-]*) fail boot-id;; esac
B="$D/boot-$BOOT"
R="$D/boot-$BOOT.receipt"
if absent "$B"; then mkdir -m 700 "$B"; chown 0:0 "$B"; chsmack -a _ "$B"; else secure_dir "$B"; fi
mkdir -m 700 "$B/lock" || fail concurrent-or-interrupted
trap 'rmdir "$B/lock"' EXIT
if absent "$R"; then (set -C; : > "$R"); chown 0:0 "$R"; chmod 600 "$R"; chsmack -a _ "$R"; else regular "$R" 600; label "$R"; fi
printf 'status=started\\n' > "$R"
'''
    # Validate all four names before creating any. An interrupted unrecorded mask
    # is refused, not adopted. Same-boot reentry requires the exact inode record.
    block += transform(f'''for n in {units}; do
 p=/run/systemd/system/$n
 absent /etc/systemd/system/$n || fail persistent-foreign-mask
 if ! absent "$p"; then
  test -L "$p" && test "$(readlink "$p")" = /dev/null || fail foreign-mask
  regular "$B/$n.owner" 600; label "$B/$n.owner"
  test "$(cat "$B/$n.owner")" = "$(stat -c '%d:%i:%u:%g' "$p")" || fail foreign-mask-identity
 else
  absent "$B/$n.owner" || fail interrupted-mask
 fi
done
for n in {units}; do
 p=/run/systemd/system/$n
 if absent "$p"; then
  ln -s /dev/null "$p" || fail mask-create
  (set -C; stat -c '%d:%i:%u:%g' "$p" > "$B/$n.owner") || fail mask-owner
  chown 0:0 "$B/$n.owner"; chmod 600 "$B/$n.owner"; chsmack -a _ "$B/$n.owner"
 fi
done
''')
    block += 'systemctl daemon-reload || fail reload\n'
    block += ''.join('systemctl --no-block stop '+n+' || fail stop\n' for n in UNITS)
    block += f'''i=0
while test "$i" -le 8; do
 ok=1
 for n in {units}; do
  s=$(systemctl show "$n" -p Id -p LoadState -p ActiveState -p MainPID) || fail show
  properties='Id LoadState ActiveState'
  test "$n" = wifi-presence.path || properties="$properties MainPID"
  for property in $properties; do
   test "$(printf '%s\\n' "$s" | grep -c "^$property=")" = 1 || fail property-count
  done
  printf '%s\\n' "$s" | grep -Fx "Id=$n" >/dev/null || fail id
  for line in LoadState=masked ActiveState=inactive; do
   printf '%s\\n' "$s" | grep -Fx "$line" >/dev/null || ok=0
  done
  if test "$n" != wifi-presence.path || printf '%s\\n' "$s" | grep -q '^MainPID='; then
   test "$(printf '%s\\n' "$s" | grep -c '^MainPID=')" = 1 || fail property-count
   printf '%s\\n' "$s" | grep -Fx 'MainPID=0' >/dev/null || ok=0
  fi
 done
 test "$ok" = 1 && break
 test "$i" = 8 && break
 sleep 1
 i=$((i+1))
done
test "$ok" = 1 || fail not-quiescent
if rmdir "$B/lock"; then trap - EXIT; else trap - EXIT; fail lock-release; fi
printf 'status=success masked=4 inactive=4 service_MainPID0=3\\n' > "$R"
'''
    block = metadata(block)
    guard = base+dirs+'''secure_dir "$D"
regular "$D/previous.awk" 600; label "$D/previous.awk"
'''+f'test "$(hash "$D/previous.awk")" = {previous_sha} || fail previous-pin\n'+'''regular "$D/block.sh" 600; label "$D/block.sh"
'''+f'test "$(hash "$D/block.sh")" = {sha(block)} || fail block-pin\n'
    wrapper = '#!/usr/bin/awk -f\n# Q70D privacy extension v1; prior AWK first\nBEGIN {\n'
    for command, code in ((guard+'exec /usr/bin/awk -f "$D/previous.awk"\n', 81),
                          (guard+'. "$D/block.sh"\n', 82)):
        wrapper += ' if (system('+json.dumps('/bin/sh -c '+Q(command))+') != 0) exit '+str(code)+';\n'
    wrapper += ' exit 0;\n}\n'
    runtime_readback = '''regular "$H" 755; label "$H"
'''+f'test "$(hash "$H")" = {sha(wrapper)} || fail installed-hook-pin\n'+transform('''for p in /run/systemd /run/systemd/system; do secure_dir "$p"; done
BOOT=$(cat /proc/sys/kernel/random/boot_id)
case "$BOOT" in ''|*[!a-zA-Z0-9-]*) fail boot-id;; esac
B="$D/boot-$BOOT"
secure_dir "$B"
absent "$B/lock" || fail runtime-incomplete
regular "$D/boot-$BOOT.receipt" 600; label "$D/boot-$BOOT.receipt"
test "$(cat "$D/boot-$BOOT.receipt")" = 'status=success masked=4 inactive=4 service_MainPID0=3' || fail runtime-receipt
''')
    for unit in UNITS:
        runtime_readback += transform(f'''p=/run/systemd/system/{unit}
absent /etc/systemd/system/{unit} || fail persistent-foreign-mask
test -L "$p" && test "$(readlink "$p")" = /dev/null || fail missing-mask
regular "$B/{unit}.owner" 600; label "$B/{unit}.owner"
test "$(cat "$B/{unit}.owner")" = "$(stat -c '%d:%i:%u:%g' "$p")" || fail mask-identity
''')
        runtime_readback += f's=$(systemctl show {unit} -p Id -p LoadState -p ActiveState -p MainPID) || fail show\n'
        required_properties = ('Id', 'LoadState', 'ActiveState') + (() if unit == 'wifi-presence.path' else ('MainPID',))
        runtime_readback += 'for property in '+' '.join(required_properties)+'''; do
 test "$(printf '%s\\n' "$s" | grep -c "^$property=")" = 1 || fail property-count
done
'''
        for expected in ('Id='+unit, 'LoadState=masked', 'ActiveState=inactive'):
            runtime_readback += 'printf \'%s\\n\' "$s" | grep -Fx '+Q(expected)+' >/dev/null || fail runtime-state\n'
        if unit == 'wifi-presence.path':
            runtime_readback += '''if printf '%s\\n' "$s" | grep -q '^MainPID='; then
 test "$(printf '%s\\n' "$s" | grep -c '^MainPID=')" = 1 || fail property-count
 printf '%s\\n' "$s" | grep -Fx 'MainPID=0' >/dev/null || fail runtime-state
fi
'''
        else:
            runtime_readback += "printf '%s\\n' \"$s\" | grep -Fx 'MainPID=0' >/dev/null || fail runtime-state\n"
    readback = readback.replace('after) registry_after\n', 'after) registry_after\n'+runtime_readback)
    hookinverse = base+dirs+auth+'''secure_dir "$D"
R="$D"
owned intent
regular "$H" 755; label "$H"
'''+f'test "$(hash "$H")" = {sha(wrapper)} || fail hook-pin\n'+'''regular "$D/previous.awk" 600; label "$D/previous.awk"
'''+f'test "$(hash "$D/previous.awk")" = {previous_sha} || fail previous-pin\n'+'''absent "$D/restore.intent" && absent "$D/restored" || fail restore-replay
receipt restore.intent
T="$H.privacy-extension-restore"
(set -C; cat "$D/previous.awk" > "$T") || fail stage
chown 0:0 "$T"; chmod 755 "$T"; chsmack -a _ "$T"
regular "$T" 755; label "$T"
'''+f'test "$(hash "$T")" = {previous_sha} || fail stage-pin\nregular "$H" 755; label "$H"\ntest "$(hash "$H")" = {sha(wrapper)} || fail hook-changed\n'+'''mv -T "$T" "$H"
receipt restored
# Runtime masks intentionally retained; no starts/reloads/unmasks.
'''
    hookinstall = base+dirs+checks+auth+registry_functions+'''test -f "$DB" && test ! -L "$DB" || fail database-type
test "$(sqlite3 -readonly "$DB" 'PRAGMA quick_check;')" = ok || fail database-integrity
registry_before
'''+transform(condition_shell)+'''conditions
absent "$D" || fail install-replay
regular "$H" 755; label "$H"
'''+f'test "$(hash "$H")" = {previous_sha} || fail previous-pin\n'+transform(markers_before)+transform(f'''for n in {units}; do
 for p in /run/systemd/system/$n /etc/systemd/system/$n; do absent "$p" || fail preexisting-mask; done
done
''')+'''mkdir -m 700 "$D" || fail install-create
chown 0:0 "$D"; chsmack -a _ "$D"
secure_dir "$D"
R="$D"
receipt intent
(cd "$D"; sqlite3 -readonly -bail "$DB" '.backup before.db')
test "$(sqlite3 -readonly "$D/before.db" 'PRAGMA quick_check;')" = ok || fail backup-integrity
chown 0:0 "$D/before.db"; chmod 600 "$D/before.db"; chsmack -a _ "$D/before.db"
receipt backup.complete
(set -C; cat "$H" > "$D/previous.awk") || fail previous-copy
chown 0:0 "$D/previous.awk"; chmod 600 "$D/previous.awk"; chsmack -a _ "$D/previous.awk"
regular "$D/previous.awk" 600; label "$D/previous.awk"
'''+f'test "$(hash "$D/previous.awk")" = {previous_sha} || fail previous-copy-pin\n'
    hookinverse = metadata(hookinverse)
    for name, data, mode in [('block.sh', block, '600'), ('hook-inverse.sh', hookinverse, '600'),
                             ('app-inverse.sh', metadata(appinverse), '600'), ('wrapper.awk', wrapper, '755')]:
        encoded = base64.b64encode(data.encode()).decode()
        hookinstall += f'(set -C; printf %s {encoded} | base64 -d > "$D/{name}") || fail prepare\n'
        hookinstall += metadata(f'chown 0:0 "$D/{name}"; chmod {mode} "$D/{name}"; chsmack -a _ "$D/{name}"\n')
        hookinstall += f'regular "$D/{name}" {mode}; label "$D/{name}"\ntest "$(hash "$D/{name}")" = {sha(data)} || fail prepare-pin\n'
    hookinstall += '''T="$H.privacy-extension-new"
(set -C; cat "$D/wrapper.awk" > "$T") || fail stage
chown 0:0 "$T"; chmod 755 "$T"; chsmack -a _ "$T"
regular "$T" 755; label "$T"
'''+f'test "$(hash "$T")" = {sha(wrapper)} || fail stage-pin\nregular "$H" 755; label "$H"\ntest "$(hash "$H")" = {previous_sha} || fail previous-changed\n'+'''mv -T "$T" "$H"
receipt installed
# Hook NOT executed. No service activation is included in this packet.
'''
    return {'app-apply.sh': metadata(appapply), 'app-inverse.sh': metadata(appinverse),
            'hook-install.sh': metadata(hookinstall), 'hook-inverse.sh': hookinverse,
            'block.sh': block, 'wrapper.awk': wrapper, 'selected-readback.sh': readback,
            'apply.sql': apply_sql, 'inverse.sql': inverse_sql, 'previous.awk': previous_text}


def emit(packet, rows, before, snapshot_sha, output):
    """Write private create-once local output. Failure may leave partial output."""
    output = Path(output)
    require(not output.resolve().is_relative_to(ROOT.resolve()), 'Private output outside repository required')
    require(not os.path.lexists(output) and output.parent.is_dir(), 'New output and existing parent required')
    manifest = {'schema_version': 1, 'offline_only': True, 'tested_identity': reg.IDENTITY,
                'runtime_directory': D, 'hook': HOOK, 'registry_before': rows, 'before': before,
                'snapshot_sha256': snapshot_sha, 'previous_hook_sha256': sha(packet['previous.awk']),
                'unit_sha256': PINS, 'app_ids': list(IDS), 'masked_units': list(UNITS),
                'limitations': ['no activation', 'no process termination or absence proof', 'early boot window possible',
                                'finite polls, no hard native-call timeout', 'not crash atomic',
                                'hook inverse retains masks; app inverse never starts services',
                                'interrupted inverse refuses replay; manual reconciliation required'],
                'files': {n: {'sha256': sha(s), 'bytes': len(s.encode()), 'mode': '0600'} for n, s in packet.items()}}
    payloads = {**packet, 'manifest.json': json.dumps(manifest, indent=2, sort_keys=True)+'\n'}
    output.mkdir(mode=0o700)
    for name, content in payloads.items():
        fd = os.open(output/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
    return manifest


def generate(snapshot, before_path, previous_path, output):
    before = reg.read_json(Path(before_path))
    validate_before(before)
    rows, digest = read_snapshot(snapshot)
    prior = Path(previous_path)
    require(prior.is_file() and not prior.is_symlink(), 'Regular immutable prior bytes required')
    previous = prior.read_bytes()
    packet = render(rows, before, previous)
    require(prior.read_bytes() == previous, 'Prior changed during planning')
    return emit(packet, rows, before, digest, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'before', 'previous-hook', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        generate(args.snapshot, args.before, args.previous_hook, args.output)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print('privacy-extension: refused; check captured inputs, native pins and new private output.', file=sys.stderr)
        return 1
    print('Generated private offline extension. Nothing installed, activated or restored.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
