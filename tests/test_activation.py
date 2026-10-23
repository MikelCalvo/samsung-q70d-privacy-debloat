"""Actual shell activation wiring; fake only the service manager."""
import hashlib, importlib.util, os, pathlib, re, subprocess, tempfile, unittest
P=pathlib.Path(__file__).resolve().parents[1]
# Characterization of the reviewed six-line activation, no installed input.
ACTIVATION = '''set -eu
h=$(sha256sum /opt/etc/parseinfo.sh) || exit 1
test "${h%% *}" = WRAPPER_SHA || exit 1
s=$(systemctl show AT-HUB.service -p ActiveState) || exit 1
test "$s" = ActiveState=inactive || exit 1
systemctl --no-block start AT-HUB.service
'''
class Activation(unittest.TestCase):
    def command(self):
        return ACTIVATION

    def scenario(self,text,code,tamper=False):
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d); hook=d/'hook'; hook.write_text('owned fixture')
            log=d/'calls'; binary=d/'systemctl'
            binary.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$LOG"\nif test "$1" = show; then printf "%s" "$SHOW_TEXT"; exit "$SHOW_EXIT"; fi\ntest "$*" = "--no-block start AT-HUB.service"\n')
            binary.chmod(0o755)
            command=self.command().replace('/opt/etc/parseinfo.sh',str(hook))
            command=command.replace('WRAPPER_SHA',hashlib.sha256(hook.read_bytes()).hexdigest())
            self.assertNotIn('/opt/etc/parseinfo.sh',command,'activation native path not relocated')
            if tamper: hook.write_text('foreign bytes')
            r=subprocess.run(['/bin/bash','-s'],input=command,text=True,capture_output=True,timeout=5,env={'PATH':str(d)+':/usr/bin:/bin','LOG':str(log),'SHOW_TEXT':text,'SHOW_EXIT':str(code)})
            calls=log.read_text().splitlines() if log.exists() else []
            return r.returncode,any(x=='--no-block start AT-HUB.service' for x in calls)
    def test_valid_inactive_starts(self):self.assertEqual(self.scenario('ActiveState=inactive\n',0),(0,True))
    def test_failed_show_valid_stdout_never_starts(self):
        code,started=self.scenario('ActiveState=inactive\n',1)
        self.assertFalse(started); self.assertNotEqual(code,0)
    def test_active_never_starts(self):
        code,started=self.scenario('ActiveState=active\n',0)
        self.assertFalse(started); self.assertNotEqual(code,0)
    def test_failed_empty_never_starts(self):
        code,started=self.scenario('',1)
        self.assertFalse(started); self.assertNotEqual(code,0)
    def test_duplicate_inactive_never_starts(self):
        code,started=self.scenario('ActiveState=inactive\nActiveState=inactive\n',0)
        self.assertFalse(started); self.assertNotEqual(code,0)
class GeneratedActivation(Activation):
    """The same five behavioral oracles against the public generated activation."""
    def command(self):
        spec=importlib.util.spec_from_file_location('recognition',P/'tools/recognition.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        self.assertTrue(callable(getattr(mod,'activation',None)), 'missing generated activation API')
        return mod.activation('WRAPPER_SHA')

    def test_wrapper_tamper_never_starts(self):
        code,started=self.scenario('ActiveState=inactive\n',0,tamper=True)
        self.assertFalse(started); self.assertNotEqual(code,0)

    def test_activation_binds_wrapper_hash(self):
        spec=importlib.util.spec_from_file_location('recognition',P/'tools/recognition.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        self.assertTrue(callable(getattr(mod,'activation',None)), 'missing generated activation API')
        code=mod.activation(hashlib.sha256(b'owned fixture').hexdigest())
        self.assertEqual(code,ACTIVATION.replace('WRAPPER_SHA',hashlib.sha256(b'owned fixture').hexdigest()))

if __name__=='__main__':unittest.main(verbosity=2)
