"""Synthetic offline integration: real envelope, shell, AWK, SQLite and files.

Only UID/GID/SMACK, systemctl and sleep are doubled. Native data paths are
literally relocated before hashes are computed. No device or network access.
"""
from contextlib import closing
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import registry, tv_session

IDS = ('com.samsung.tv.tvsensor-iot-service',
       'org.tizen.voice-app', 'org.tizen.voice-app-service', 'org.tizen.voice-client',
       'org.tizen.voice-onboarding', 'org.tizen.stt-client')
UNITS = ('wifi-presence.path', 'wifi-presence.service', 'remote-management.service',
         'remote-shop-care-hub.service')
MARKERS = ('/opt/usr/share/systemd/system/org.tizen.voice-app',
           '/opt/usr/share/systemd/system/org.tizen.voice-client')
OUTPUTS = {'app-apply.sh', 'app-inverse.sh', 'hook-install.sh', 'hook-inverse.sh',
           'block.sh', 'wrapper.awk', 'selected-readback.sh', 'apply.sql',
           'inverse.sql', 'previous.awk', 'manifest.json'}


def module():
    assert (ROOT/'tools/privacy_extension.py').is_file(), 'missing privacy extension API'
    return importlib.import_module('tools.privacy_extension')


class Extension(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory(prefix='privacy-extension-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'tv'
        self.bin = self.base/'bin'
        self.bin.mkdir()
        self.log = self.base/'calls'
        self.metadata = {
            '/opt': ('0:0:755', 'access="_"'),
            '/opt/usr': ('0:0:755', 'access="_"'),
            '/opt/usr/share': ('0:0:755', 'access="_"'),
            '/opt/etc': ('0:1051:777', 'access="System::Shared" transmute="TRUE"'),
            '/run/systemd': ('0:0:755', 'access="System::Run" transmute="TRUE"'),
            '/run/systemd/system': ('0:202:775', 'access="System::Run" transmute="TRUE"'),
        }
        for path in (*self.metadata, '/etc/systemd/system', '/usr/lib/systemd/system',
                     '/opt/dbspace', '/opt/usr/share/systemd/system', '/proc/sys/kernel/random'):
            (self.root/path.lstrip('/')).mkdir(parents=True, exist_ok=True)
        for path, (metadata, _) in self.metadata.items():
            self.path(path).chmod(int(metadata.rsplit(':', 1)[1], 8))
        self.path('/proc/sys/kernel/random/boot_id').write_text('synthetic-boot\n')
        self.meta = self.base/'metadata.json'
        self.meta.write_text(json.dumps(self.metadata))
        # Prior AWK is synthetic and proves ordering without running vendor stock.
        command = 'printf "prior\\n" >> '+str(self.log)
        self.previous = ('#!/usr/bin/awk -f\nBEGIN { if (system('+json.dumps(command)+') != 0) exit 9; exit 0 }\n').encode()
        self.hook.write_bytes(self.previous)
        self.hook.chmod(0o755)
        self.pins = {}
        for name in UNITS:
            data = (name+' synthetic unit\n').encode()
            self.path('/usr/lib/systemd/system/'+name).write_bytes(data)
            self.pins[name] = hashlib.sha256(data).hexdigest()
        self.before = {'schema_version': 1, 'tested_identity': registry.IDENTITY,
                       'markers': [{'path': p, 'state': 'absent'} for p in MARKERS],
                       'unit_conditions': [
                           {'unit': p.rsplit('/', 1)[1]+'.service',
                            'ConditionPathExists': ['!'+p, '/tmp/AFTER_PRODUCTION']}
                           for p in MARKERS]}
        self.rows = [dict(app_id=app, app_disable='false', app_onboot='true',
                          app_autorestart='true') for app in IDS]
        self.snapshot = self.base/'snapshot.db'
        con = sqlite3.connect(self.snapshot)
        con.execute('CREATE TABLE package_app_info(app_id TEXT, app_disable TEXT, app_onboot TEXT, app_autorestart TEXT, untouched TEXT)')
        for row in self.rows:
            con.execute('INSERT INTO package_app_info VALUES(?,?,?,?,?)',
                        tuple(row[k] for k in ('app_id',)+registry.FIELDS)+('keep',))
        for app in registry.IDS:
            con.execute('INSERT INTO package_app_info VALUES(?,?,?,?,?)', (app, 'true', 'false', 'false', 'prior'))
        for app in ('unrelated', 'com.samsung.tv.vif'):
            con.execute('INSERT INTO package_app_info VALUES(?,?,?,?,?)', (app, 'false', 'true', 'false', 'family'))
        con.commit(); con.close()
        self.db = self.path(registry.DB)
        self.db.write_bytes(self.snapshot.read_bytes())
        self.before_path = self.base/'before.json'
        self.before_path.write_text(json.dumps(self.before))
        self.prior_path = self.base/'previous.awk'
        self.prior_path.write_bytes(self.previous)
        fake = '''#!/bin/bash
printf '%s\\n' "$*" >> "$LOG"
case "$1" in
cat)
 case "$2" in
 org.tizen.voice-app.service) p=org.tizen.voice-app;;
 org.tizen.voice-client.service) p=org.tizen.voice-client;; *) exit 1;; esac
 printf 'ConditionPathExists=!%s/opt/usr/share/systemd/system/%s\\nConditionPathExists=/tmp/AFTER_PRODUCTION\\n' "$TVROOT" "$p";;
show)
 if test "${REVERSE:-0}" = 1; then
  printf 'MainPID=0\\nActiveState=inactive\\nLoadState=masked\\nId=%s\\n' "$2"
 else
  printf 'Id=%s\\nLoadState=masked\\nActiveState=inactive\\nMainPID=0\\n' "$2"
 fi
 test "${DUPLICATE:-0}" = 0 || printf 'MainPID=1\\n'
 test "${SHOW_FAIL:-0}" = 0;;
--no-block) test "$2" = stop && test "${STOP_FAIL:-0}" = 0;;
daemon-reload) test "${RELOAD_FAIL:-0}" = 0;;
*) exit 1;; esac
'''
        stat = '''#!/usr/bin/python3
import os,sys,json,subprocess
p=sys.argv[-1]; key=p.removeprefix(os.environ['TVROOT'])
m=json.load(open(os.environ['META'])).get(key)
f=sys.argv[2]
if f=='%u:%g:%a' and m: print(m[0]); sys.exit(0)
f=f.replace('%u','0').replace('%g','0')
sys.exit(subprocess.run(['/usr/bin/stat','-c',f,p]).returncode)
'''
        smack = '''#!/usr/bin/python3
import os,sys,json
p=sys.argv[-1]
if len(sys.argv)==2:
 m=json.load(open(os.environ['META'])).get(p.removeprefix(os.environ['TVROOT']))
 print(p+' '+(m[1] if m else 'access="_"'))
'''
        for name, text in {'systemctl': fake, 'stat': stat, 'chsmack': smack,
                           'sleep': '#!/bin/sh\nexit 0\n'}.items():
            p = self.bin/name; p.write_text(text); p.chmod(0o755)
        self.env = {'PATH': str(self.bin)+':/usr/bin:/bin', 'HOME': str(self.base),
                    'TVROOT': str(self.root), 'META': str(self.meta), 'LOG': str(self.log)}
        self.packet = self.m.render(self.rows, self.before, self.previous,
                                   previous_sha=hashlib.sha256(self.previous).hexdigest(),
                                   unit_pins=self.pins, transform=self.adapt)
        native = r'(?<![\w/.-])/(?:opt(?:/|\b)|run/systemd|etc/systemd|usr/lib/systemd|proc/sys/kernel/random)'
        # Optional private execution evidence; never enabled by the public suite.
        evidence = os.environ.get('PRIVACY_EXTENSION_EVIDENCE')
        if evidence:
            import shutil
            target = Path(evidence)/self.id()
            target.mkdir(mode=0o700)
            for name, text in self.packet.items(): (target/name).write_text(text)
            self.addCleanup(shutil.copytree, self.base, target/'fixture')
        for name, data in self.packet.items():
            if name != 'previous.awk':
                self.assertIsNone(re.search(native, data), 'unrelocated data path: '+name)

    def path(self, p): return self.root/p.lstrip('/')
    @property
    def hook(self): return self.path('/opt/etc/parseinfo.sh')
    @property
    def task(self): return self.path(self.m.D)

    def adapt(self, text):
        for prefix in ('/opt', '/run/systemd', '/etc/systemd', '/usr/lib/systemd', '/proc/sys/kernel/random'):
            text = text.replace(prefix, str(self.root)+prefix)
        return text.replace('PATH=/usr/bin:/bin', 'PATH='+str(self.bin)+':/usr/bin:/bin').replace(
            '"$(id -u)" = 0', '"$(id -u)" = '+str(os.getuid())).replace(
            'chown 0:0', 'chown '+str(os.getuid())+':'+str(os.getgid()))

    def runpart(self, name, *args, **env):
        import shlex
        script = ('set -- '+' '.join(shlex.quote(a) for a in args)+'\n'+self.packet[name]).encode()
        command = tv_session.envelope(script)
        return subprocess.run(['/bin/bash', '-c', command], capture_output=True,
                              env={**self.env, **env}, timeout=20)

    def success(self, name, *args):
        result = self.runpart(name, *args)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def installed(self): self.success('hook-install.sh', '--authorize')
    def applied(self): self.installed(); self.success('app-apply.sh', '--authorize')

    def dispatch(self, **env):
        return subprocess.run(['/usr/bin/awk', '-f', str(self.hook)], capture_output=True,
                              env={**self.env, **env}, timeout=20)

    def values(self):
        with closing(sqlite3.connect(self.db)) as con:
            return con.execute('SELECT * FROM package_app_info ORDER BY app_id').fetchall()

    def test_envelope_install_apps_awk_inverse_preserves_prior_and_unrelated(self):
        original = self.values()
        parents = {p: (self.path(p).stat().st_ino, self.path(p).stat().st_mode) for p in self.metadata}
        self.applied()
        self.assertNotIn('prior', self.log.read_text())
        self.assertEqual((self.task/'previous.awk').read_bytes(), self.previous)
        self.assertEqual((self.task/'app-inverse.sh').read_text(), self.packet['app-inverse.sh'])
        self.assertTrue((self.task/'apps/before.db').is_file())
        self.assertEqual(self.dispatch().returncode, 0)
        calls = self.log.read_text().splitlines()
        start = calls.index('prior')
        self.assertEqual(calls[start+1], 'daemon-reload')
        self.assertEqual([x for x in calls if x.startswith('--no-block')], ['--no-block stop '+n for n in UNITS])
        self.success('selected-readback.sh', 'after')
        masks = {p.name: p.lstat().st_ino for p in self.path('/run/systemd/system').iterdir()}
        self.assertEqual(set(masks), set(UNITS))
        self.assertEqual(self.dispatch().returncode, 0, 'owned same-boot reentry')
        manager_before = self.log.read_bytes()
        self.success('hook-inverse.sh', '--authorize')
        self.success('app-inverse.sh', '--authorize')
        self.assertEqual(manager_before, self.log.read_bytes(), 'inverse must not start/reload/unmask')
        self.assertEqual(self.values(), original)
        self.assertEqual(self.hook.read_bytes(), self.previous)
        self.assertEqual(masks, {p.name: p.lstat().st_ino for p in self.path('/run/systemd/system').iterdir()})
        self.assertEqual(parents, {p: (self.path(p).stat().st_ino, self.path(p).stat().st_mode) for p in self.metadata})
        self.assertNotEqual(self.runpart('hook-inverse.sh', '--authorize').returncode, 0)
        self.assertNotEqual(self.runpart('app-inverse.sh', '--authorize').returncode, 0)

    def test_installer_replay_and_prior_unit_marker_drift_refuse(self):
        for kind in ('prior', 'unit', 'marker'):
            with self.subTest(kind=kind):
                p = self.hook if kind == 'prior' else self.path('/usr/lib/systemd/system/'+UNITS[-1]) if kind == 'unit' else self.path(MARKERS[-1])
                old = p.read_bytes() if p.exists() else None
                p.write_bytes(b'foreign')
                self.assertNotEqual(self.runpart('hook-install.sh', '--authorize').returncode, 0)
                self.assertFalse(self.task.exists())
                if old is None: p.unlink()
                else: p.write_bytes(old)
        self.installed()
        hook = self.hook.read_bytes()
        self.assertNotEqual(self.runpart('hook-install.sh', '--authorize').returncode, 0)
        self.assertEqual(self.hook.read_bytes(), hook)

    def test_foreign_last_mask_prevalidated_before_first_mask(self):
        self.applied()
        foreign = self.path('/run/systemd/system/'+UNITS[-1]); foreign.symlink_to('/dev/null')
        result = self.dispatch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([p.name for p in foreign.parent.iterdir()], [UNITS[-1]])
        self.assertNotIn('daemon-reload', self.log.read_text())

    def test_runtime_failures_never_success_and_hook_inverse_retains_masks(self):
        self.applied()
        for env in ({'STOP_FAIL': '1'}, {'SHOW_FAIL': '1'}, {'DUPLICATE': '1'}):
            with self.subTest(env=env):
                self.assertNotEqual(self.dispatch(**env).returncode, 0)
                self.assertNotIn('success', (self.task/'boot-synthetic-boot.receipt').read_text())
        self.success('hook-inverse.sh', '--authorize')
        self.assertEqual(len(list(self.path('/run/systemd/system').iterdir())), 4)

    def test_app_sql_atomic_drift_refusal_and_field_specific_inverse(self):
        self.installed()
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('UPDATE package_app_info SET app_onboot=? WHERE app_id=?', ('false', IDS[-1]))
            con.commit()
        before = self.values()
        self.assertNotEqual(self.runpart('app-apply.sh', '--authorize').returncode, 0)
        self.assertEqual(self.values(), before)
        self.assertFalse((self.task/'apps').exists())
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('UPDATE package_app_info SET app_onboot=? WHERE app_id=?', ('true', IDS[-1]))
            con.commit()
        self.success('app-apply.sh', '--authorize')
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('UPDATE package_app_info SET untouched=? WHERE app_id=?', ('changed independently', IDS[0]))
            con.commit()
        self.success('app-inverse.sh', '--authorize')
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('SELECT untouched FROM package_app_info WHERE app_id=?', (IDS[0],)).fetchone()[0], 'changed independently')

    def test_partial_app_marker_failure_explicit_inverse_and_no_apply_replay(self):
        self.installed()
        # A real write failure after SQLite commit; no fake sqlite response.
        p = self.bin/'chsmack'
        p.write_text(p.read_text()+'\nif len(sys.argv)>2 and sys.argv[-1].endswith("org.tizen.voice-client"):\n sys.exit(7)\n')
        self.assertNotEqual(self.runpart('app-apply.sh', '--authorize').returncode, 0)
        self.assertTrue((self.task/'apps/registry.intent').is_file())
        self.assertFalse((self.task/'apps/apply.complete').exists())
        self.assertNotEqual(self.runpart('app-apply.sh', '--authorize').returncode, 0)
        self.success('app-inverse.sh', '--authorize')
        self.assertTrue(all(not self.path(p).exists() for p in MARKERS))
        self.assertEqual(self.db_rows_flags(), [tuple(r[k] for k in registry.FIELDS) for r in self.rows])

    def db_rows_flags(self):
        with closing(sqlite3.connect(self.db)) as con:
            return [con.execute('SELECT app_disable,app_onboot,app_autorestart FROM package_app_info WHERE app_id=?', (a,)).fetchone() for a in IDS]

    def test_inverse_refuses_foreign_marker_and_changed_hook(self):
        self.applied()
        self.path(MARKERS[-1]).write_text('foreign\n')
        state = self.values()
        self.assertNotEqual(self.runpart('app-inverse.sh', '--authorize').returncode, 0)
        self.assertEqual(self.values(), state)
        self.hook.write_text('foreign\n')
        self.assertNotEqual(self.runpart('hook-inverse.sh', '--authorize').returncode, 0)
        self.assertEqual(self.hook.read_text(), 'foreign\n')

    def test_snapshot_and_before_validation_no_registry_global_mutation(self):
        rows, digest = self.m.read_snapshot(self.snapshot)
        self.assertEqual(rows, self.rows)
        self.assertEqual(digest, hashlib.sha256(self.snapshot.read_bytes()).hexdigest())
        self.assertEqual(len(registry.IDS), 23)
        self.m.validate_before(self.before)
        for bad in ({**self.before, 'extra': 1},
                    {**self.before, 'markers': [{'path': p, 'state': 'present'} for p in MARKERS]}):
            with self.assertRaises(ValueError): self.m.validate_before(bad)
        bad = copy.deepcopy(self.before)
        bad['unit_conditions'][0]['ConditionPathExists'] = ['/tmp/AFTER_PRODUCTION']
        with self.assertRaises(ValueError): self.m.validate_before(bad)
        (self.base/'snapshot.db-wal').touch()
        with self.assertRaises(ValueError): self.m.read_snapshot(self.snapshot)

    def test_installer_registry_preflight_before_native_intent(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('UPDATE package_app_info SET app_onboot=? WHERE app_id=?', ('false', IDS[-1]))
            con.commit()
        hook = self.hook.read_bytes()
        self.assertNotEqual(self.runpart('hook-install.sh', '--authorize').returncode, 0)
        self.assertFalse(self.task.exists(), 'registry drift must precede install intent')
        self.assertEqual(self.hook.read_bytes(), hook)

    def test_readback_verifies_hook_pin_and_four_runtime_unit_states(self):
        self.applied()
        self.assertEqual(self.dispatch().returncode, 0)
        self.success('selected-readback.sh', 'after')
        result = self.runpart('selected-readback.sh', 'after', REVERSE='1')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotEqual(self.runpart('selected-readback.sh', 'after', SHOW_FAIL='1').returncode, 0)
        self.hook.write_text('foreign\n')
        self.assertNotEqual(self.runpart('selected-readback.sh', 'after').returncode, 0)

    def test_installer_preserves_before_database_before_hook_swap(self):
        original = self.db.read_bytes()
        self.installed()
        self.assertTrue((self.task/'before.db').is_file())
        with closing(sqlite3.connect(self.task/'before.db')) as con:
            self.assertEqual(con.execute('PRAGMA quick_check').fetchall(), [('ok',)])
            self.assertEqual(con.execute('SELECT count(*) FROM package_app_info').fetchone()[0], 31)
        self.assertEqual(self.db.read_bytes(), original)

    def test_owned_mask_replacement_and_lock_cleanup_fail_closed(self):
        self.applied()
        self.assertEqual(self.dispatch().returncode, 0)
        p = self.path('/run/systemd/system/'+UNITS[-1])
        saved = p.with_name(p.name+'.old'); p.rename(saved); p.symlink_to('/dev/null')
        self.assertNotEqual(self.dispatch().returncode, 0)
        p.unlink(); saved.rename(p)
        tool = self.bin/'rmdir'; tool.write_text('#!/bin/sh\nexit 1\n'); tool.chmod(0o755)
        self.assertNotEqual(self.dispatch().returncode, 0)
        self.assertNotIn('success', (self.task/'boot-synthetic-boot.receipt').read_text())
        self.assertTrue((self.task/'boot-synthetic-boot/lock').is_dir())

    def test_native_pins_required_generate_no_outputs_for_synthetic_prior(self):
        out = self.base/'private-output'
        with self.assertRaises(ValueError):
            self.m.generate(self.snapshot, self.before_path, self.prior_path, out)
        self.assertFalse(out.exists())
        self.assertEqual(self.m.PREVIOUS_SHA, 'c9a3ea4dbdbcf06a262dcc6f7c87f71f6a15cb31ce554ab5e029dff0cdb10e40')
        self.assertEqual(set(self.m.PINS), set(UNITS))
        with self.assertRaises(ValueError):
            self.m.render(self.rows, self.before, self.previous)
        with self.assertRaises(ValueError):
            self.m.render(self.rows, self.before, self.previous, previous_sha=hashlib.sha256(self.previous).hexdigest(), unit_pins={})

    def test_import_has_no_file_network_or_process_io(self):
        code = '''import sys
sys.path.insert(0,sys.argv[1])
from tools import registry,recognition
source=open(sys.argv[2]).read()
compiled=compile(source,sys.argv[2],'exec')
def deny(event,args):
 if event=='open' or event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn'}:
  raise RuntimeError('import attempted IO')
sys.addaudithook(deny)
exec(compiled,{'__name__':'tools.privacy_extension','__package__':'tools','__file__':sys.argv[2]})
'''
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT), str(ROOT/'tools/privacy_extension.py')],
                                capture_output=True, env={'PATH': '/usr/bin:/bin'}, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_cli_refuses_synthetic_prior_and_requires_all_explicit_inputs(self):
        out = self.base/'cli-output'
        command = [sys.executable, '-B', str(ROOT/'tools/privacy_extension.py'), '--snapshot', str(self.snapshot),
                   '--before', str(self.before_path), '--previous-hook', str(self.prior_path), '--output', str(out)]
        result = subprocess.run(command, capture_output=True, env={'PATH': '/usr/bin:/bin'}, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(out.exists())
        result = subprocess.run(command[:3], capture_output=True, env={'PATH': '/usr/bin:/bin'}, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.m.IDS, IDS)
        self.assertEqual(self.m.PINS, {
            'wifi-presence.service': 'a2f4f11950f547507675522bd92a90b2a56902906b66fd54a262a1a967baf2e7',
            'wifi-presence.path': '03caae12e4fe516057da6d919d7e987953c991c5ad5add19e2a73697652bcd34',
            'remote-management.service': '20a53a5c7f2a53185e228f622e980d90fb4ea71220909fa0c3296e38172cfabd',
            'remote-shop-care-hub.service': 'e9a53a363a9d5a7e725ac25d8ef07b01cd409a3a507dad39d7859203a6e03302'})

    def path_without_pid(self):
        """Model the captured Tizen .path without service-only MainPID."""
        p = self.bin/'systemctl'
        s = p.read_text()
        old = "  printf 'Id=%s\\nLoadState=masked\\nActiveState=inactive\\nMainPID=0\\n' \"$2\""
        new = "  printf 'Id=%s\\nLoadState=masked\\nActiveState=inactive\\n' \"$2\"; test \"$2\" = wifi-presence.path || printf 'MainPID=0\\n'"
        self.assertEqual(s.count(old), 1)
        s = s.replace(old, new)
        p.write_text(s)
        self.assertIn('test "$2" = wifi-presence.path', s)

    def test_path_unit_absent_pid_runtime_and_readback(self):
        self.path_without_pid()
        self.applied()
        result = self.dispatch()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.success('selected-readback.sh', 'after')
        receipt = self.task/'boot-synthetic-boot.receipt'
        self.assertEqual(receipt.read_text(), 'status=success masked=4 inactive=4 service_MainPID0=3\n')
        # The exception applies only to the single pinned .path unit.
        p = self.bin/'systemctl'
        p.write_text(p.read_text().replace('test "$2" = wifi-presence.path',
                                         'test "$2" = wifi-presence.service'))
        self.assertNotEqual(self.runpart('selected-readback.sh', 'after').returncode, 0)
        self.assertNotEqual(self.dispatch().returncode, 0)

    def install_smack_model(self, failure=''):
        """Unknown new inodes inherit User until explicitly relabeled."""
        labels = self.base/'smack-labels.json'
        labels.write_text(json.dumps({str(self.hook): '_',
                                     str(self.path('/opt/usr/share/systemd/system')): '_'}))
        text = '''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=sys.argv[-1]
store=Path(os.environ['SMACK_STORE'])
labels=json.loads(store.read_text())
if len(sys.argv)>2:
 if os.environ.get('SMACK_FAIL_BASENAME')==Path(p).name:
  sys.exit(9)
 labels[p]=sys.argv[2]
 store.write_text(json.dumps(labels))
else:
 meta=json.load(open(os.environ['META'])).get(p.removeprefix(os.environ['TVROOT']))
 label=labels.get(p)
 if label is None and meta:
  print(p+' '+meta[1])
 else:
  print(p+' access="'+(label or 'User')+'"')
'''
        (self.bin/'chsmack').write_text(text)
        self.env.update(SMACK_STORE=str(labels), SMACK_FAIL_BASENAME=failure)
        return labels

    def test_receipts_explicit_smack_for_user_creator_and_both_inverses(self):
        labels = self.install_smack_model()
        original = self.values()
        self.applied()
        self.assertEqual(self.dispatch().returncode, 0)
        self.success('selected-readback.sh', 'after')
        self.success('hook-inverse.sh', '--authorize')
        self.success('app-inverse.sh', '--authorize')
        self.assertEqual(self.values(), original)
        recorded = json.loads(labels.read_text())
        for p in (self.task/'intent', self.task/'installed', self.task/'restored',
                  self.task/'apps/plan.bound', self.task/'apps/inverse.complete'):
            self.assertEqual(recorded.get(str(p)), '_', p.name)

    def test_receipt_label_failure_stops_before_hook_swap(self):
        self.install_smack_model('intent')
        before = self.hook.read_bytes()
        self.assertNotEqual(self.runpart('hook-install.sh', '--authorize').returncode, 0)
        self.assertEqual(self.hook.read_bytes(), before)
        self.assertFalse((self.task/'installed').exists())

    def test_receipt_label_failure_stops_before_registry_mutation(self):
        self.install_smack_model('plan.bound')
        self.installed()
        before = self.values()
        self.assertNotEqual(self.runpart('app-apply.sh', '--authorize').returncode, 0)
        self.assertEqual(self.values(), before)
        self.assertFalse((self.task/'apps/registry.intent').exists())

    def test_offline_emit_exclusive_private_complete_and_envelope_budgets(self):
        out = self.base/'output'
        manifest = self.m.emit(self.packet, self.rows, self.before, '0'*64, out)
        self.assertEqual({p.name for p in out.iterdir()}, OUTPUTS)
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        for name, entry in manifest['files'].items():
            data = (out/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            self.assertEqual((out/name).stat().st_mode & 0o777, 0o600)
            if name.endswith('.sh'):
                self.assertLess(len(tv_session.envelope(b'set -- --authorize\n'+data).encode()), 60*1024)
                result = subprocess.run(['/bin/sh', '-n', str(out/name)], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
        frozen = {p.name: p.read_bytes() for p in out.iterdir()}
        with self.assertRaises(ValueError): self.m.emit(self.packet, self.rows, self.before, '0'*64, out)
        self.assertEqual(frozen, {p.name: p.read_bytes() for p in out.iterdir()})
        with self.assertRaises(ValueError): self.m.emit(self.packet, self.rows, self.before, '0'*64, ROOT/'must-not-create-extension')


if __name__ == '__main__':
    unittest.main()
