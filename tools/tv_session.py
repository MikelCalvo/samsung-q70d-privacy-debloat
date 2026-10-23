#!/usr/bin/env python3
"""Explicit one-shot owner root transport using an external pinned dependency.

MIT. No upstream code or Samsung files are bundled. Importing this module does
not load the dependency, create listeners, or contact a device.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import datetime
import gzip
import hashlib
import importlib
import ipaddress
import json
import math
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

UPSTREAM_COMMIT = "bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653"
MAX_SCRIPT_BYTES = 128 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024
REPOSITORY = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORY = "/usr/share/dotnet/shared/Microsoft.NETCore.App"
RUNTIME_LINK_COMMAND = "readlink -f /usr/share/dotnet.tizen/netcoreapp"
RUNTIME_LIST_COMMAND = "ls " + RUNTIME_DIRECTORY + "/"
SYSTEM_HASH_COMMAND = "sha256sum /etc/passwd /usr/share/sdbd/public.pem"


class Refusal(Exception):
    """Local admission failure; details are never printed to public output."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse otherwise echoes arbitrary user values, possibly secrets.
        raise Refusal("invalid arguments")


def parser():
    result = SafeParser(description="One explicit pinned-upstream root session; raw output is private.")
    result.add_argument("--upstream", type=Path, required=True)
    result.add_argument("--host", required=True, help="TV IPv4 address")
    result.add_argument("--controller", required=True, help="reachable local controller IPv4 address")
    result.add_argument("--script", type=Path, required=True, help="authorized UTF-8 shell script (max 131072 bytes; 32768-byte payload budget)")
    result.add_argument("--receipt", type=Path, required=True, help="new private JSON file outside this repository")
    result.add_argument("--sdb", type=Path, required=True, help="external Tizen Studio sdb executable")
    result.add_argument("--authorize-root-session", action="store_true", help="authorize root acquisition AND the supplied script")
    result.add_argument("--capture-port", type=int, default=38471)
    result.add_argument("--agent-port", type=int, default=38472)
    result.add_argument("--sdb-timeout", type=float, default=8.0)
    result.add_argument("--accept-timeout", type=float, default=20.0)
    result.add_argument("--command-timeout", type=float, default=30.0)
    result.add_argument("--session-timeout", type=float, default=240.0, help="whole worker deadline, including cleanup (max 900s)")
    return result


def envelope(script):
    """No script quotes/backslashes pass through the upstream C# argv parser."""
    if not 1 <= len(script) <= MAX_SCRIPT_BYTES or b"\0" in script:
        raise Refusal("script size or NUL")
    script.decode("utf-8")
    compressed = len(script) > MAX_PAYLOAD_BYTES
    payload = gzip.compress(script, mtime=0) if compressed else script
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise Refusal("payload size")
    encoded = base64.b64encode(payload).decode("ascii")
    # Preserve the original small-script envelope byte-for-byte. Larger scripts
    # use one deterministic gzip member, never uploads, chunks or extra EXECs.
    # Only fixed ASCII and base64 reach ProcessStartInfo.Arguments. The bounded
    # payload expands to under 44 KiB, below the agent's 64 KiB EXEC limit.
    # Refuse missing gzip before starting Bash/script actions; pipefail also
    # propagates base64, gzip and script errors (not atomic decode validation).
    guard = "command -v gzip >/dev/null 2>&1 || exit 127; " if compressed else ""
    decoder = " | gzip -d -c" if compressed else ""
    command = "/bin/bash -o pipefail -c '" + guard + "printf %s " + encoded + " | /usr/bin/base64 -d" + decoder + " | /bin/bash'"
    if len(command.encode("ascii")) >= 60 * 1024:
        raise Refusal("envelope size")
    return command


