#!/usr/bin/env python3
"""Generate a private, offline-only plan for the exact Q70D reference profile."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shlex
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'profiles/tq55q70datxxc-tizen8-1400.0.json'
IDENTITY = {'model': 'TQ55Q70DATXXC', 'family': 'Q70D', 'diagonal_inches': 55,
            'tizen': '8.0', 'architecture': 'ARMv7 32-bit', 'firmware': 'T-PTMLDDEUC-1400.0'}
FIELDS = ('app_disable', 'app_onboot', 'app_autorestart')
DESIRED = dict(zip(FIELDS, ('true', 'false', 'false')))
IDS = (
    'com.samsung.tizen.samsung-analytics', 'com.samsung.tv.acr',
    'com.samsung.tv.adagent-service', 'com.samsung.tv.canalysis-service',
    'com.samsung.tv.contents-recognition-dbmgr', 'com.samsung.tv.pisa-service',
    'com.samsung.tv.targeted-ad-service', 'org.tizen.pisa-control-service',
    'com.samsung.tv.alexa-client', 'com.samsung.tv.alexa-fullscreen-app',
    'com.samsung.tv.bixby-context-client', 'com.samsung.tv.bixby-promotion',
    'com.samsung.tv.bixby-prov', 'com.samsung.tv.bixbycapsuleviewer',
    'com.samsung.tv.farfieldvoice', 'com.samsung.tv.mybixby',
    'com.samsung.tv.ondevice-voice', 'com.samsung.tv.utterance-recommender-app',
    'com.samsung.tv.utterance-recommender-core', 'com.samsung.tv.voice-instant-app',
    'com.samsung.tv.voiceassistant-music', 'com.samsung.tv.wakeup-engine-alexa',
    'com.samsung.tv.wakeup-engine-bixby',
)
PREFS = ('db/menu/voice/voice_activated', 'db/si_service/voice_recog_enable',
         'db/multi-assistant/prelaunch_mode')
MARKERS = {
    '/opt/usr/share/systemd/system/pisa-service': ('pisa-service.service', 'adagent-service.service'),
    '/opt/usr/share/systemd/system/canalysis-daemon': ('canalysis-service.service',),
    '/opt/usr/share/systemd/system/com.samsung.tv.bixby-prov': ('com.samsung.tv.bixby-prov.service',),
    '/opt/usr/share/systemd/system/com.samsung.tv.ondevice-voice': ('com.samsung.tv.ondevice-voice.service',),
    '/opt/usr/share/systemd/system/com.samsung.tv.farfieldvoice': ('com.samsung.tv.farfieldvoice.service',),
}
DB = '/opt/dbspace/.pkgmgr_parser.db'
Q = shlex.quote


class Refusal(ValueError):
    """A failed closed validation boundary, with no private values in errors."""


def require(value, message):
    if not value:
        raise Refusal(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    require(not path.is_symlink() and path.is_file(), 'JSON input must be a regular non-symlink file')
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def entries(value, fields, key, expected):
    require(type(value) is list, 'Expected an explicit list')
    require(all(type(row) is dict and set(row) == set(fields) for row in value), 'Unexpected entry fields')
    keys = [row[key] for row in value]
    require(all(type(k) is str for k in keys), 'Invalid identifier type')
    require(len(keys) == len(set(keys)) and set(keys) == set(expected), 'Unknown, missing or duplicate selected identifier')
    return {row[key]: row for row in value}


def validate_profile(profile):
    require(profile['schema_version'] == 1 and profile['tested_identity'] == IDENTITY, 'Unsupported profile identity')
    registry = profile['registry']
    require(registry['table'] == 'package_app_info' and registry['key'] == 'app_id'
            and registry['fields'] == list(FIELDS) and registry['desired_flags'] == DESIRED
            and registry['database_path_observed'] == DB and registry['selected_count'] == 23,
            'Unsupported registry profile')
    selected = [row['app_id'] for row in registry['selected_components']]
    require(len(selected) == 23 and set(selected) == set(IDS), 'Unsupported selected components')
    require([(p['key'], p['type'], p['desired']) for p in profile['voice_preferences']]
            == [(key, 'Boolean', False) for key in PREFS], 'Unsupported preference profile')
    require({m['path']: tuple(m['unit_names']) for m in profile['condition_markers']} == MARKERS
            and len(profile['condition_markers']) == 5, 'Unsupported marker profile')


def validate_before(before):
    require(type(before) is dict and set(before) == {'schema_version', 'tested_identity', 'preferences', 'markers', 'unit_conditions'}, 'Unexpected BEFORE fields')
    require(type(before['schema_version']) is int and before['schema_version'] == 1
            and before['tested_identity'] == IDENTITY
            and type(before['tested_identity'].get('diagonal_inches')) is int, 'BEFORE identity must match the exact tested build')
    prefs = entries(before['preferences'], ('key', 'type', 'value'), 'key', PREFS)
    require(all(p['type'] == 'Boolean' and type(p['value']) is bool for p in prefs.values()), 'Preferences require actual typed Boolean values')
    markers = entries(before['markers'], ('path', 'state'), 'path', MARKERS)
    require(all(m['state'] == 'absent' for m in markers.values()), 'All five markers must be observed absent')
    units = {u: path for path, names in MARKERS.items() for u in names}
    conditions = entries(before['unit_conditions'], ('unit', 'ConditionPathExists'), 'unit', units)
    require(all(conditions[u]['ConditionPathExists'] == ['!' + path] for u, path in units.items()), 'Every actual consumer condition must match its exact negative marker')
    return prefs


def no_sidecars(path):
    require(all(not Path(str(path) + suffix).exists() and not Path(str(path) + suffix).is_symlink()
                for suffix in ('-wal', '-shm', '-journal')), 'Export a standalone consistent SQLite snapshot without sidecars')


def read_snapshot(path):
    require(not path.is_symlink() and path.is_file(), 'Snapshot must be a regular non-symlink file')
    path = path.resolve(strict=True)
    no_sidecars(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as con:
        require(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Snapshot integrity check failed')
        require(con.execute("SELECT type FROM sqlite_master WHERE name='package_app_info'").fetchall() == [('table',)], 'Registry table missing')
        require(not con.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name='package_app_info'").fetchall(), 'Registry triggers require separate review')
        rows = []
        for app in IDS:
            matches = con.execute('SELECT app_disable,app_onboot,app_autorestart FROM package_app_info WHERE app_id=?', (app,)).fetchall()
            require(len(matches) == 1, 'Missing or duplicate selected database identifier')
            require(all(type(v) is str and v in ('true', 'false') for v in matches[0]), 'Selected flags require SQLite text true/false')
            rows.append(dict(zip(('app_id',) + FIELDS, (app,) + matches[0])))
    no_sidecars(path)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Source snapshot changed during planning')
    return rows, digest


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def match(row):
    return ' AND '.join('typeof(' + f + ")='text' AND " + f + ' IS ' + literal(row[f]) for f in FIELDS)


def guard_queries(rows, mode):
    queries = ["SELECT count(*)=0 FROM sqlite_master WHERE type='trigger' AND tbl_name='package_app_info';"]
    for row in rows:
        key = 'app_id=' + literal(row['app_id'])
        queries.append('SELECT count(*)=1 FROM package_app_info WHERE ' + key + ';')
        if mode == 'before':
            predicate = match(row)
        elif mode == 'after':
            predicate = match(DESIRED)
        else:
            predicate = '(' + match(row) + ') OR (' + match(DESIRED) + ')'
        queries.append('SELECT count(*)=1 FROM package_app_info WHERE ' + key + ' AND (' + predicate + ');')
    return queries


def sql_plan(rows, inverse=False):
    mode = 'either' if inverse else 'before'
    lines = ['PRAGMA busy_timeout=3000;', 'BEGIN IMMEDIATE;',
             'CREATE TEMP TABLE registry_guard(ok INTEGER NOT NULL CHECK(ok=1));']
    for query in guard_queries(rows, mode):
        lines.append('INSERT INTO registry_guard ' + query)
    for row in rows:
        desired = row if inverse else DESIRED
        assignments = ','.join(f + '=' + literal(desired[f]) for f in FIELDS)
        lines.append('UPDATE package_app_info SET ' + assignments + ' WHERE app_id=' + literal(row['app_id']) + ';')
        lines.append('INSERT INTO registry_guard SELECT changes()=1;')
    lines += ['DROP TABLE registry_guard;', 'COMMIT;']
    return '\n'.join(lines) + '\n'


def heredoc(command, text, tag):
    return command + " <<'" + tag + "'\n" + text.rstrip() + '\n' + tag + '\n'


def pref_output(key, value):
    return key + ', value = ' + ('True' if value else 'False') + ' (Boolean)'


def common_shell(rows, prefs, token):
    text = '''#!/bin/sh
# Private generated plan. Review before explicitly running on the exact tested TV.
set -eu
umask 077
fail() { printf '%s\\n' "registry: $*" >&2; exit 1; }
'''
    text += 'DB=' + Q(DB) + '\nTOKEN=' + Q(token) + '\n'
    text += '''test "$(id -u)" = 0 || fail 'root required'
command -v sqlite3 >/dev/null || fail 'sqlite3 required'
command -v vconftool >/dev/null || fail 'vconftool required'
command -v systemctl >/dev/null || fail 'systemctl required'
test -f "$DB" && test ! -L "$DB" || fail 'unsafe native database'
check_db() {
    test "$(sqlite3 -readonly "$DB" 'PRAGMA quick_check;')" = ok || fail 'integrity check failed'
}
absent() { test ! -e "$1" && test ! -L "$1"; }
receipt() { (set -C; printf '%s\\n' "$TOKEN" > "$R/$1"); }
owned() { test -f "$R/$1" && test ! -L "$R/$1" && test "$(cat "$R/$1")" = "$TOKEN"; }
check_marker() { test -f "$1" && test ! -L "$1" && test "$(cat "$1")" = "$TOKEN"; }
conditions() {
'''
    for path, units in MARKERS.items():
        for unit in units:
            # Exactly one effective ConditionPathExists entry, no additional reset/positive entries.
            text += '    raw=$(systemctl cat ' + Q(unit) + ") || fail 'unit condition command failed'\n"
            text += '    actual=$(printf \'%s\\n\' "$raw" | awk \'/^[[:space:]]*ConditionPathExists[[:space:]]*=/ {sub(/^[[:space:]]*/, ""); print}\')\n'
            text += '    test "$actual" = ' + Q('ConditionPathExists=!' + path) + " || fail 'unit conditions drifted'\n"
    text += '}\n'
    for mode in ('before', 'after', 'either'):
        text += 'registry_' + mode + '() {\n'
        queries = '\n'.join(guard_queries(rows, mode))
        text += '    result=$(\n' + heredoc('sqlite3 -readonly -bail "$DB"', queries, 'REGISTRY_READ') + ')\n'
        text += '    test "$result" = ' + Q('\n'.join(['1'] * (1 + 2 * len(rows)))) + " || fail 'registry drift or missing selected row'\n}\n"
        text += 'prefs_' + mode + '() {\n'
        for key in PREFS:
            before = prefs[key]['value']
            a, b = Q(pref_output(key, before)), Q(pref_output(key, False))
            text += '    value=$(vconftool get ' + Q(key) + ')\n'
            expression = 'test "$value" = ' + (a if mode == 'before' else b)
            if mode == 'either':
                expression = '{ test "$value" = ' + a + ' || test "$value" = ' + b + '; }'
            text += '    ' + expression + " || fail 'preference drift or wrong type'\n"
        text += '}\n'
    text += 'markers_before() {\n'
    for path in MARKERS:
        text += '    absent ' + Q(path) + " || fail 'marker must be absent'\n"
    text += '}\nmarkers_after() {\n'
    for path in MARKERS:
        text += '    check_marker ' + Q(path) + " || fail 'marker missing or changed'\n"
    text += '}\n'
    return text


def readback_shell(common):
    return common + '''test "$#" = 1 || fail 'usage: selected-readback.sh before|after'
conditions
check_db
case "$1" in
    before) registry_before; prefs_before; markers_before ;;
    after) registry_after; prefs_after; markers_after ;;
    *) fail 'usage: selected-readback.sh before|after' ;;
esac
printf '%s\\n' 'Selected registry, typed preferences and all five conditions/markers verified.'
'''


def apply_shell(common, sql, prefs):
    text = common + '''test "$#" = 2 && test "$1" = --authorize || fail 'usage: apply.sh --authorize /absolute/private/new-run-dir'
R=$2
case "$R" in /*) ;; *) fail 'absolute private run directory required';; esac
conditions
check_db
registry_before
prefs_before
markers_before
mkdir -m 700 "$R" || fail 'run directory must be create-once'
receipt plan.bound
# A consistent SQLite online backup, never a raw copy of a live database.
# backup path is fixed after changing to the new private run directory.
(cd "$R"; sqlite3 -readonly -bail "$DB" '.backup before.db')
test "$(sqlite3 -readonly "$R/before.db" 'PRAGMA quick_check;')" = ok || fail 'backup integrity failed'
receipt backup.complete
receipt registry.intent
'''
    text += heredoc('sqlite3 -bail "$DB"', sql, 'REGISTRY_APPLY')
    text += 'registry_after\nreceipt registry.complete\n'
    for i, key in enumerate(PREFS):
        text += 'receipt pref-' + str(i) + '.intent\n'
        text += 'vconftool set -f -t bool ' + Q(key) + ' 0\n'
        text += 'test "$(vconftool get ' + Q(key) + ')" = ' + Q(pref_output(key, False)) + " || fail 'preference setter readback failed'\n"
        text += 'receipt pref-' + str(i) + '.complete\n'
    for i, path in enumerate(MARKERS):
        text += 'receipt marker-' + str(i) + '.intent\n'
        text += '(set -C; printf \'%s\\n\' "$TOKEN" > ' + Q(path) + ')\n'
        text += 'check_marker ' + Q(path) + " || fail 'marker creation readback failed'\n"
        text += 'receipt marker-' + str(i) + '.complete\n'
    units = [unit for names in MARKERS.values() for unit in names]
    text += 'receipt stop.intent\nsystemctl stop ' + ' '.join(map(Q, units)) + '\nreceipt stop.complete\n'
    text += 'check_db\nregistry_after\nprefs_after\nmarkers_after\nconditions\nreceipt apply.complete\n'
    text += "printf '%s\\n' 'Apply verified; reboot remains manual. Voice features are disabled.'\n"
    return text


def inverse_shell(common, sql, prefs):
    text = common + '''test "$#" = 2 && test "$1" = --authorize || fail 'usage: inverse.sh --authorize /absolute/private/run-dir'
R=$2
case "$R" in /*) ;; *) fail 'absolute private run directory required';; esac
test -d "$R" && test ! -L "$R" || fail 'unsafe run directory'
owned plan.bound || fail 'run directory is not bound to this plan'
absent "$R/inverse.complete" || fail 'inverse already complete'
conditions
check_db
registry_either
prefs_either
'''
    # Validate the entire pending recovery set before the first inverse write.
    for i, path in enumerate(MARKERS):
        text += 'if ! absent ' + Q(path) + '; then\n'
        text += '    owned marker-' + str(i) + ".intent || fail 'unowned marker stage'\n"
        text += '    check_marker ' + Q(path) + " || fail 'foreign or changed marker'\nfi\n"
    text += '''if owned registry.intent; then
    owned backup.complete || fail 'missing validated backup stage'
else
    registry_before
fi
'''
    for i, key in enumerate(PREFS):
        text += 'if ! owned pref-' + str(i) + '.intent; then\n'
        text += '    test "$(vconftool get ' + Q(key) + ')" = ' + Q(pref_output(key, prefs[key]['value'])) + " || fail 'preference changed outside this plan'\nfi\n"
    text += '''# A prior interrupted inverse may be retried: each recovery write is idempotent.
# No promise is made about power loss between a mutation and its receipt.
if absent "$R/inverse.intent"; then receipt inverse.intent; else owned inverse.intent || fail 'invalid inverse intent'; fi
if owned registry.intent; then
'''
    text += heredoc('sqlite3 -bail "$DB"', sql, 'REGISTRY_INVERSE') + 'fi\nregistry_before\n'
    for i, key in enumerate(PREFS):
        text += 'if owned pref-' + str(i) + '.intent; then\n'
        text += '    vconftool set -f -t bool ' + Q(key) + (' 1\n' if prefs[key]['value'] else ' 0\n')
        text += '    test "$(vconftool get ' + Q(key) + ')" = ' + Q(pref_output(key, prefs[key]['value'])) + " || fail 'inverse preference readback failed'\nfi\n"
    for path in MARKERS:
        text += 'if ! absent ' + Q(path) + '; then check_marker ' + Q(path) + ' || fail \'marker changed\'; rm ' + Q(path) + '; fi\n'
    text += 'check_db\nregistry_before\nprefs_before\nmarkers_before\nconditions\nreceipt inverse.complete\n'
    text += "printf '%s\\n' 'Captured fields/preferences and absent markers restored. Services are NOT started; reboot is manual.'\n"
    return text


def generate(snapshot, before_path, output):
    # All validation is completed before creating any output.
    destination = output.resolve()
    require(not destination.is_relative_to(ROOT.resolve()), 'Private output must be outside the repository')
    require(not output.exists() and not output.is_symlink(), 'Output must be a new directory')
    require(output.parent.is_dir(), 'Output parent must already exist')
    profile = read_json(PROFILE)
    validate_profile(profile)
    before = read_json(before_path)
    prefs = validate_before(before)
    rows, digest = read_snapshot(snapshot)
    binding = json.dumps({'before': before, 'rows': rows, 'source_sha256': digest}, sort_keys=True).encode()
    token = 'registry-plan-' + hashlib.sha256(binding).hexdigest()
    common = common_shell(rows, prefs, token)
    apply_sql, inverse_sql = sql_plan(rows), sql_plan(rows, inverse=True)
    files = {'apply.sql': apply_sql, 'inverse.sql': inverse_sql,
             'apply.sh': apply_shell(common, apply_sql, prefs),
             'inverse.sh': inverse_shell(common, inverse_sql, prefs),
             'selected-readback.sh': readback_shell(common)}
    manifest = {'schema_version': 1, 'tested_identity': IDENTITY, 'selected_count': 23,
                'source_sha256': digest, 'before': before, 'registry_before': rows,
                'plan_token': token, 'reboot': 'manual', 'crash_atomic': False,
                'files_sha256': {name: hashlib.sha256(value.encode()).hexdigest() for name, value in files.items()}}
    files['manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    output.mkdir(mode=0o700)
    for name, content in files.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path, help='Owner-exported standalone consistent SQLite snapshot (read only)')
    parser.add_argument('--before', required=True, type=Path, help='Actual identity, typed preferences, absent markers and six consumer conditions')
    parser.add_argument('--output', required=True, type=Path, help='New private directory outside this repository')
    args = parser.parse_args(argv)
    try:
        generate(args.snapshot, args.before, args.output)
    except (Refusal, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        print('registry: refused; check exact profile, actual BEFORE schema, consistent snapshot and new private output (see docs/registry-tool.md).', file=sys.stderr)
        return 1
    print('Private offline plan generated: 23 components, 3 Boolean preferences, 5 markers / 6 consumers. Nothing executed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
