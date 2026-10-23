"""Offline only: relocate literal device paths; real awk/bash/files, fake systemctl."""
import hashlib, importlib.util, json, os, pathlib, shutil, subprocess, tempfile, unittest
P = pathlib.Path(__file__).resolve().parents[1]
SOURCE = pathlib.Path(os.environ.get('RECOGNITION_SOURCE', P/'tools/recognition.py'))
class Package(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'missing offline renderer')
        spec=importlib.util.spec_from_file_location('pkg', SOURCE); self.mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.mod)
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.r=pathlib.Path(self.tmp.name)
        self.uid=os.getuid(); self.gid=os.getgid(); self.log=self.r/'calls'
        self.meta=self.r/'metadata.json'
        self.metadata={
          '/opt':dict(uid=0,gid=0,label='_'), '/opt/usr':dict(uid=0,gid=0,label='_'), '/opt/usr/share':dict(uid=0,gid=0,label='_'),
          '/opt/etc':dict(uid=0,gid=1051,label='System::Shared',transmute=True),
          '/run/systemd':dict(uid=0,gid=0,label='System::Run',transmute=True),
          '/run/systemd/system':dict(uid=0,gid=202,label='System::Run',transmute=True)}
        self.meta.write_text(json.dumps(self.metadata))
        self.root=self.r/'tv'; self.root.mkdir()
        for d in ('opt/etc','opt/usr/share/hermes-tv-debloat','usr/lib/systemd/system','run/systemd/system','etc/systemd/system','proc/sys/kernel/random'):
            (self.root/d).mkdir(parents=True, exist_ok=True)
        for path,mode in [('/opt',0o755),('/opt/etc',0o777),('/opt/usr',0o755),('/opt/usr/share',0o755),('/run/systemd',0o755),('/run/systemd/system',0o775)]: (self.root/path.lstrip('/')).chmod(mode)
        (self.root/'opt/usr/share/hermes-tv-debloat').chmod(0o700)
        (self.root/'proc/sys/kernel/random/boot_id').write_text('offline-boot\n')
        self.stock=b'#!/bin/bash\nprintf "stock\\n" >> "'+str(self.log).encode()+b'"\nexit "${STOCK_EXIT:-0}"\n'
        (self.root/'opt/etc/parseinfo.sh').write_bytes(self.stock); (self.root/'opt/etc/parseinfo.sh').chmod(0o777)
        self.pins={}
        for name in ('AT-HUB.service','contents-recognition-service.service','contents-ui-detector-service.service'):
            data=(name+' fixture\n').encode(); (self.root/'usr/lib/systemd/system'/name).write_bytes(data); self.pins[name]=hashlib.sha256(data).hexdigest()
        self.bin=self.r/'bin'; self.bin.mkdir()
        fake='''#!/bin/bash
printf '%s\\n' "$*" >> "$LOG"
case "$1" in
show) case "$2" in *contents-*) printf 'Id=%s\\nLoadState=masked\\nActiveState=%s\\nMainPID=%s\\n' "$2" "${ACTIVE:-inactive}" "${PID:-0}"; if test "${DUPLICATE:-0}" = 1; then printf 'ActiveState=active\\n'; fi;; *) exit 1;; esac;;
--no-block) test "$2" = stop && test "${STOP_FAIL:-0}" = 0;;
daemon-reload) test "${RELOAD_FAIL:-0}" = 0;;
*) exit 1;;
esac
'''
        # Only UID/GID and SMACK are emulated; native paths/types/modes/inodes remain real.
        stat_script="""#!/usr/bin/python3
import json,os,subprocess,sys
args=sys.argv[1:]; p=args[-1]; key=p.removeprefix(os.environ['ROOT'])
m=json.load(open(os.environ['META'])).get(key,{})
fmt=args[1].replace('%u',str(m.get('uid',0))).replace('%g',str(m.get('gid',0)))
if 'mode' in m: fmt=fmt.replace('%a',m['mode'])
sys.exit(subprocess.run(['/usr/bin/stat','-c',fmt,p]).returncode)
"""
        smack_script="""#!/usr/bin/python3
import json,os,sys
p=sys.argv[-1]; key=p.removeprefix(os.environ['ROOT']); m=json.load(open(os.environ['META'])).get(key,{})
if len(sys.argv)==2:
 print(p+' access="'+m.get('label','_')+'"'+(' transmute="TRUE"' if m.get('transmute',False) else ''))
else:
 with open(os.environ['META']+'.writes','a') as f: f.write(key+'\\n')
"""
        for n,body in {'systemctl':fake,'stat':stat_script,'chsmack':smack_script,'sleep':'#!/bin/bash\nexit 0\n'}.items():
            f=self.bin/n; f.write_text(body); f.chmod(0o755)
        # Exact literal relocation + identity/hash fixture adaptation; no production env override.
        self.packet=self.mod.render(stock_sha=hashlib.sha256(self.stock).hexdigest(), unit_pins=self.pins)
        def adapt(s):
            s=s.replace('/opt',str(self.root)+'/opt').replace('/run/',str(self.root)+'/run/').replace('/etc/systemd/',str(self.root)+'/etc/systemd/').replace('/usr/lib/systemd/',str(self.root)+'/usr/lib/systemd/').replace('/proc/sys/kernel/random/',str(self.root)+'/proc/sys/kernel/random/').replace('PATH=/usr/bin:/bin','PATH='+str(self.bin)+':/usr/bin:/bin')
            s=s.replace('"$(id -u)" = 0','"$(id -u)" = '+str(self.uid)).replace('chown 0:0',f'chown {self.uid}:{self.gid}')
            return s
        # Render with relocated scripts so all embedded hashes refer to actual adapted bytes.
        self.packet=self.mod.render(stock_sha=hashlib.sha256(self.stock).hexdigest(),unit_pins=self.pins, transform=adapt)
        # Refuse fixture execution unless every native data path was relocated.
        # The shebang/interpreters, coreutils and /dev/null remain real host tools.
        import re
        native = r'(?<![\w/.-])/(?:opt(?:/|\b)|run/systemd|etc/systemd|usr/lib/systemd|proc/sys/kernel/random)'
        for name, text in self.packet.items():
            self.assertIsNone(re.search(native,text), 'unrelocated native path in '+name)
        self.assertTrue((self.bin/'systemctl').is_file())
        self.env={'PATH':str(self.bin)+':/usr/bin:/bin','LOG':str(self.log),'HOME':str(self.r),'ROOT':str(self.root),'META':str(self.meta)}
    def runpart(self, part, **env):
        return subprocess.run(['/bin/bash','-s'],input=self.packet[part].encode(),env={**self.env,**env},capture_output=True,timeout=12)
    @property
    def hook(self): return self.root/'opt/etc/parseinfo.sh'
    @property
    def task(self): return self.root/self.mod.D.lstrip('/')
    def install(self):
        x=self.runpart('installer'); self.assertEqual(x.returncode,0,x.stderr.decode()); return x
    def dispatch(self, **env):
        return subprocess.run([str(self.hook)],env={**self.env,**env},capture_output=True,timeout=12)
    def test_vendor_stock_pin_and_synthetic_execution(self):
        # Nonunique vendor pins, NOT redistributed Samsung input files.
        self.assertEqual(self.mod.STOCK_SHA,'c6369e7dec69408e176daa252d436acf6f8e265f560504d8bd831c8023c71d61')
        self.assertEqual(self.mod.PINS,{
            'AT-HUB.service':'b6829f0f7e95464178f92922e5fdca83bf0874df2e1bbb77d68db6892a5490b3',
            'contents-recognition-service.service':'0138444405ca3a84d1ab03c3ed4c5c5c46f7c6523b610986196f840a920b083c',
            'contents-ui-detector-service.service':'431cfb11d3fd622c32046dd662e47464b6c42e3d2b54626e901715f045d50d50'})
        self.install()
        self.assertEqual(self.dispatch().returncode,0)
        self.assertEqual(self.log.read_text().splitlines()[0],'stock')

    def test_fixture_install_real_awk_masks_inverse_roundtrip(self):
        self.install()
        self.assertFalse(self.log.exists(), 'installer must never execute the hook')
        self.assertEqual(self.dispatch().returncode,0)
        runtime=self.root/'run/systemd/system'
        masks={p.name:os.lstat(p).st_ino for p in runtime.iterdir()}
        self.assertEqual(set(masks),set(self.mod.UNITS))
        self.assertEqual((self.task/'boot-offline-boot.receipt').read_text(),
                         'boot=offline-boot status=success masked=2 inactive=2 MainPID=0\n')
        calls=self.log.read_bytes()
        restored=self.runpart('inverse')
        self.assertEqual(restored.returncode,0,restored.stderr.decode())
        self.assertEqual(self.hook.read_bytes(),self.stock)
        self.assertEqual(self.hook.stat().st_mode & 0o777,0o777)
        self.assertEqual(masks,{p.name:os.lstat(p).st_ino for p in runtime.iterdir()})
        self.assertEqual(calls,self.log.read_bytes(),'inverse must not use the manager')
        self.assertIn('no services started, masks retained',(self.task/'restored').read_text())

    def test_renderer_rejects_bad_pin_shapes(self):
        for pins in ({}, {**self.pins,'foreign.service':'0'*64},
                     {**self.pins,'AT-HUB.service':'not-a-digest'}):
            with self.subTest(keys=sorted(pins)):
                with self.assertRaises(ValueError): self.mod.render(unit_pins=pins)
        with self.assertRaises(ValueError): self.mod.render(stock_sha='wrong')
    def test_install_preserve_inverse_replay(self):
        self.install(); self.assertEqual((self.task/'parseinfo.stock.sh').read_bytes(),self.stock)
        self.assertEqual(self.hook.stat().st_mode&0o777,0o755)
        before=self.hook.read_bytes(); self.assertNotEqual(self.runpart('installer').returncode,0); self.assertEqual(self.hook.read_bytes(),before)
        self.assertEqual(self.runpart('inverse').returncode,0); self.assertEqual(self.hook.read_bytes(),self.stock); self.assertEqual(self.hook.stat().st_mode&0o777,0o777)
        self.assertNotEqual(self.runpart('inverse').returncode,0)
    def test_real_awk_dispatch_order_and_two_masks(self):
        self.install(); x=self.dispatch(); self.assertEqual(x.returncode,0,x.stderr.decode())
        lines=self.log.read_text().splitlines(); stops=[x for x in lines if x.startswith('--no-block stop')]
        self.assertEqual(stops,['--no-block stop contents-ui-detector-service.service','--no-block stop contents-recognition-service.service']); self.assertEqual(lines[0],'stock')
        masks=list((self.root/'run/systemd/system').iterdir()); self.assertEqual(len(masks),2); self.assertTrue(all(x.is_symlink() and os.readlink(x)=='/dev/null' for x in masks))
        self.assertIn('success',(self.task/'boot-offline-boot.receipt').read_text()); self.assertEqual(self.dispatch().returncode,0)
    def test_partial_foreign_mask_refuses_before_mutation(self):
        self.install(); foreign=self.root/'run/systemd/system/contents-ui-detector-service.service'; foreign.symlink_to('/dev/null')
        self.assertNotEqual(self.dispatch().returncode,0); self.assertEqual(len(list(foreign.parent.iterdir())),1); self.assertNotIn('stop',self.log.read_text())
    def test_stock_and_block_tamper_fail_before_stop(self):
        self.install(); (self.task/'block.sh').write_text('exit 0\n'); self.assertNotEqual(self.dispatch().returncode,0); self.assertFalse(self.log.exists())
    def test_failure_receipt_not_success(self):
        self.install(); self.assertNotEqual(self.dispatch(STOP_FAIL='1').returncode,0); self.assertNotIn('success',(self.task/'boot-offline-boot.receipt').read_text())
    def test_unexpected_state_is_not_success(self):
        self.install(); self.assertNotEqual(self.dispatch(ACTIVE='active',PID='23').returncode,0); self.assertNotIn('success',(self.task/'boot-offline-boot.receipt').read_text())
    def test_installer_wrong_stock_or_pin_no_mutation(self):
        self.hook.write_text('wrong'); self.assertNotEqual(self.runpart('installer').returncode,0); self.assertEqual(self.hook.read_text(),'wrong'); self.assertFalse(self.task.exists())
    def test_inverse_foreign_hook_refuses(self):
        self.install(); self.hook.write_text('foreign'); self.assertNotEqual(self.runpart('inverse').returncode,0); self.assertEqual(self.hook.read_text(),'foreign')
    def test_inode_modes_no_foreign_dirs(self):
        self.task.symlink_to(self.r); self.assertNotEqual(self.runpart('installer').returncode,0); self.assertEqual(self.hook.read_bytes(),self.stock)
    def test_foreign_runtime_directory_rejected(self):
        self.install(); p=self.root/'run/systemd/system'; p.rmdir(); p.symlink_to(self.r/'bin')
        self.assertNotEqual(self.dispatch().returncode,0)
        self.assertFalse((self.bin/'contents-recognition-service.service').is_symlink())
    def test_wrong_unit_pin_rejected_before_backup(self):
        (self.root/'usr/lib/systemd/system/AT-HUB.service').write_text('changed')
        self.assertNotEqual(self.runpart('installer').returncode,0); self.assertFalse(self.task.exists())
    def test_stock_tamper_fail_closed(self):
        self.install(); p=self.task/'parseinfo.stock.sh'; p.write_text('exit 9\n')
        self.assertNotEqual(self.dispatch().returncode,0); self.assertFalse(self.log.exists())
    def test_reload_failure_truthful_and_inverse_keeps_masks(self):
        self.install(); self.assertNotEqual(self.dispatch(RELOAD_FAIL='1').returncode,0)
        self.assertNotIn('stop',self.log.read_text()); self.assertNotIn('success',(self.task/'boot-offline-boot.receipt').read_text())
        self.assertEqual(self.runpart('inverse').returncode,0); self.assertEqual(len(list((self.root/'run/systemd/system').iterdir())),2)
    def test_nonzero_stock_prevents_all_systemctl(self):
        self.install(); self.assertNotEqual(self.dispatch(STOCK_EXIT='9').returncode,0)
        self.assertEqual(self.log.read_text(),'stock\n'); self.assertEqual(len(list((self.root/'run/systemd/system').iterdir())),0)
    def test_duplicate_properties_refuse_success(self):
        self.install(); self.assertNotEqual(self.dispatch(DUPLICATE='1').returncode,0)
    def test_inverse_marker_content_tamper_refused(self):
        self.install(); (self.task/'intent').write_text('foreign')
        self.assertNotEqual(self.runpart('inverse').returncode,0)
    def test_second_foreign_mask_prevalidated(self):
        self.install(); p=self.root/'run/systemd/system/contents-ui-detector-service.service'; p.write_text('foreign')
        self.assertNotEqual(self.dispatch().returncode,0); self.assertEqual(len(list(p.parent.iterdir())),1)

    def update_meta(self,path,**fields):
        self.metadata.setdefault(path,{}).update(fields); self.meta.write_text(json.dumps(self.metadata))
    def parents(self):
        return {p:(os.lstat(self.root/p.lstrip('/')).st_ino,os.lstat(self.root/p.lstrip('/')).st_mode,os.lstat(self.root/p.lstrip('/')).st_uid,os.lstat(self.root/p.lstrip('/')).st_gid) for p in self.metadata}
    def test_mf1_exact_opt_baseline_all_consumers_no_parent_changes(self):
        before=self.parents(); meta=self.meta.read_bytes()
        self.install(); x=self.dispatch(); self.assertEqual(x.returncode,0,x.stderr.decode())
        self.assertEqual(self.runpart('inverse').returncode,0)
        self.assertEqual(before,self.parents()); self.assertEqual(meta,self.meta.read_bytes())
        writes=pathlib.Path(str(self.meta)+'.writes').read_text().splitlines()
        self.assertTrue(all(p not in self.metadata for p in writes))
    def test_mf2_exact_runtime_baseline(self):
        # Characterization of the exact accepted vendor parent metadata.
        self.task.mkdir(mode=0o700)
        x=self.runpart('block'); self.assertEqual(x.returncode,0,x.stderr.decode())
        self.assertEqual(len(list((self.root/'run/systemd/system').iterdir())),2)
    def test_mf3_private_sibling_exact(self):
        self.assertEqual(self.mod.D,'/opt/usr/share/hermes-recognition-persistent-20261023')
    def test_task_existing_metadata_is_enforced(self):
        self.install(); self.task.chmod(0o755)
        self.assertNotEqual(self.dispatch().returncode,0)
        self.assertNotEqual(self.runpart('inverse').returncode,0)
    def test_task_label_is_enforced(self):
        self.install(); self.update_meta(self.mod.D,label='User')
        self.assertNotEqual(self.dispatch().returncode,0)
        self.assertNotEqual(self.runpart('inverse').returncode,0)
    def test_exact_baseline_negative_dimensions(self):
        for path in ('/opt/etc','/run/systemd/system','/run/systemd','/opt','/opt/usr','/opt/usr/share'):
            for field,value in [('uid',9),('gid',9),('mode','757'),('label','User'),('transmute',path not in ('/opt/etc','/run/systemd/system','/run/systemd'))]:
                with self.subTest(path=path,field=field):
                    original=dict(self.metadata[path]); self.update_meta(path,**{field:value})
                    part='block' if path.startswith('/run/') else 'installer'
                    if part=='block' and not self.task.exists(): self.task.mkdir(mode=0o700)
                    x=self.runpart(part); self.assertNotEqual(x.returncode,0,(path,field))
                    self.metadata[path]=original; self.meta.write_text(json.dumps(self.metadata))
                    if self.task.exists(): self.task.rmdir()
    def test_baseline_types_and_path_are_not_generalized(self):
        for path in ('/opt/etc','/run/systemd/system'):
            for kind in ('file','symlink'):
                with self.subTest(path=path,kind=kind):
                    p=self.root/path.lstrip('/'); save=p.with_name(p.name+'.save'); p.rename(save)
                    if kind=='file': p.write_text('foreign')
                    else: p.symlink_to(save,target_is_directory=True)
                    if path.startswith('/run/'):
                        if not self.task.exists(): self.task.mkdir(mode=0o700)
                        x=self.runpart('block'); self.task.rmdir()
                    else: x=self.runpart('installer')
                    self.assertNotEqual(x.returncode,0); p.unlink(); save.rename(p)
        self.install(); self.task.chmod(0o777); self.update_meta(self.mod.D,uid=0,gid=1051,label='System::Shared',transmute=True)
        self.assertNotEqual(self.dispatch().returncode,0); self.assertNotEqual(self.runpart('inverse').returncode,0)
    def test_common_policy_wrapper_inverse_reject_each_dimension(self):
        self.install()
        for field,value in [('uid',9),('gid',9),('mode','775'),('label','_'),('transmute',False)]:
            with self.subTest(field=field):
                original=dict(self.metadata['/opt/etc']); self.update_meta('/opt/etc',**{field:value})
                self.assertNotEqual(self.dispatch().returncode,0)
                self.assertNotEqual(self.runpart('inverse').returncode,0)
                self.metadata['/opt/etc']=original; self.meta.write_text(json.dumps(self.metadata))

    def test_lock_cleanup_failure_cannot_publish_success(self):
        self.install()
        f=self.bin/'rmdir'; f.write_text('#!/bin/bash\nexit 1\n'); f.chmod(0o755)
        x=self.dispatch()
        self.assertNotEqual(x.returncode,0)
        self.assertNotIn('success',(self.task/'boot-offline-boot.receipt').read_text())
        self.assertTrue((self.task/'boot-offline-boot'/'lock').is_dir())

