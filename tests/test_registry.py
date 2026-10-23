"""Synthetic, hardware-free tests; only external command boundaries are faked."""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/registry.py'
PROFILE = ROOT / 'profiles/tq55q70datxxc-tizen8-1400.0.json'


@contextmanager
def connect(path):
    con = sqlite3.connect(path)
    try:
        with con:
            yield con
    finally:
        con.close()


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='registry-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.profile = json.loads(PROFILE.read_text())
        self.ids = [c['app_id'] for c in self.profile['registry']['selected_components']]
        self.fields = self.profile['registry']['fields']
        self.db = self.base / 'source.db'
        with connect(self.db) as con:
            con.execute('CREATE TABLE package_app_info(app_id TEXT, app_disable TEXT, app_onboot TEXT, app_autorestart TEXT, unrelated TEXT)')
            for i, app in enumerate(self.ids):
                con.execute('INSERT INTO package_app_info VALUES(?,?,?,?,?)', (app, 'true' if i % 2 else 'false', 'true', 'false' if i % 3 else 'true', 'keep'))
            con.execute("INSERT INTO package_app_info VALUES('org.example.preserved','false','true','true','untouched')")
        self.before = {
            'schema_version': 1,
            'tested_identity': self.profile['tested_identity'],
            'preferences': [{'key': p['key'], 'type': 'Boolean', 'value': i != 1} for i, p in enumerate(self.profile['voice_preferences'])],
            'markers': [{'path': m['path'], 'state': 'absent'} for m in self.profile['condition_markers']],
            'unit_conditions': [{'unit': u, 'ConditionPathExists': ['!' + m['path']]} for m in self.profile['condition_markers'] for u in m['unit_names']],
        }
        self.before_path = self.base / 'before.json'
        self.out = self.base / 'plan'

    def cli(self, before=None, output=None):
        self.before_path.write_text(json.dumps(self.before if before is None else before))
        return subprocess.run([sys.executable, str(TOOL), '--snapshot', str(self.db), '--before', str(self.before_path), '--output', str(output or self.out)], capture_output=True, text=True)

    def generate(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.out

    def dump(self, path):
        with connect(path) as con:
            return con.execute('SELECT * FROM package_app_info ORDER BY app_id').fetchall()

    def test_cli_positive_private_output_and_snapshot_unchanged(self):
        digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.generate()
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o700)
        for name in ('apply.sh', 'inverse.sh', 'selected-readback.sh', 'apply.sql', 'inverse.sql', 'manifest.json'):
            self.assertTrue((self.out / name).is_file(), name)
            self.assertEqual((self.out / name).stat().st_mode & 0o077, 0)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(manifest['selected_count'], 23)
        self.assertEqual(manifest['before']['preferences'], self.before['preferences'])
        recorded = {r['app_id']: r for r in manifest['registry_before']}
        self.assertEqual(recorded[self.ids[1]]['app_disable'], 'true')
        self.assertNotEqual(recorded[self.ids[1]]['app_disable'], self.profile['registry']['selected_components'][1]['observed_before']['app_disable'])
        self.assertNotEqual(self.cli().returncode, 0)

    def test_every_selected_field_drift_and_missing_refused_by_apply_sql(self):
        self.generate()
        sql = (self.out / 'apply.sql').read_text()
        for app in self.ids:
            for field in self.fields:
                target = self.base / 'drift.db'
                shutil.copyfile(self.db, target)
                with connect(target) as con:
                    con.execute('UPDATE package_app_info SET ' + field + "='invalid' WHERE app_id=?", (app,))
                before = self.dump(target)
                with connect(target) as con:
                    with self.assertRaises(sqlite3.DatabaseError):
                        con.executescript(sql)
                self.assertEqual(self.dump(target), before)
            target = self.base / 'missing.db'
            shutil.copyfile(self.db, target)
            with connect(target) as con:
                con.execute('DELETE FROM package_app_info WHERE app_id=?', (app,))
            with connect(target) as con:
                with self.assertRaises(sqlite3.DatabaseError):
                    con.executescript(sql)

    def test_sql_roundtrip_field_specific_preserves_other_rows(self):
        self.generate()
        original = self.dump(self.db)
        target = self.base / 'target.db'
        shutil.copyfile(self.db, target)
        with connect(target) as con:
            con.executescript((self.out / 'apply.sql').read_text())
            self.assertEqual(con.execute("SELECT count(*) FROM package_app_info WHERE app_disable='true' AND app_onboot='false' AND app_autorestart='false'").fetchone()[0], 23)
            con.execute("UPDATE package_app_info SET unrelated='new-preserved' WHERE app_id=?", (self.ids[0],))
            con.commit()
            con.executescript((self.out / 'inverse.sql').read_text())
        expected = [tuple(list(r[:4]) + ['new-preserved']) if r[0] == self.ids[0] else r for r in original]
        self.assertEqual(self.dump(target), expected)

    def test_invalid_inputs_refused_before_output(self):
        bad_cases = []
        for section in ('preferences', 'markers', 'unit_conditions'):
            b = copy.deepcopy(self.before); b[section].pop(); bad_cases.append(b)
            b = copy.deepcopy(self.before); b[section].append(copy.deepcopy(b[section][0])); bad_cases.append(b)
        b = copy.deepcopy(self.before); b['tested_identity']['firmware'] = 'other'; bad_cases.append(b)
        b = copy.deepcopy(self.before); b['preferences'][0]['value'] = 1; bad_cases.append(b)
        b = copy.deepcopy(self.before); b['markers'][0]['state'] = 'present'; bad_cases.append(b)
        b = copy.deepcopy(self.before); b['unit_conditions'][0]['ConditionPathExists'] = ['/wrong']; bad_cases.append(b)
        b = copy.deepcopy(self.before); b['preferences'][0]['key'] = 'unknown'; bad_cases.append(b)
        for i, before in enumerate(bad_cases):
            output = self.base / ('reject-' + str(i))
            self.assertNotEqual(self.cli(before, output).returncode, 0)
            self.assertFalse(output.exists())
        for corruption in ('duplicate', 'missing', 'integer'):
            with connect(self.db) as con:
                if corruption == 'duplicate':
                    con.execute('INSERT INTO package_app_info SELECT * FROM package_app_info WHERE app_id=?', (self.ids[0],))
                elif corruption == 'missing':
                    con.execute('DELETE FROM package_app_info WHERE app_id=?', (self.ids[1],))
                else:
                    con.execute('UPDATE package_app_info SET app_disable=NULL WHERE app_id=?', (self.ids[2],))
            output = self.base / corruption
            self.assertNotEqual(self.cli(output=output).returncode, 0)
            self.assertFalse(output.exists())

    def test_each_registry_corruption_independently_refused(self):
        clean = self.db.read_bytes()
        for corruption in ('duplicate', 'missing', 'null', 'integer', 'trigger'):
            with self.subTest(corruption=corruption):
                self.db.write_bytes(clean)
                with connect(self.db) as con:
                    if corruption == 'duplicate':
                        con.execute('INSERT INTO package_app_info SELECT * FROM package_app_info WHERE app_id=?', (self.ids[0],))
                    elif corruption == 'missing':
                        con.execute('DELETE FROM package_app_info WHERE app_id=?', (self.ids[0],))
                    elif corruption == 'null':
                        con.execute('UPDATE package_app_info SET app_disable=NULL WHERE app_id=?', (self.ids[0],))
                    elif corruption == 'integer':
                        con.execute('UPDATE package_app_info SET app_disable=1 WHERE app_id=?', (self.ids[0],))
                    else:
                        con.execute('CREATE TRIGGER unsafe AFTER UPDATE ON package_app_info BEGIN DELETE FROM package_app_info; END')
                output = self.base / corruption
                self.assertNotEqual(self.cli(output=output).returncode, 0)
                self.assertFalse(output.exists())

    def test_every_inverse_field_drift_and_missing_refused_before_writes(self):
        self.generate()
        apply_sql = (self.out / 'apply.sql').read_text()
        inverse_sql = (self.out / 'inverse.sql').read_text()
        applied = self.base / 'applied.db'
        shutil.copyfile(self.db, applied)
        with connect(applied) as con:
            con.executescript(apply_sql)
        clean = applied.read_bytes()
        for app in self.ids:
            for field in self.fields:
                target = self.base / 'inverse-drift.db'
                target.write_bytes(clean)
                with connect(target) as con:
                    con.execute('UPDATE package_app_info SET ' + field + "='invalid' WHERE app_id=?", (app,))
                before = self.dump(target)
                with connect(target) as con:
                    with self.assertRaises(sqlite3.DatabaseError):
                        con.executescript(inverse_sql)
                self.assertEqual(self.dump(target), before)
            target = self.base / 'inverse-missing.db'
            target.write_bytes(clean)
            with connect(target) as con:
                con.execute('DELETE FROM package_app_info WHERE app_id=?', (app,))
            with connect(target) as con:
                with self.assertRaises(sqlite3.DatabaseError):
                    con.executescript(inverse_sql)

    def test_json_duplicate_keys_and_optimized_interpreter(self):
        self.before_path.write_text(json.dumps(self.before).replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        argv = [str(TOOL), '--snapshot', str(self.db), '--before', str(self.before_path), '--output', str(self.out)]
        result = subprocess.run([sys.executable] + argv, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())
        self.before_path.write_text(json.dumps(self.before))
        result = subprocess.run([sys.executable, '-OO'] + argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stop_failure_and_every_setter_failure_recoverable(self):
        native, target, env = self.harness()
        original = self.dump(target)
        for i, failure in enumerate([p['key'] for p in self.before['preferences']] + ['stop']):
            with self.subTest(stage=i):
                run = self.base / ('failure-run-' + str(i))
                env['FAIL_SET'] = failure
                if failure == 'stop': env['FAIL_STOP'] = '1'
                result = self.run_script('apply.sh', ['--authorize', str(run)], env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((run / 'apply.complete').exists())
                env.pop('FAIL_SET'); env.pop('FAIL_STOP', None)
                result = self.run_script('inverse.sh', ['--authorize', str(run)], env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.dump(target), original)
                self.assertFalse(any(native.glob('marker-*')))

    def test_failed_condition_command_cannot_authenticate_good_text(self):
        native, target, env = self.harness()
        env['FAIL_CAT'] = '1'
        run = self.base / 'run'
        result = self.run_script('apply.sh', ['--authorize', str(run)], env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(run.exists())

    def test_run_parent_trust_is_documented(self):
        # This planner deliberately requires operator-controlled ancestors;
        # it does not claim a local-root/concurrent-writer sandbox.
        self.assertIn('operator-controlled directory ancestors', (ROOT / 'docs/registry-tool.md').read_text())

    def test_source_and_before_symlinks_refused(self):
        original = self.db
        linked = self.base / 'snapshot-link.db'
        linked.symlink_to(original)
        self.db = linked
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertFalse(self.out.exists())
        self.db = original
        original_before = self.base / 'before-original.json'
        original_before.write_text(json.dumps(self.before))
        self.before_path.unlink()
        self.before_path.symlink_to(original_before)
        result = subprocess.run([sys.executable, str(TOOL), '--snapshot', str(self.db), '--before', str(self.before_path), '--output', str(self.out)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())

    def test_readback_rejects_duplicates_and_preference_and_condition_drift(self):
        native, target, env = self.harness()
        self.assertEqual(self.run_script('selected-readback.sh', ['before'], env).returncode, 0)
        conditions = native / 'conditions.json'
        prior = conditions.read_text()
        wrong = json.loads(prior); wrong[self.before['unit_conditions'][0]['unit']] = '/wrong'
        conditions.write_text(json.dumps(wrong))
        self.assertNotEqual(self.run_script('apply.sh', ['--authorize', str(self.base / 'run')], env).returncode, 0)
        self.assertFalse((self.base / 'run').exists())
        conditions.write_text(prior)
        preferences = native / 'prefs.json'
        prior = preferences.read_text()
        wrong = json.loads(prior); wrong[self.before['preferences'][0]['key']] = False
        preferences.write_text(json.dumps(wrong))
        self.assertNotEqual(self.run_script('selected-readback.sh', ['before'], env).returncode, 0)
        preferences.write_text(prior)
        with connect(target) as con:
            con.execute('INSERT INTO package_app_info SELECT * FROM package_app_info WHERE app_id=?', (self.ids[0],))
        self.assertNotEqual(self.run_script('selected-readback.sh', ['before'], env).returncode, 0)

    def test_inverse_rejects_unowned_and_foreign_marker_before_writes(self):
        native, target, env = self.harness()
        original = self.dump(target)
        self.assertNotEqual(self.run_script('inverse.sh', ['--authorize', str(self.base / 'unowned')], env).returncode, 0)
        run = self.base / 'run'
        self.assertEqual(self.run_script('apply.sh', ['--authorize', str(run)], env).returncode, 0)
        marker = next(native.glob('marker-*'))
        marker.write_text('foreign\n')
        applied = self.dump(target)
        self.assertNotEqual(self.run_script('inverse.sh', ['--authorize', str(run)], env).returncode, 0)
        self.assertEqual(self.dump(target), applied)
        self.assertNotEqual(applied, original)
        self.assertFalse((run / 'inverse.complete').exists())

    def test_new_plan_identity_strict_types_and_private_before_mode(self):
        invalid = copy.deepcopy(self.before)
        invalid['tested_identity']['diagonal_inches'] = 55.0
        self.assertNotEqual(self.cli(invalid).returncode, 0)
        self.assertFalse(self.out.exists())

    def test_output_in_repo_and_wal_source_refused(self):
        output = ROOT / 'registry-test-should-not-exist'
        self.assertNotEqual(self.cli(output=output).returncode, 0)
        self.assertFalse(output.exists())
        Path(str(self.db) + '-wal').write_bytes(b'not-a-consistent-export')
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertFalse(self.out.exists())

    def harness(self):
        self.generate()
        native = self.base / 'native'
        native.mkdir()
        target = native / 'registry.db'
        shutil.copyfile(self.db, target)
        mapping = {m['path']: str(native / ('marker-' + str(i))) for i, m in enumerate(self.profile['condition_markers'])}
        for file in self.out.glob('*.sh'):
            text = file.read_text().replace('/opt/dbspace/.pkgmgr_parser.db', str(target))
            for old, new in mapping.items():
                text = text.replace(old, new)
            file.write_text(text)
            self.assertEqual(subprocess.run(['sh', '-n', str(file)], capture_output=True).returncode, 0)
        prefs = {p['key']: p['value'] for p in self.before['preferences']}
        (native / 'prefs.json').write_text(json.dumps(prefs))
        (native / 'conditions.json').write_text(json.dumps({u['unit']: mapping[u['ConditionPathExists'][0][1:]] for u in self.before['unit_conditions']}))
        bins = self.base / 'bin'; bins.mkdir()
        fake = '''#!/usr/bin/env python3
import json, os, pathlib, sys
root=pathlib.Path(os.environ['FAKE_NATIVE']); name=pathlib.Path(sys.argv[0]).name; a=sys.argv[1:]
if name=='id': print('0'); sys.exit(0)
if name=='systemctl':
 if a[0]=='cat':
  d=json.loads((root/'conditions.json').read_text()); print('[Unit]\\nConditionPathExists=!' + d[a[1]]); sys.exit(7 if os.environ.get('FAIL_CAT') else 0)
 if a[0]=='stop':
  if os.environ.get('FAIL_STOP'): sys.exit(8)
  with (root/'stops').open('a') as f: f.write(' '.join(a[1:])+'\\n')
  sys.exit(0)
 sys.exit(9)
p=root/'prefs.json'; d=json.loads(p.read_text())
if a[0]=='get':
 k=a[1]; print(k+', value = '+('True' if d[k] else 'False')+' (Boolean)'); sys.exit(0)
if a[0]=='set':
 k=a[-2]; d[k]=a[-1]=='1'; p.write_text(json.dumps(d))
 if os.environ.get('FAIL_SET')==k: sys.exit(7)
 sys.exit(0)
sys.exit(9)
'''
        for name in ('id', 'systemctl', 'vconftool'):
            p = bins / name; p.write_text(fake); p.chmod(0o700)
        env = {'PATH': str(bins) + os.pathsep + os.environ['PATH'], 'FAKE_NATIVE': str(native), 'HOME': str(self.base)}
        return native, target, env

    def run_script(self, name, args, env):
        return subprocess.run(['sh', str(self.out / name)] + args, env=env, capture_output=True, text=True)

    def test_real_generated_shell_apply_readback_inverse(self):
        native, target, env = self.harness()
        original = self.dump(target)
        run = self.base / 'run'
        denied = self.run_script('apply.sh', [str(run)], env)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse(run.exists())
        result = self.run_script('apply.sh', ['--authorize', str(run)], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((run / 'apply.complete').exists())
        self.assertTrue((run / 'before.db').is_file())
        self.assertEqual(self.run_script('selected-readback.sh', ['after'], env).returncode, 0)
        self.assertNotEqual(self.run_script('apply.sh', ['--authorize', str(run)], env).returncode, 0)
        result = self.run_script('inverse.sh', ['--authorize', str(run)], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dump(target), original)
        self.assertEqual(self.run_script('selected-readback.sh', ['before'], env).returncode, 0)
        self.assertFalse(any(native.glob('marker-*')))
        self.assertTrue((run / 'inverse.complete').exists())
        allowed = {u['unit'] for u in self.before['unit_conditions']}
        self.assertEqual(set((native / 'stops').read_text().split()), allowed)

    def test_setter_failure_no_false_success_partial_inverse(self):
        native, target, env = self.harness()
        original = self.dump(target)
        env['FAIL_SET'] = self.before['preferences'][1]['key']
        run = self.base / 'run'
        result = self.run_script('apply.sh', ['--authorize', str(run)], env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((run / 'apply.complete').exists())
        del env['FAIL_SET']
        result = self.run_script('inverse.sh', ['--authorize', str(run)], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dump(target), original)
        self.assertEqual(json.loads((native / 'prefs.json').read_text()), {p['key']: p['value'] for p in self.before['preferences']})


if __name__ == '__main__':
    unittest.main()