def preflight(args):
    if not args.authorize_root_session:
        raise Refusal("root not authorized")
    if sys.platform != "linux" or sys.version_info < (3, 11):
        raise Refusal("Linux Python 3.11+ required")
    for value in (args.host, args.controller):
        address = ipaddress.IPv4Address(value)
        if address.is_unspecified or address.is_multicast or str(address) == "255.255.255.255":
            raise Refusal("invalid endpoint")
    if args.host == args.controller:
        raise Refusal("endpoints must differ")
    for port in (args.capture_port, args.agent_port):
        if not 1024 <= port <= 65535:
            raise Refusal("unprivileged callback ports required")
    if args.capture_port == args.agent_port:
        raise Refusal("callback ports must differ")
    for value, maximum in ((args.sdb_timeout, 60), (args.accept_timeout, 120),
                           (args.command_timeout, 300), (args.session_timeout, 900)):
        if not math.isfinite(value) or not 0.1 <= value <= maximum:
            raise Refusal("invalid timeout")
    args.upstream = args.upstream.expanduser().resolve(strict=True)
    args.sdb = args.sdb.expanduser().resolve(strict=True)
    if not args.sdb.is_file() or not os.access(args.sdb, os.X_OK):
        raise Refusal("sdb executable required")
    if not args.script.is_file():
        raise Refusal("regular script required")
    with args.script.open("rb") as stream:
        script = stream.read(MAX_SCRIPT_BYTES + 1)
    command = envelope(script)
    receipt = args.receipt.expanduser().resolve()
    if receipt == REPOSITORY or receipt.is_relative_to(REPOSITORY):
        raise Refusal("receipt inside repository")
    if not receipt.parent.is_dir():
        raise Refusal("receipt parent must already exist")
    if receipt.exists() or args.receipt.is_symlink():
        raise Refusal("receipt must be new")
    # No import before validating the exact source tree. Include ignored files:
    # an ignored Python overlay or cached bytecode is not a clean source tree.
    checks = ((["rev-parse", "HEAD"], UPSTREAM_COMMIT),
              (["status", "--porcelain=v1", "--untracked-files=all", "--ignored", "--", "src"], ""),
              (["diff", "--exit-code", "HEAD", "--", "payloads/common", "Makefile"], ""))
    for command_args, expected in checks:
        result = subprocess.run(["git", "--no-optional-locks", "-C", str(args.upstream), *command_args],
                                capture_output=True, text=True, timeout=10, check=False)
        if result.returncode or result.stdout.strip() != expected:
            raise Refusal("upstream revision or source mismatch")
    source = args.upstream / "src" / "samsung_tv_root"
    for name in ("archive_root.py", "sdb.py", "__init__.py"):
        if not (source / name).is_file() or (source / name).is_symlink():
            raise Refusal("source files missing")
    payloads = args.upstream / "payloads" / "common" / "out"
    for name in ("SamsungTvRootAgent.dll", "SamsungTvArchiveRoot.dll"):
        if not (payloads / name).is_file():
            raise Refusal("build external common-payload first")
    return receipt, script, command