class OfflineCLI(unittest.TestCase):
    """New public CLI contract: real subprocesses, no TV/native script execution."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.out = self.root / 'private output'

    def cli(self, *args):
        import sys
        return subprocess.run([sys.executable, '-B', str(P/'tools/recognition.py'), *map(str,args)],
                              capture_output=True, timeout=10,
                              env={'PATH':'/usr/bin:/bin','HOME':str(self.root),
                                   'TMPDIR':str(self.root),'PYTHONDONTWRITEBYTECODE':'1'})

    def test_generate_complete_exclusive_manifest_bound_output(self):
        result = self.cli('--output', self.out)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        names = {'installer.sh','inverse.sh','wrapper.awk','block.sh','activate.sh','manifest.json'}
        self.assertEqual(set(p.name for p in self.out.iterdir()) if self.out.exists() else set(), names)
        manifest = json.loads((self.out/'manifest.json').read_text())
        spec=importlib.util.spec_from_file_location('public_renderer',P/'tools/recognition.py')
        self.assertIsNotNone(spec)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        expected=mod.render()
        for name,key in [('installer.sh','installer'),('inverse.sh','inverse'),('wrapper.awk','wrapper'),('block.sh','block')]:
            self.assertEqual((self.out/name).read_text(),expected[key])
        self.assertEqual((self.out/'activate.sh').read_text(),mod.activation(mod.sha(expected['wrapper'])))
        self.assertEqual(manifest['schema_version'], 1)
        self.assertEqual(set(manifest['files']), names-{'manifest.json'})
        self.assertEqual(manifest['target'], {'model':'TQ55Q70DATXXC','firmware':'T-PTMLDDEUC-1400.0','tizen':'8','arch':'ARMv7'})
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o700)
        for name, metadata in manifest['files'].items():
            data = (self.out/name).read_bytes()
            self.assertEqual(metadata['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual(metadata['bytes'],len(data))
            self.assertEqual((self.out/name).stat().st_mode & 0o777, 0o600)
            self.assertEqual(metadata['mode'],'0600')
        wrapper_sha = hashlib.sha256((self.out/'wrapper.awk').read_bytes()).hexdigest()
        self.assertIn(wrapper_sha,(self.out/'activate.sh').read_text())
        self.assertIn(wrapper_sha,(self.out/'inverse.sh').read_text())
        self.assertIn(wrapper_sha,(self.out/'installer.sh').read_text())
        for name in names-{'manifest.json','wrapper.awk'}:
            for shell in ['/bin/sh','/bin/bash']:
                checked = subprocess.run([shell,'-n',str(self.out/name)],capture_output=True)
                self.assertEqual(checked.returncode,0,checked.stderr.decode())
        # Parse real AWK with an unconditional earlier BEGIN exit: never execute its system().
        checked = subprocess.run(['/usr/bin/awk','-f','-','-f',str(self.out/'wrapper.awk')],
                                 input=b'BEGIN { exit 0 }\n',capture_output=True,timeout=5)
        self.assertEqual(checked.returncode,0,checked.stderr.decode())

    def test_repository_output_refused_before_creation(self):
        target = P/'recognition-output-must-not-exist'
        self.assertFalse(target.exists())
        result = self.cli('--output',target)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(target.exists())

    def test_symlink_parent_into_repository_refused(self):
        alias = self.root/'repo-alias'
        alias.symlink_to(P,target_is_directory=True)
        result = self.cli('--output',alias/'recognition-output-must-not-exist')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((P/'recognition-output-must-not-exist').exists())

    def test_existing_directory_and_file_never_clobbered(self):
        for kind in ['directory','file','dangling-symlink']:
            target = self.root/kind
            if kind == 'directory':
                target.mkdir(); (target/'sentinel').write_text('keep')
            elif kind == 'file': target.write_text('keep')
            else: target.symlink_to(self.root/'absent')
            result = self.cli('--output',target)
            self.assertNotEqual(result.returncode,0)
            if kind == 'directory': self.assertEqual((target/'sentinel').read_text(),'keep')
            elif kind == 'file': self.assertEqual(target.read_text(),'keep')
            else: self.assertTrue(target.is_symlink())

    def test_generation_with_network_and_process_creation_denied(self):
        # Real CLI executes with audit denial at the external side-effect boundaries.
        # No fake network response and no native process can hide behind a dry run.
        import sys
        code = '''import runpy,sys

def deny(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.posix_spawn','os.spawn','os.exec','os.fork'}:
        raise RuntimeError('offline generator attempted external IO')
sys.addaudithook(deny)
script,output=sys.argv[1:]
sys.argv=[script,'--output',output]
runpy.run_path(script,run_name='__main__')
'''
        child = subprocess.run([sys.executable,'-B','-c',code,str(P/'tools/recognition.py'),str(self.out)],
                               capture_output=True,timeout=10,
                               env={'PATH':'/usr/bin:/bin','HOME':str(self.root),'TMPDIR':str(self.root)})
        self.assertEqual(child.returncode,0,child.stderr.decode())
        self.assertTrue((self.out/'manifest.json').is_file())

    def test_required_output_and_unknown_pin_override_refused(self):
        self.assertNotEqual(self.cli().returncode,0)
        self.assertNotEqual(self.cli('--output',self.out,'--stock-sha','0'*64).returncode,0)
        self.assertFalse(self.out.exists())

    def test_repeat_generation_preserves_every_byte(self):
        first = self.cli('--output',self.out)
        self.assertEqual(first.returncode,0)
        self.assertTrue(self.out.is_dir(),'CLI did not generate its output')
        before = {p.name:p.read_bytes() for p in self.out.iterdir()}
        self.assertNotEqual(self.cli('--output',self.out).returncode,0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.out.iterdir()})

if __name__=='__main__': unittest.main(verbosity=2)
