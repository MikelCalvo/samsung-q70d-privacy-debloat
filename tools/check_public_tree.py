"""Offline packaging/privacy checks; no network and no device execution.

Pattern checks supplement manual review. They are not a proof of secrecy.
Only paths and fixed rule names are reported, never matched values.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import stat
from pathlib import Path

IGNORED_DIRS = {'.git', '__pycache__', '.venv'}
PRIVATE_SUFFIXES = {
    '.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx', '.pcap', '.pcapng',
    '.tar', '.gz', '.tgz', '.zip', '.wgt', '.tpk', '.rpm', '.so', '.bin', '.dll',
    '.exe', '.log', '.jsonl',
}
EXAMPLE_NETWORKS = tuple(ipaddress.ip_network(n) for n in ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24', '127.0.0.0/8'))
EMAIL = re.compile(r'[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
NOREPLY = re.compile(r'\d+\+[A-Za-z0-9-]+@users\.noreply\.github\.com\Z')
IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')
MAC = re.compile(r'(?<!\w)(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?!\w)')
UUID = re.compile(r'(?<!\w)[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?!\w)')
HOST_HOME = re.compile(r'[/]home/(?!owner(?:/|\b))[^\s\x27\x22`]+')


def scan_text(text: str, path: str) -> list[dict[str, str]]:
    kinds = set()
    if SECRET.search(text):
        kinds.add('credential_material')
    if MAC.search(text) or UUID.search(text):
        kinds.add('unique_device_identifier')
    if HOST_HOME.search(text):
        kinds.add('personal_host_path')
    if any(not NOREPLY.fullmatch(m.group()) for m in EMAIL.finditer(text)):
        kinds.add('personal_email')
    for m in IPV4.finditer(text):
        try:
            address = ipaddress.ip_address(m.group())
        except ValueError:
            continue
        # The standard all-hosts limited broadcast is not an installation address.
        if int(address) == 2**32 - 1 or address.is_unspecified or any(address in n for n in EXAMPLE_NETWORKS):
            continue
        if address.is_private or address.is_link_local:
            kinds.add('nonpublic_example_address')
    return [{'path': path, 'kind': k} for k in sorted(kinds)]


def scan_tree(root: Path) -> list[dict[str, str]]:
    root = root.resolve(strict=True)
    issues = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        name = relative.as_posix()
        if not stat.S_ISREG(mode):
            issues.append({'path': name, 'kind': 'symlink_or_special_file'})
            continue
        if path.suffix.lower() in PRIVATE_SUFFIXES or path.name.startswith('.env'):
            issues.append({'path': name, 'kind': 'private_or_binary_file'})
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            issues.append({'path': name, 'kind': 'non_utf8_file'})
            continue
        issues.extend(scan_text(text, name))
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        issues = scan_tree(args.root)
    except (OSError, ValueError):
        print(json.dumps({'status': 'error', 'kind': 'unreadable_tree'}))
        return 2
    print(json.dumps({'status': 'pass' if not issues else 'fail', 'issues': issues}, indent=2))
    return int(bool(issues))


if __name__ == '__main__':
    raise SystemExit(main())
