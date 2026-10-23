"""Offline-only renderer. It never connects, installs or executes on a TV."""
import base64
import hashlib
import json
import re
import shlex

D='/opt/usr/share/hermes-recognition-persistent-20261023'
HOOK='/opt/etc/parseinfo.sh'
STOCK_SHA='c6369e7dec69408e176daa252d436acf6f8e265f560504d8bd831c8023c71d61'
PINS={
 'AT-HUB.service':'b6829f0f7e95464178f92922e5fdca83bf0874df2e1bbb77d68db6892a5490b3',
 'contents-recognition-service.service':'0138444405ca3a84d1ab03c3ed4c5c5c46f7c6523b610986196f840a920b083c',
 'contents-ui-detector-service.service':'431cfb11d3fd622c32046dd662e47464b6c42e3d2b54626e901715f045d50d50',
}
UNITS=('contents-recognition-service.service','contents-ui-detector-service.service')
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def q(s): return shlex.quote(s)
COMMON='''set -eu
PATH=/usr/bin:/bin
export PATH
umask 077
unset ENV BASH_ENV CDPATH
fail() { printf '%s\\n' "REFUSE: $*" >&2; exit 1; }
test "$(id -u)" = 0 || fail root
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
regular() { test -f "$1" && test ! -L "$1" || fail file-type; test "$(stat -c '%u:%g:%a' "$1")" = "0:0:$2" || fail file-metadata; }
label() { case "$(chsmack "$1")" in *'access="_"'*) :;; *) fail smack;; esac; }
secure_dir() {
 test -d "$1" && test ! -L "$1" || fail directory-type
 case "$1" in
 /opt/etc) metadata='0:1051:777'; smack='access="System::Shared" transmute="TRUE"';;
 /run/systemd/system) metadata='0:202:775'; smack='access="System::Run" transmute="TRUE"';;
 /run/systemd) metadata='0:0:755'; smack='access="System::Run" transmute="TRUE"';;
 /opt|/opt/usr|/opt/usr/share) metadata='0:0:755'; smack='access="_"';;
 "$D") metadata='0:0:700'; smack='access="_"';;
 *) test "$(stat -c '%u:%g' "$1")" = '0:0' || fail directory-owner
    m=$(stat -c '%a' "$1"); test "$((0$m & 0022))" = 0 || fail directory-writable
    metadata="0:0:$m"; smack='access="_"';;
 esac
 test "$(stat -c '%u:%g:%a' "$1")" = "$metadata" || fail directory-metadata
 test "$(chsmack "$1")" = "$1 $smack" || fail directory-smack
}
'''
def render(stock_sha=STOCK_SHA,unit_pins=None,transform=lambda s:s):
    pins=PINS if unit_pins is None else unit_pins
    if set(pins)!=set(PINS) or any(not re.fullmatch('[0-9a-f]{64}',v) for v in [stock_sha,*pins.values()]):
        raise ValueError('exact unit allowlist and SHA256 pins required')
    base=transform(COMMON+f'D={D}\nH={HOOK}\n')
    # All executable/script hashes are calculated AFTER offline fixture relocation.
    checks=''
    for n,h in pins.items():
        path='/usr/lib/systemd/system/'+n
        checks+=f'test -f {path} && test ! -L {path} || fail unit-type\ntest "$(hash {path})" = {h} || fail unit-pin\n'
    checks=transform(checks)
    dirs=transform('for p in /opt /opt/etc /opt/usr /opt/usr/share; do secure_dir "$p"; done\n')
    units=' '.join(UNITS)
    block=base+dirs+checks+f'''secure_dir "$D"
for p in /run/systemd /run/systemd/system; do secure_dir "$p"; done
BOOT=$(cat /proc/sys/kernel/random/boot_id)
case "$BOOT" in ''|*[!a-zA-Z0-9-]*) fail boot-id;; esac
R="$D/boot-$BOOT.receipt"
B="$D/boot-$BOOT"
if test -e "$B" || test -L "$B"; then secure_dir "$B"; else mkdir -m 700 "$B" || fail boot-create; chsmack -a _ "$B"; fi
mkdir -m 700 "$B/lock" || fail concurrent-or-interrupted
trap 'rmdir "$B/lock"' EXIT
if test -e "$R" || test -L "$R"; then regular "$R" 600; else (set -C; : > "$R") || fail receipt-create; chown 0:0 "$R"; chmod 600 "$R"; chsmack -a _ "$R"; fi
printf 'boot=%s status=started\\n' "$BOOT" > "$R"
# Validate BOTH names and ownership records before creating EITHER mask.
for n in {units}; do
 p=/run/systemd/system/$n
 if test -e "$p" || test -L "$p"; then
  test -L "$p" && test "$(readlink "$p")" = /dev/null || fail foreign-mask
  regular "$B/$n.owner" 600
  test "$(cat "$B/$n.owner")" = "$(stat -c '%d:%i:%u:%g' "$p")" || fail foreign-mask-identity
 else
  test ! -e "$B/$n.owner" && test ! -L "$B/$n.owner" || fail interrupted-mask
 fi
done
for n in {units}; do
 p=/run/systemd/system/$n
 if test ! -L "$p"; then
  ln -s /dev/null "$p" || fail mask-create
  (set -C; stat -c '%d:%i:%u:%g' "$p" > "$B/$n.owner") || fail ownership-record
  chmod 600 "$B/$n.owner"; chsmack -a _ "$B/$n.owner"
 fi
done
systemctl daemon-reload || fail reload
systemctl --no-block stop contents-ui-detector-service.service || fail stop-ui
systemctl --no-block stop contents-recognition-service.service || fail stop-provider
ok=0
i=0
while test "$i" -le 8; do
 ok=1
 for n in {units}; do
  s=$(systemctl show "$n" -p Id -p LoadState -p ActiveState -p MainPID) || fail show
  for property in Id LoadState ActiveState MainPID; do
   test "$(printf '%s\\n' "$s" | grep -c "^$property=")" = 1 || fail property-count
  done
  printf '%s\\n' "$s" | grep -Fx "Id=$n" >/dev/null || fail id
  for line in LoadState=masked ActiveState=inactive MainPID=0; do
   printf '%s\\n' "$s" | grep -Fx "$line" >/dev/null || ok=0
  done
 done
 test "$ok" = 1 && break
 test "$i" = 8 && break
 sleep 1
 i=$((i+1))
done
test "$ok" = 1 || fail not-quiescent
# Ordinary release failure must not leave a completed receipt.
if rmdir "$B/lock"; then
 trap - EXIT
else
 trap - EXIT
 fail lock-release
fi
printf 'boot=%s status=success masked=2 inactive=2 MainPID=0\\n' "$BOOT" > "$R"
'''
    # base/dirs/checks already transformed; transform only the block suffix.
    prefix=base+dirs+checks
    block=prefix+transform(block[len(prefix):])
    guard=base+dirs+f'''secure_dir "$D"
regular "$D/parseinfo.stock.sh" 700
label "$D/parseinfo.stock.sh"
test "$(hash "$D/parseinfo.stock.sh")" = {stock_sha} || fail stock-pin
regular "$D/block.sh" 600
label "$D/block.sh"
test "$(hash "$D/block.sh")" = {sha(block)} || fail block-pin
'''
    # Guard is shell -c data, never passed as an unsigned script filename.
    # guard includes literal fixed paths in its suffix; relocate that suffix before hashing.
    # base+dirs are already transformed; avoid transforming them a second time.
    guard=base+dirs+transform(guard[len(base+dirs):])
    wrapper='#!/usr/bin/awk -f\n# HERMES recognition persistent v1\nBEGIN {\n'
    for command,code in ((guard+'exec /bin/bash "$D/parseinfo.stock.sh"\n',71),(guard+'. "$D/block.sh"\n',72)):
        wrapper+='  if (system('+json.dumps('/bin/sh -c '+q(command))+') != 0) exit '+str(code)+';\n'
    wrapper+='  exit 0;\n}\n'
    inverse=base+dirs+transform(f'''secure_dir "$D"
regular "$D/intent" 600
test "$(cat "$D/intent")" = 'HERMES recognition persistent v1; no immediate execution' || fail intent-marker
regular "$H" 755
label "$H"
test "$(hash "$H")" = {sha(wrapper)} || fail installed-hook-pin
regular "$D/parseinfo.stock.sh" 700
label "$D/parseinfo.stock.sh"
test "$(hash "$D/parseinfo.stock.sh")" = {stock_sha} || fail stock-pin
test ! -e "$D/restored" && test ! -L "$D/restored" || fail replay
(set -C; printf 'restore-hook-only; runtime masks intentionally retained\\n' > "$D/restore-intent") || fail restore-replay
# Stage on the hook filesystem without clobbering an existing name.
T="$H.hermes-restore-20261023"
(set -C; cat "$D/parseinfo.stock.sh" > "$T") || fail restore-stage
chown 0:0 "$T"; chmod 777 "$T"; chsmack -a _ "$T"
regular "$T" 777; label "$T"
test "$(hash "$T")" = {stock_sha} || fail restore-stage-pin
mv -T "$T" "$H"
printf 'restored hook; reboot required; no services started, masks retained\\n' > "$D/restored"
''')
    installer=base+dirs+checks+transform(f'''test ! -e "$D" && test ! -L "$D" || fail existing-task
regular "$H" 777
label "$H"
test "$(hash "$H")" = {stock_sha} || fail stock-pin
for n in {units}; do
 for p in /run/systemd/system/$n /etc/systemd/system/$n; do
  test ! -e "$p" && test ! -L "$p" || fail existing-mask
 done
done
mkdir -m 700 "$D" || fail task-create
chown 0:0 "$D"; chsmack -a _ "$D"
(set -C; printf 'HERMES recognition persistent v1; no immediate execution\\n' > "$D/intent")
cp "$H" "$D/parseinfo.stock.sh"
chown 0:0 "$D/parseinfo.stock.sh"; chmod 700 "$D/parseinfo.stock.sh"; chsmack -a _ "$D/parseinfo.stock.sh"
test "$(hash "$D/parseinfo.stock.sh")" = {stock_sha} || fail backup-pin
''')
    for name,data,mode in [('block.sh',block,'600'),('restore-hook.sh',inverse,'600'),('wrapper.awk',wrapper,'755')]:
        encoded=base64.b64encode(data.encode()).decode()
        installer+=f"(set -C; printf %s {encoded} | base64 -d > \"$D/{name}\")\n"
        installer+=f'chown 0:0 "$D/{name}"; chmod {mode} "$D/{name}"; chsmack -a _ "$D/{name}"\n'
        installer+=f'test "$(hash "$D/{name}")" = {sha(data)} || fail prepared-pin\n'
    installer+=transform(f'''T="$H.hermes-new-20261023"
(set -C; cat "$D/wrapper.awk" > "$T") || fail hook-stage
chown 0:0 "$T"; chmod 755 "$T"; chsmack -a _ "$T"
regular "$T" 755; label "$T"
test "$(hash "$T")" = {sha(wrapper)} || fail staged-pin
# Recheck original immediately before same-filesystem replacement.
regular "$H" 777; label "$H"
test "$(hash "$H")" = {stock_sha} || fail original-changed
mv -T "$T" "$H"
printf 'installed; hook NOT executed; persistence not yet verified\\n' > "$D/installed"
''')
    # Embedded write metadata also uses the offline fixture identity.
    # Do not transform entire installer: embedded paths/hashes must stay exact.
    if transform is not None:
        # Adapt only the small metadata statements built above.
        for name,_,mode in [('block.sh',block,'600'),('restore-hook.sh',inverse,'600'),('wrapper.awk',wrapper,'755')]:
            old=f'chown 0:0 "$D/{name}"; chmod {mode} "$D/{name}"; chsmack -a _ "$D/{name}"'
            installer=installer.replace(old,transform(old))
    return dict(installer=installer,inverse=inverse,wrapper=wrapper,block=block)
