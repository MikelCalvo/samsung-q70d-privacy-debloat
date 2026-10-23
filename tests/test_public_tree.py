"""Public-tree privacy and packaging checks, all fixtures synthetic."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'tools' / 'check_public_tree.py'


class PublicTree(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CHECKER.is_file(), 'public tree checker is not implemented')
        spec = importlib.util.spec_from_file_location('public_tree', CHECKER)
        if spec is None or spec.loader is None:
            self.fail('checker cannot be loaded')
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'README.md').write_text('# Example\nTV: 192.0.2.10\nController: 192.0.2.20\n')

    def issues(self):
        return self.mod.scan_tree(self.root)

    def test_documentation_addresses_are_allowed(self):
        self.assertEqual(self.issues(), [])

    def test_standard_limited_broadcast_is_not_personal_network_data(self):
        value = str(self.mod.ipaddress.IPv4Address(2**32 - 1))
        (self.root / 'README.md').write_text('Reject the standard limited broadcast: ' + value + '\n')
        self.assertEqual(self.issues(), [])

    def test_private_address_is_rejected_without_echoing_value(self):
        value = '.'.join(map(str, [192, 168, 7, 23]))
        (self.root / 'README.md').write_text('TV: ' + value + '\n')
        found = self.issues()
        self.assertTrue(any(x['kind'] == 'nonpublic_example_address' for x in found))
        self.assertNotIn(value, json.dumps(found))

    def test_credentials_are_rejected_without_echoing_value(self):
        value = 'ghp_' + 'x' * 36
        (self.root / 'README.md').write_text('credential ' + value + '\n')
        found = self.issues()
        self.assertTrue(any(x['kind'] == 'credential_material' for x in found))
        self.assertNotIn(value, json.dumps(found))

    def test_email_is_rejected_except_numeric_github_noreply(self):
        email = 'example-user' + '@' + 'private.invalid'
        (self.root / 'README.md').write_text(email + '\n')
        self.assertTrue(any(x['kind'] == 'personal_email' for x in self.issues()))
        (self.root / 'README.md').write_text('12345+publicuser@users.noreply.github.com\n')
        self.assertEqual(self.issues(), [])

    def test_private_capture_and_symlink_are_rejected_without_following(self):
        (self.root / 'private.db').write_bytes(b'not a real database')
        (self.root / 'linked.md').symlink_to('missing-target')
        found = self.issues()
        self.assertTrue(any(x['kind'] == 'private_or_binary_file' for x in found))
        self.assertTrue(any(x['kind'] == 'symlink_or_special_file' for x in found))

    def test_target_system_owner_path_is_not_a_personal_host_path(self):
        (self.root / 'README.md').write_text('/home/owner/share/tmp/sdk_tools\n')
        self.assertEqual(self.issues(), [])
        (self.root / 'README.md').write_text('/home/' + 'private-user/projects\n')
        self.assertTrue(any(x['kind'] == 'personal_host_path' for x in self.issues()))

    def test_checker_source_does_not_flag_its_own_detection_patterns(self):
        found = self.mod.scan_text(CHECKER.read_text(), 'checker-source')
        self.assertEqual(found, [])

    def test_cli_exit_and_sanitized_diagnostic(self):
        value = '.'.join(map(str, [10, 23, 45, 67]))
        (self.root / 'README.md').write_text(value + '\n')
        r = subprocess.run([sys.executable, '-B', str(CHECKER), '--root', str(self.root)], capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(value, r.stdout + r.stderr)
        self.assertIn('nonpublic_example_address', r.stdout)


if __name__ == '__main__':
    unittest.main()