def _child(args, command, directory):
    """Isolated, bounded by the parent; never emits raw output to its terminal."""
    os.setsid()
    os.umask(0o077)
    sys.dont_write_bytecode = True
    # SIGTERM normally terminates only this owned worker/group. Python finally
    # blocks cannot be promised after hard deadline; journal preserves unknowns.
    directory = Path(directory)
    journal = directory / "journal.jsonl"

    def record(kind, **values):
        with journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(kind=kind, **values), ensure_ascii=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    with (directory / "raw.log").open("w", encoding="utf-8") as raw:
        # fd redirection also catches imported native/subprocess diagnostics.
        raw.flush()
        os.dup2(raw.fileno(), 1)
        os.dup2(raw.fileno(), 2)
        with contextlib.redirect_stdout(raw), contextlib.redirect_stderr(raw):
            try:
                if any(name == "samsung_tv_root" or name.startswith("samsung_tv_root.") for name in sys.modules):
                    raise Refusal("upstream was already imported")
                sys.path.insert(0, str(args.upstream / "src"))
                ar = importlib.import_module("samsung_tv_root.archive_root")
                sdb = importlib.import_module("samsung_tv_root.sdb")
                for module in (ar, sdb):
                    if not Path(module.__file__).resolve().is_relative_to(args.upstream / "src"):
                        raise Refusal("upstream import escaped pinned source")
                os.environ["SDB"] = str(args.sdb)
                # Ignore inherited payload overrides and use this checkout only.
                os.environ["SAMSUNG_TV_ROOT_COMMON_PAYLOAD_DIRECTORY"] = str(args.upstream / "payloads/common/out")
                os.environ["SAMSUNG_TV_ROOT_COMMON31_PAYLOAD_DIRECTORY"] = str(args.upstream / "payloads/common31/out")
                original_capture = sdb.SdbClient.capture
                original_archive_capture = ar._capture
                original_server = ar.RootAgentServer
                original_cleanup = ar._cleanup
                lock = threading.RLock()
                hashes = []

                def capture(client, text, *, callback_host=None, bind_host=None, port=0,
                            timeout=30.0, on_listening=None):
                    # The launch capture and failure log can overlap. Serializing
                    # allows one fixed port rather than an arbitrary callback.
                    with lock:
                        return original_capture(client, text, callback_host=args.controller,
                                                bind_host=args.controller, port=args.capture_port,
                                                timeout=timeout, on_listening=on_listening)

                def archive_capture(client, text, timeout=15.0):
                    try:
                        value = original_archive_capture(client, text, timeout)
                    except ar.ArchiveRootError as error:
                        if text != "/usr/bin/dotnet --list-runtimes" or "Unknown option --list-runtimes" not in str(error):
                            raise
                        resolved = original_archive_capture(client, RUNTIME_LINK_COMMAND, timeout)
                        if resolved != RUNTIME_DIRECTORY + "/6.0.9":
                            raise ar.ArchiveRootError("runtime link mismatch")
                        versions = original_archive_capture(client, RUNTIME_LIST_COMMAND, timeout).splitlines()
                        # The fallback is intentionally narrower than upstream's
                        # normal runtime selection: only the observed 6.0.9 link.
                        import re
                        if "6.0.9" not in versions or any(not re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions):
                            raise ar.ArchiveRootError("unexpected runtime listing")
                        record("runtime_fallback", version="6.0.9")
                        value = "\n".join("Microsoft.NETCore.App " + v + " [" + RUNTIME_DIRECTORY + "]" for v in versions)
                    if text == SYSTEM_HASH_COMMAND:
                        hashes.append(value)
                        if len(hashes) >= 2:
                            record("system_files", unchanged=hashes[-1] == hashes[0])
                    return value

                def cleanup(client, package):
                    try:
                        value = original_cleanup(client, package)
                    except BaseException as error:
                        record("staging_cleanup", cleaned=False, error_type=type(error).__name__, error=str(error))
                        raise
                    record("staging_cleanup", cleaned=value)
                    return value

                class ObservedConnection:
                    def __init__(self, connection):
                        self.connection = connection

                    async def ping(self, *values, **options):
                        identity = await self.connection.ping(*values, **options)
                        record("identity", uid=identity.uid, euid=identity.euid, gid=identity.gid, egid=identity.egid,
                               cap_eff=identity.effective_capabilities, smack=identity.smack_label)
                        return identity

                    async def execute(self, text, timeout):
                        record("command_started", command=text)
                        result = await self.connection.execute(text, timeout)
                        record("command", command=text, exit_code=result.exit_code, timed_out=result.timed_out,
                               stdout=result.stdout, stderr=result.stderr)
                        return result

                    async def shutdown(self, *values, **options):
                        try:
                            result = await self.connection.shutdown(*values, **options)
                        except BaseException as error:
                            record("shutdown", acknowledged=False, error_type=type(error).__name__, error=str(error))
                            raise
                        record("shutdown", acknowledged=True)
                        return result

                class FixedServer(original_server):
                    def __init__(self, bind_host, port, expected_peer, secret, *, require_root=True):
                        if bind_host != args.controller or expected_peer != args.host or port != 0 or require_root is not True:
                            raise Refusal("unexpected callback configuration")
                        super().__init__(args.controller, args.agent_port, args.host, secret, require_root=True)

                    async def accept(self, *values, **options):
                        return ObservedConnection(await super().accept(*values, **options))

                    async def close(self):
                        try:
                            result = await super().close()
                        except BaseException as error:
                            record("server_close", closed=False, error_type=type(error).__name__, error=str(error))
                            raise
                        record("server_close", closed=True)
                        return result

                sdb.SdbClient.capture = capture
                ar.RootAgentServer = FixedServer
                ar._capture = archive_capture
                ar._cleanup = cleanup
                root = asyncio.run(ar.probe(args.host, callback_host=args.controller, bind_host=args.controller,
                                            sdb_timeout=args.sdb_timeout, accept_timeout=args.accept_timeout,
                                            command_timeout=args.command_timeout, commands=(command,)))
                record("root_result", result=root)
            except BaseException as error:
                record("error", error_type=type(error).__name__, error=str(error))


