"""Offline public-main tests; only external upstream/metadata are faked."""
from __future__ import annotations

import base64
import contextlib
import gzip
import importlib.util
import random
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "tv_session.py"
PIN = "bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653"

# Synthetic external boundary, not a copy of upstream implementation.
FAKE_SDB = '''
class SdbClient:
    def capture(self, command, **kwargs):
        record("capture", command=command, kwargs=kwargs)
        if command == "/usr/bin/dotnet --list-runtimes":
            if MODE in ("fallback", "bad-link", "bad-list"):
                raise Error("SDK command failed: Unknown option --list-runtimes")
            if MODE == "other-error":
                raise Error("different failure")
        if command.startswith("readlink -f "):
            return "/usr/share/dotnet/shared/Microsoft.NETCore.App/" + ("7.0.0" if MODE == "bad-link" else "6.0.9")
        if command.startswith("ls "):
            return "6.0.9\\n" + ("garbage" if MODE == "bad-list" else "")
        return "ok"
'''
FAKE_AR = '''
import json, os
from pathlib import Path
from types import SimpleNamespace
from .sdb import SdbClient
class ArchiveRootError(RuntimeError): pass

def record(kind, **values):
    with open(os.environ["FAKE_TRACE"], "a") as f:
        f.write(json.dumps(dict(kind=kind, **values)) + "\\n")
MODE = os.environ.get("FAKE_MODE", "ok")
from . import sdb
sdb.record, sdb.MODE, sdb.Error = record, MODE, ArchiveRootError

def _capture(client, command, timeout=15):
    return client.capture(command, timeout=timeout)

def _cleanup(client, package):
    record("cleanup", package=package)
    return MODE != "cleanup-error"

class Connection:
    async def ping(self):
        return SimpleNamespace(uid=0, euid=0, gid=0, egid=0, effective_capabilities="ff", smack_label="User")
    async def execute(self, command, timeout):
        record("execute", command=command, timeout=timeout, sdb=os.environ.get("SDB"),
               common=os.environ.get("SAMSUNG_TV_ROOT_COMMON_PAYLOAD_DIRECTORY"))
        return SimpleNamespace(exit_code=9 if MODE == "exit-error" else 0,
                               timed_out=MODE == "command-timeout", stdout="private-canary", stderr="private-canary")
    async def shutdown(self): pass

class RootAgentServer:
    def __init__(self, bind_host, port, expected_peer, secret, *, require_root=True):
        record("server", bind_host=bind_host, port=port, expected_peer=expected_peer, require_root=require_root)
    async def accept(self, timeout): return Connection()
    async def close(self): record("close")

async def probe(host, **kwargs):
    record("probe", host=host, kwargs={k:v for k,v in kwargs.items() if k != "commands"})
    print("private-canary")
    if MODE == "hang":
        import time
        time.sleep(10)
    client = SdbClient()
    runtimes = _capture(client, "/usr/bin/dotnet --list-runtimes", 7)
    record("runtimes", value=runtimes)
    server = RootAgentServer(kwargs["bind_host"], 0, host, b"x" * 32, require_root=True)
    connection = await server.accept(2)
    await connection.ping()
    result = await connection.execute(kwargs["commands"][0], kwargs["command_timeout"])
    await connection.shutdown()
    await server.close()
    cleaned = _cleanup(client, "synthetic-package")
    if MODE == "raise-after-command":
        raise ArchiveRootError("private-canary")
    return dict(authenticated=MODE != "unauthenticated", uid=901 if MODE == "nonroot-result" else 0, euid=0, gid=0, egid=0, cap_eff="ff", smack="User",
                commands=[dict(command=kwargs["commands"][0], exit_code=result.exit_code,
                               timed_out=result.timed_out, stdout=result.stdout, stderr=result.stderr)],
                staging_cleaned=cleaned, system_files_unchanged=MODE != "hash-error")
'''


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TOOL.exists():
            spec = importlib.util.spec_from_file_location("tv_session_test_subject", TOOL)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)
        else:
            cls.module = None

    def setUp(self):
        self.assertIsNotNone(self.module, "public session main is not implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.upstream = self.home / "upstream"
        package = self.upstream / "src" / "samsung_tv_root"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "sdb.py").write_text(FAKE_SDB)
        (package / "archive_root.py").write_text(FAKE_AR)
        payloads = self.upstream / "payloads" / "common" / "out"
        payloads.mkdir(parents=True)
        for name in ("SamsungTvRootAgent.dll", "SamsungTvArchiveRoot.dll"):
            (payloads / name).write_bytes(b"synthetic-external-boundary")
        self.sdb = self.home / "sdb"
        self.sdb.write_text("#!/bin/sh\nexit 0\n")
        self.sdb.chmod(0o700)
        self.script = self.home / "script.sh"
        self.script.write_bytes(b"printf '%s\\n' 'backslash\\quote\"$value'\nexit 0\n")
        self.receipt = self.home / "receipt.json"
        self.trace = self.home / "trace.jsonl"
        self.git_calls = []
        self.git_rev = PIN
        self.git_dirty = False
        self.env = mock.patch.dict(os.environ, {"FAKE_TRACE": str(self.trace), "FAKE_MODE": "ok"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def args(self):
        return ["--upstream", str(self.upstream), "--host", "192.0.2.10", "--controller", "192.0.2.20",
                "--script", str(self.script), "--receipt", str(self.receipt), "--sdb", str(self.sdb),
                "--authorize-root-session"]

    def git(self, argv, **kwargs):
        self.git_calls.append((argv, kwargs))
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, self.git_rev + "\n", "")
        if "status" in argv:
            return subprocess.CompletedProcess(argv, 0, "?? src/extra.py\n" if self.git_dirty else "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def invoke(self, args=None, mode="ok"):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(self.module.subprocess, "run", side_effect=self.git), \
             mock.patch.dict(os.environ, {"FAKE_MODE": mode}), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(self.args() if args is None else args)
        self.assertNotIn("private-canary", stdout.getvalue() + stderr.getvalue())
        return code

    def events(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def test_success_exact_transport_and_private_receipt(self):
        self.assertEqual(self.invoke(), 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["root"]["commands"][0]["stdout"], "private-canary")
        commands = [e for e in self.events() if e["kind"] == "execute"]
        self.assertEqual(len(commands), 1)
        command = commands[0]["command"]
        self.assertNotIn("\\", command)
        self.assertNotIn("\n", command)
        encoded = command.split("printf %s ", 1)[1].split(" ", 1)[0]
        self.assertEqual(base64.b64decode(encoded), self.script.read_bytes())
        server = next(e for e in self.events() if e["kind"] == "server")
        self.assertEqual(server["port"], 38472)
        capture = next(e for e in self.events() if e["kind"] == "capture")
        self.assertEqual(capture["kwargs"]["port"], 38471)
        self.assertEqual(capture["kwargs"]["callback_host"], "192.0.2.20")
        self.assertTrue(any("status" in call[0] for call in self.git_calls))
        self.assertTrue(all(0 < call[1]["timeout"] <= 15 for call in self.git_calls))

    def test_exact_runtime_fallback(self):
        self.assertEqual(self.invoke(mode="fallback"), 0)
        events = self.events()
        runtime = next(e["value"] for e in events if e["kind"] == "runtimes")
        self.assertEqual(runtime, "Microsoft.NETCore.App 6.0.9 [/usr/share/dotnet/shared/Microsoft.NETCore.App]")
        self.assertEqual([e["command"] for e in events if e["kind"] == "capture"], [
            "/usr/bin/dotnet --list-runtimes", "readlink -f /usr/share/dotnet.tizen/netcoreapp",
            "ls /usr/share/dotnet/shared/Microsoft.NETCore.App/"])

    def test_other_runtime_errors_refuse(self):
        for mode in ("other-error", "bad-link", "bad-list"):
            with self.subTest(case=mode):
                self.receipt.unlink(missing_ok=True)
                self.trace.unlink(missing_ok=True)
                self.assertNotEqual(self.invoke(mode=mode), 0)
                self.assertFalse(any(e["kind"] == "execute" for e in self.events()))

    def test_command_exit_timeout_and_cleanup_refuse(self):
        for mode in ("exit-error", "command-timeout", "cleanup-error", "hash-error", "raise-after-command",
                     "unauthenticated", "nonroot-result"):
            with self.subTest(case=mode):
                self.receipt.unlink(missing_ok=True)
                self.trace.unlink(missing_ok=True)
                self.assertNotEqual(self.invoke(mode=mode), 0)
                receipt = json.loads(self.receipt.read_text())
                self.assertFalse(receipt["ok"])
                self.assertTrue(any(e["kind"] == "command" for e in receipt["observations"]))
                self.assertTrue(any(e["kind"] == "staging_cleanup" for e in receipt["observations"]))

    def test_grant_required_before_upstream_or_receipt(self):
        self.assertNotEqual(self.invoke(self.args()[:-1]), 0)
        self.assertEqual(len(self.git_calls), 0)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(len(self.events()), 0)

    def test_revision_and_source_clean_required(self):
        for changed in ("revision", "source"):
            self.git_rev = "0" * 40 if changed == "revision" else PIN
            self.git_dirty = changed == "source"
            self.assertNotEqual(self.invoke(), 0)
            self.assertEqual(len(self.events()), 0)
            self.receipt.unlink(missing_ok=True)

    def test_repo_receipt_and_symlink_refuse(self):
        for path in (ROOT / "never-created-private.json", self.home / "link" / "private.json"):
            if path.parent.name == "link":
                path.parent.symlink_to(ROOT, target_is_directory=True)
            args = self.args()
            args[args.index("--receipt") + 1] = str(path)
            self.assertNotEqual(self.invoke(args), 0)
            self.assertFalse(path.exists())
            self.assertEqual(len(self.events()), 0)

    def test_existing_receipt_not_overwritten(self):
        self.receipt.write_text("retain")
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(self.receipt.read_text(), "retain")
        self.assertEqual(len(self.events()), 0)

    def test_invalid_script_encoding_and_content_refuse(self):
        for content in (b"", b"echo hi\0", b"\xff\n"):
            with self.subTest(case=len(content)):
                self.script.write_bytes(content)
                self.assertNotEqual(self.invoke(), 0)
                self.assertEqual(len(self.events()), 0)
                self.assertFalse(self.receipt.exists())

    def test_missing_payloads_refuse_before_upstream(self):
        (self.upstream / "payloads/common/out/SamsungTvRootAgent.dll").unlink()
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(len(self.events()), 0)
        self.assertFalse(self.receipt.exists())

    def test_size_budget_and_timeout_inputs_refuse(self):
        self.script.write_bytes(b"x" * (128 * 1024 + 1))
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(len(self.events()), 0)
        self.script.write_text("exit 0\n")
        for value in ("nan", "inf", "0", "301"):
            self.receipt.unlink(missing_ok=True)
            self.assertNotEqual(self.invoke(self.args() + ["--command-timeout", value]), 0)
        self.assertEqual(len(self.events()), 0)

    def test_overall_wait_is_finite_and_cleanup_unknown_not_success(self):
        self.assertNotEqual(self.invoke(self.args() + ["--session-timeout", "0.2"], mode="hang"), 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertTrue(receipt["session_timed_out"])
        self.assertFalse(receipt["ok"])

    def test_ports_explicit_and_distinct(self):
        self.assertEqual(self.invoke(self.args() + ["--capture-port", "40001", "--agent-port", "40002"]), 0)
        self.assertEqual(next(e for e in self.events() if e["kind"] == "server")["port"], 40002)
        self.receipt.unlink()
        self.trace.unlink()
        self.assertNotEqual(self.invoke(self.args() + ["--capture-port", "40002", "--agent-port", "40002"]), 0)
        self.assertEqual(len(self.events()), 0)

    def test_generated_recognition_script_bytes_roundtrip(self):
        # Read-only cross-tool integration: invoke its actual offline generator,
        # never run the resulting device installer on this host.
        generated = self.home / "generated"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/recognition.py"),
                                 "--output", str(generated)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        generated_script = generated / "installer.sh"
        self.script.write_bytes(generated_script.read_bytes())
        self.assertEqual(self.invoke(), 0)
        command = next(e["command"] for e in self.events() if e["kind"] == "execute")
        encoded = command.split("printf %s ", 1)[1].split(" ", 1)[0]
        self.assertEqual(base64.b64decode(encoded), generated_script.read_bytes())

    def test_maximum_budget_executes_without_e2big(self):
        self.script.write_bytes(b"#" + b"x" * (32768 - 9) + b"\nexit 0\n")
        self.assertEqual(self.script.stat().st_size, 32768)
        self.assertEqual(self.invoke(), 0)
        command = next(e["command"] for e in self.events() if e["kind"] == "execute")
        result = subprocess.run(["/bin/sh", "-c", command], capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)

    def test_large_input_uses_deterministic_gzip_preserving_exact_bytes(self):
        script = b'#' + b'x' * (128 * 1024 - 60) + '\nprintf "%s\\n" "caf\u00e9\\\\quote\\\"$literal"\nexit 7\n'.encode()
        script += b'\n' * (128 * 1024 - len(script))
        self.assertEqual(len(script), 128 * 1024)
        command = self.module.envelope(script)
        self.assertEqual(command, self.module.envelope(script))
        encoded = command.split('printf %s ', 1)[1].split(' ', 1)[0]
        payload = base64.b64decode(encoded, validate=True)
        self.assertEqual(payload, gzip.compress(script, mtime=0))
        self.assertEqual(gzip.decompress(payload), script)
        self.assertLessEqual(len(payload), 32768)
        self.assertLess(len(command.encode('ascii')), 60 * 1024)
        result = subprocess.run(['/bin/sh', '-c', command], capture_output=True, timeout=3)
        expected = subprocess.run(['/bin/bash'], input=script, capture_output=True, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (expected.returncode, expected.stdout, expected.stderr))
        self.assertEqual(result.returncode, 7)

    def test_large_script_accepted_by_public_main(self):
        self.script.write_bytes(b'#' + b'x' * 50000 + b'\nexit 0\n')
        self.assertEqual(self.invoke(), 0)
        command = next(e['command'] for e in self.events() if e['kind'] == 'execute')
        encoded = command.split('printf %s ', 1)[1].split(' ', 1)[0]
        self.assertEqual(gzip.decompress(base64.b64decode(encoded)), self.script.read_bytes())

    def test_incompressible_wire_payload_refused_before_upstream(self):
        rng = random.Random(81)
        script = bytes(rng.randrange(32, 127) for _ in range(60000))
        self.assertGreater(len(gzip.compress(script, mtime=0)), 32768)
        self.script.write_bytes(script)
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(len(self.events()), 0)
        self.assertEqual(len(self.git_calls), 0)
        self.assertFalse(self.receipt.exists())

    def test_input_read_bounded_before_compression(self):
        stream = mock.mock_open(read_data=b'x' * (128 * 1024 + 1))
        args = self.module.parser().parse_args(self.args())
        with mock.patch.object(Path, 'open', stream), \
             mock.patch.object(gzip, 'compress', side_effect=AssertionError('must not compress oversized input')):
            with self.assertRaises(self.module.Refusal):
                self.module.preflight(args)
        stream().read.assert_called_once_with(128 * 1024 + 1)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(len(self.events()), 0)

    def test_missing_gzip_refuses_before_script_actions(self):
        script = b'#' + b'x' * 50000 + b'\nprintf action\n'
        command = self.module.envelope(script)
        empty = self.home / 'empty-path'; empty.mkdir()
        result = subprocess.run(['/bin/sh', '-c', command], env={'PATH': str(empty)},
                                capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')

    def test_corrupt_gzip_and_base64_cannot_report_success(self):
        script = b'#' + b'x' * 50000 + b'\nprintf action\nexit 0\n'
        command = self.module.envelope(script)
        encoded = command.split('printf %s ', 1)[1].split(' ', 1)[0]
        damaged = bytearray(base64.b64decode(encoded)); damaged[-8] ^= 1
        bad_gzip = command.replace(encoded, base64.b64encode(damaged).decode('ascii'))
        for corrupt in (bad_gzip, command.replace('/usr/bin/base64 -d', '/bin/false')):
            with self.subTest(decoder=corrupt == bad_gzip):
                result = subprocess.run(['/bin/sh', '-c', corrupt], capture_output=True, timeout=3)
                self.assertNotEqual(result.returncode, 0)

    def test_small_envelope_bytes_unchanged(self):
        script = b'printf unchanged\n'
        encoded = base64.b64encode(script).decode('ascii')
        self.assertEqual(self.module.envelope(script),
                         "/bin/bash -o pipefail -c 'printf %s " + encoded + " | /usr/bin/base64 -d | /bin/bash'")

    def test_environment_pinned_to_explicit_external_inputs(self):
        with mock.patch.dict(os.environ, {"SDB": "/invalid/inherited-sdb",
             "SAMSUNG_TV_ROOT_COMMON_PAYLOAD_DIRECTORY": "/invalid/inherited-payload"}):
            self.assertEqual(self.invoke(), 0)
        call = next(e for e in self.events() if e["kind"] == "execute")
        self.assertEqual(call["sdb"], str(self.sdb))
        self.assertEqual(call["common"], str(self.upstream / "payloads/common/out"))

    def test_import_and_help_have_no_operational_effects(self):
        self.assertEqual(self.invoke(["--help"]), 0)
        self.assertEqual(len(self.git_calls), 0)
        self.assertEqual(len(self.events()), 0)
        self.assertFalse(self.receipt.exists())

    def test_decoder_failure_cannot_report_success(self):
        self.assertEqual(self.invoke(), 0)
        command = next(e["command"] for e in self.events() if e["kind"] == "execute")
        result = subprocess.run(["/bin/sh", "-c", command.replace("/usr/bin/base64 -d", "/bin/false")],
                                capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)

    def test_envelope_executes_exact_shell_bytes_locally(self):
        self.script.write_bytes(b"printf '%s\\n' 'one\\two' 'dollar$quote\"'\nexit 7\n")
        self.assertEqual(self.invoke(), 0)
        command = next(e["command"] for e in self.events() if e["kind"] == "execute")
        result = subprocess.run(["/bin/sh", "-c", command], capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b'one\\two\ndollar$quote"\n')


if __name__ == "__main__":
    unittest.main()
