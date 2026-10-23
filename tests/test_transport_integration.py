"""Real registry generation/session serialization with synthetic native state only."""
import base64
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest

import test_registry as registry_tests

ROOT = Path(__file__).resolve().parents[1]


class TransportIntegrationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('transport_session', ROOT / 'tools/tv_session.py')
        assert spec is not None and spec.loader is not None
        self.session = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.session)
        self.registry = registry_tests.RegistryTests(methodName='runTest')
        self.registry.setUp()
        self.addCleanup(self.registry.doCleanups)
        self.base = self.registry.base
        self.execution = 0
        evidence = os.environ.get('TRANSPORT_EVIDENCE_DIR')
        self.evidence = Path(evidence) / self._testMethodName if evidence else None
        if self.evidence:
            self.evidence.mkdir(parents=True, exist_ok=False)
            self.addCleanup(shutil.copytree, self.base, self.evidence / 'fixture')

    def compose(self, name, args):
        # The session has no argv feature: prefix exact safely quoted positional
        # parameters, as documented, before the actual generator's shell bytes.
        self.execution += 1
        script = ('set -- ' + shlex.join(args) + '\n').encode() + (self.registry.out / name).read_bytes()
        if self.evidence:
            (self.evidence / (str(self.execution) + '-' + name + '.input')).write_bytes(script)
        return script

    def run_envelope(self, name, args, env):
        command = self.session.envelope(self.compose(name, args))
        self.assertLess(len(command.encode('ascii')), 60 * 1024)
        label = str(self.execution) + '-' + name
        if self.evidence:
            (self.evidence / (label + '.command')).write_text(command)
            (self.evidence / (label + '.env.json')).write_text(json.dumps(env))
            shutil.copytree(self.base / 'native', self.evidence / (label + '.before'))
        result = subprocess.run(['/bin/sh', '-c', command], env=env,
                                capture_output=True, text=True, timeout=30)
        if self.evidence:
            (self.evidence / (label + '.stdout')).write_text(result.stdout)
            (self.evidence / (label + '.stderr')).write_text(result.stderr)
            (self.evidence / (label + '.exit')).write_text(str(result.returncode))
            shutil.copytree(self.base / 'native', self.evidence / (label + '.after'))
        return result

    def test_actual_generated_registry_outputs_fit_session(self):
        self.registry.generate()
        run = self.base / "run with ' quote"
        for name, args in (('apply.sh', ['--authorize', str(run)]),
                           ('inverse.sh', ['--authorize', str(run)]),
                           ('selected-readback.sh', ['before'])):
            with self.subTest(script=name):
                script = self.compose(name, args)
                self.assertGreater(len(script), 32768)
                command = self.session.envelope(script)
                self.assertLess(len(command.encode('ascii')), 60 * 1024)
                encoded = command.split('printf %s ', 1)[1].split(' ', 1)[0]
                payload = base64.b64decode(encoded, validate=True)
                self.assertLessEqual(len(payload), 32768)
                self.assertEqual(gzip.decompress(payload), script)

    def test_registry_apply_readback_inverse_through_session(self):
        native, target, env = self.registry.harness()
        original = self.registry.dump(target)
        preferences = json.loads((native / 'prefs.json').read_text())
        run = self.base / "run with ' quote"
        for name, args in (('selected-readback.sh', ['before']),
                           ('apply.sh', ['--authorize', str(run)]),
                           ('selected-readback.sh', ['after']),
                           ('inverse.sh', ['--authorize', str(run)]),
                           ('selected-readback.sh', ['before'])):
            result = self.run_envelope(name, args, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            if name == 'apply.sh':
                self.assertTrue((run / 'apply.complete').is_file())
                self.assertTrue((run / 'before.db').is_file())
                self.assertNotEqual(self.registry.dump(target), original)
        self.assertEqual(self.registry.dump(target), original)
        self.assertEqual(json.loads((native / 'prefs.json').read_text()), preferences)
        self.assertFalse(any(native.glob('marker-*')))
        self.assertTrue((run / 'inverse.complete').is_file())
        allowed = {u['unit'] for u in self.registry.before['unit_conditions']}
        self.assertEqual(set((native / 'stops').read_text().split()), allowed)


if __name__ == '__main__':
    unittest.main()