def stop_worker(worker):
    """Kill only the worker we created, never a shared/global SDB server."""
    if not worker.is_alive():
        return
    try:
        if os.getpgid(worker.pid) == worker.pid:
            os.killpg(worker.pid, signal.SIGTERM)
        else:
            worker.terminate()
    except ProcessLookupError:
        pass
    worker.join(1)
    if worker.is_alive():
        try:
            if os.getpgid(worker.pid) == worker.pid:
                os.killpg(worker.pid, signal.SIGKILL)
            else:
                worker.kill()
        except ProcessLookupError:
            pass
        worker.join(1)


def collect(directory, receipt):
    journal = directory / "journal.jsonl"
    observations = []
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:
                observations.append(json.loads(line))
            except json.JSONDecodeError:
                receipt["journal_incomplete"] = True
    receipt["observations"] = observations
    log = directory / "raw.log"
    receipt["upstream_log"] = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    root = next((item["result"] for item in observations if item["kind"] == "root_result"), None)
    receipt["root"] = root
    # These are observations of the upstream calls, not independent device
    # probes. Absence means unknown, never successful cleanup.
    cleanup = {"staging_cleaned": None, "system_files_unchanged": None,
               "shutdown_acknowledged": None, "server_closed": None}
    for item in observations:
        if item["kind"] == "staging_cleanup":
            cleanup["staging_cleaned"] = item["cleaned"]
        elif item["kind"] == "system_files":
            cleanup["system_files_unchanged"] = item["unchanged"]
        elif item["kind"] == "shutdown":
            cleanup["shutdown_acknowledged"] = item["acknowledged"]
        elif item["kind"] == "server_close":
            cleanup["server_closed"] = item["closed"]
    if isinstance(root, dict):
        for key in ("staging_cleaned", "system_files_unchanged"):
            cleanup[key] = root.get(key)
    receipt["cleanup"] = cleanup
    commands = root.get("commands", []) if isinstance(root, dict) else []
    valid_root = isinstance(root, dict) and root.get("authenticated") is True and all(
        type(root.get(key)) is int and root[key] == 0 for key in ("uid", "euid", "gid", "egid"))
    valid_commands = isinstance(commands, list) and len(commands) == 1 and all(
        isinstance(item, dict) and type(item.get("exit_code")) is int and item["exit_code"] == 0
        and item.get("timed_out") is False for item in commands)
    receipt["ok"] = bool(valid_root and valid_commands and all(value is True for value in cleanup.values())
                         and not receipt.get("session_timed_out") and receipt.get("worker_exit") == 0
                         and not receipt.get("journal_incomplete")
                         and not any(item["kind"] == "error" for item in observations))


def main(argv=None):
    output = None
    worker = None
    receipt = {"schema": 1, "source_commit": UPSTREAM_COMMIT, "ok": False,
               "session_timed_out": False, "started_utc": datetime.datetime.now(datetime.UTC).isoformat()}
    try:
        args = parser().parse_args(argv)
        destination, script, command = preflight(args)
        # Reserve the receipt BEFORE any root operation, exclusive and private.
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        output = os.fdopen(descriptor, "w", encoding="utf-8")
        receipt.update(script_sha256=hashlib.sha256(script).hexdigest(), script_bytes=len(script),
                       host=args.host, controller=args.controller,
                       capture_port=args.capture_port, agent_port=args.agent_port)
        with tempfile.TemporaryDirectory(prefix="tv-session-", dir=destination.parent) as temporary:
            directory = Path(temporary)
            worker = multiprocessing.get_context("fork").Process(target=_child, args=(args, command, str(directory)))
            worker.start()
            try:
                worker.join(args.session_timeout)
                if worker.is_alive():
                    receipt["session_timed_out"] = True
                    stop_worker(worker)
            finally:
                stop_worker(worker)
                receipt["worker_exit"] = worker.exitcode
                collect(directory, receipt)
    except BaseException as error:
        if isinstance(error, SystemExit) and error.code == 0:
            return 0
        receipt["ok"] = False
        receipt["error_type"] = type(error).__name__
        receipt["error"] = str(error)
    finally:
        if output is not None:
            receipt["completed_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
            try:
                json.dump(receipt, output, indent=2, ensure_ascii=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                receipt["ok"] = False
            finally:
                output.close()
        if worker is not None and not worker.is_alive():
            worker.close()
    # No addresses, user paths, command text, stdout, stderr or exception text.
    print("tv-session: success; private receipt saved" if receipt["ok"] else "tv-session: failed or refused; inspect private receipt if created")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