def activation(wrapper_sha):
    """Bind the reviewed inactive-only activation to this generated wrapper."""
    return f'''set -eu
h=$(sha256sum {HOOK}) || exit 1
test "${{h%% *}}" = {wrapper_sha} || exit 1
s=$(systemctl show AT-HUB.service -p ActiveState) || exit 1
test "$s" = ActiveState=inactive || exit 1
systemctl --no-block start AT-HUB.service
'''


def generate(output):
    """Create private offline output; never connect or execute native commands.

    Exclusive creation is no-clobber, not an atomic multi-file transaction.
    A failed write may leave this newly owned output directory incomplete.
    """
    import os
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    output = Path(output).expanduser().absolute()
    resolved = output.resolve()
    if resolved == repo or repo in resolved.parents:
        raise ValueError('output must be outside the repository')
    if os.path.lexists(output):
        raise ValueError('output must be a new directory')
    packet = render()
    payloads = {name: packet[key].encode('utf-8') for name, key in (
        ('installer.sh', 'installer'), ('inverse.sh', 'inverse'),
        ('wrapper.awk', 'wrapper'), ('block.sh', 'block'))}
    payloads['activate.sh'] = activation(sha(packet['wrapper'])).encode('utf-8')
    manifest = {
        'schema_version': 1,
        'target': {'model': 'TQ55Q70DATXXC', 'firmware': 'T-PTMLDDEUC-1400.0',
                   'tizen': '8', 'arch': 'ARMv7'},
        'offline_only': True,
        'runtime_directory': D,
        'hook': HOOK,
        'vendor_stock_sha256': STOCK_SHA,
        'vendor_unit_sha256': PINS,
        'masked_units': list(UNITS),
        'files': {name: {'sha256': hashlib.sha256(data).hexdigest(),
                         'bytes': len(data), 'mode': '0600'}
                  for name, data in payloads.items()},
    }
    payloads['manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode('utf-8')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in payloads.items():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(output/name, flags, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    return manifest


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new private directory outside the repository')
    args = parser.parse_args(argv)
    try:
        generate(args.output)
    except ValueError as exc:
        parser.exit(1, 'REFUSE: '+str(exc)+'\n')
    except (OSError, RuntimeError):
        parser.exit(1, 'REFUSE: output unavailable; any partial output is private and incomplete\n')
    print('Generated 6 private offline files; nothing connected, installed or executed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
