"""Free application release fixtures; no AWS calls or real service changes.

All application directories are temporary. Service commands, health requests
and activity reads are doubles; archive extraction and manifest checks are real.
Run with the project venv: python docs/aws/livekit-production-tools/app_release_contract.py.
"""
import hashlib, io, json, os, sys, tarfile, tempfile, unittest
import signal
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_common as common, app_stage as stage, app_cutover as cutover

class ReleaseFixture(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='app-release-qa-')
        self.root = Path(self.temp.name).resolve()
        self.receipt = self.root / 'receipt'
        self.release = self.root / 'release'
        self.receipt.mkdir()
        self.release.mkdir()
        (self.release / '.venv/bin').mkdir(parents=True)
        (self.release / '.venv/bin/python').write_text('private runtime remains')
        self.values = {'RECEIPT': self.receipt, 'RELEASE': self.release, 'OLD': self.root / 'old', 'DATA': self.root / 'data', 'ENV': self.root / 'provider.env', 'LIVEKIT_ENV': self.root / 'runtime.env', 'CADDY': self.root / 'Caddyfile', 'AUTH': self.root / 'auth', 'CONF': self.root / 'new.conf', 'PYTHON': self.release / '.venv/bin/python'}
        self.patches = []
        for module in [common, stage, cutover]:
            for (name, value) in self.values.items():
                if hasattr(module, name):
                    self.patches.append(patch.object(module, name, value))
                    self.patches[-1].start()
        self.commit = '1' * 40
        self.files = {'server/test.py': b'print("fixture")\n', 'web/a.js': b'console.log("fixture");\n'}
        self.archive(self.files)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def archive(self, files, extra=None):
        archive = self.receipt / 'source.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for (name, data) in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if extra:
                tar.addfile(extra)
        (self.receipt / 'package.json').write_text(json.dumps({'commit': self.commit, 'archives': {'source.tar.gz': {'bytes': archive.stat().st_size, 'sha256': common.sha(archive)}}}))
        (self.receipt / 'source-manifest.json').write_text(json.dumps({name: hashlib.sha256(data).hexdigest() for (name, data) in self.files.items()}))

    def test_valid_stage_preserves_venv_and_binds_exact_manifest(self):
        stage.main()
        self.assertEqual(common.verify_source(), 2)
        self.assertEqual((self.release / '.venv/bin/python').read_text(), 'private runtime remains')

    def test_stage_rejects_other_existing_files(self):
        (self.release / 'unexpected').write_text('leave')
        with self.assertRaises(AssertionError):
            stage.main()
        self.assertEqual((self.release / 'unexpected').read_text(), 'leave')

    def test_stage_rejects_symbolic_link(self):
        info = tarfile.TarInfo('web/link')
        info.type = tarfile.SYMTYPE
        info.linkname = '/etc/passwd'
        self.archive(self.files, info)
        with self.assertRaises(AssertionError):
            stage.main()
        self.assertFalse((self.release / 'server').exists())

    def test_stage_rejects_traversal_and_extra_files(self):
        for name in ['../escape', 'unmanifested', 'web/../escape']:
            self.archive({**self.files, name: b'no'})
            with self.assertRaises(AssertionError):
                stage.main()

    def test_stage_rejects_runtime_archive_entry(self):
        self.archive({**self.files, '.venv/bin/python': b'overwrite'})
        with self.assertRaises(AssertionError):
            stage.main()
        self.assertEqual((self.release / '.venv/bin/python').read_text(), 'private runtime remains')

    def test_manifest_rejects_later_unmanifested_source(self):
        stage.main()
        (self.release / 'injected.py').write_text('x')
        with self.assertRaises(AssertionError):
            common.verify_source()

    def test_manifest_allows_only_exact_shared_links_and_bytecode(self):
        stage.main()
        self.values['DATA'].mkdir()
        self.values['ENV'].write_text('secret')
        (self.release / 'data').symlink_to(self.values['DATA'])
        (self.release / '.env').symlink_to(self.values['ENV'])
        (self.release / 'server/__pycache__').mkdir()
        (self.release / 'server/__pycache__/test.pyc').write_bytes(b'bytecode')
        self.assertEqual(common.verify_source(), 2)
        (self.release / 'server/__pycache__/not_code.txt').write_text('x')
        with self.assertRaises(AssertionError):
            common.verify_source()

    def test_receipts_never_overwrite(self):
        common.save('proof.json', {'once': 1})
        with self.assertRaises(AssertionError):
            common.save('proof.json', {'twice': 2})

    def rtc(self):
        report = {'passed': 32, 'total': 32, 'provider_calls': 0, 'physical_microphone': False, 'transport': 'real-hosted-livekit', 'errors': [], 'blocked': [], 'rtc': {'localType': 'relay', 'localRelayProtocol': 'tls', 'relayUsesTLS': True}, 'frames': {'received': 40, 'forwarded': 32}}
        (self.receipt / 'hosted-rtc.json').write_text(json.dumps(report))
        return report

    def test_rtc_requires_real_relay_tls_clean_frames(self):
        report = self.rtc()
        self.assertEqual(cutover.validate_rtc_receipt(), common.sha(self.receipt / 'hosted-rtc.json'))
        for (key, value) in [('provider_calls', 1), ('physical_microphone', True), ('total', 33), ('errors', ['bad']), ('transport', 'real-local-livekit')]:
            (self.receipt / 'hosted-rtc.json').write_text(json.dumps({**report, key: value}))
            with self.assertRaises(AssertionError):
                cutover.validate_rtc_receipt()

    def test_dropin_preserves_provider_env_and_trusts_only_loopback(self):
        text = cutover.dropin()
        self.assertIn('ExecStart=\nExecStart=' + str(self.values['PYTHON']), text)
        self.assertIn('EnvironmentFile=' + str(self.values['LIVEKIT_ENV']), text)
        self.assertIn('--forwarded-allow-ips 127.0.0.1', text)
        self.assertNotIn('MOCK_LLM', text)
        self.assertNotIn('*', text)

    def prepare_cutover(self):
        stage.main()
        self.rtc()
        data = self.values['DATA']
        data.mkdir()
        (data / 'fixture').write_bytes(b'preserve customer bytes')
        for name in ['ENV', 'CADDY', 'AUTH', 'LIVEKIT_ENV']:
            self.values[name].write_text(name + ' secret fixture')
        (self.receipt / 'gates.json').write_text('[]')
        common.save('app-staged-gates.ok.json', {'commit': self.commit, 'source_manifest_sha256': common.sha(self.receipt / 'source-manifest.json'), 'passed': 34, 'total': 34, 'outbound_attempts': 0, 'mock': True, 'isolated': True, 'results': 'gates.json', 'results_sha256': common.sha(self.receipt / 'gates.json')})
        self.active = True
        self.calls = []
        self.health = {'mock': False, 'model_tier': 'customer', 'tts_provider': 'sarvam', 'stt_provider': 'sarvam', 'runtime_providers': ['gemini']}

    def state(self, key):
        return {'ActiveState': 'active' if self.active else 'inactive', 'WorkingDirectory': str(self.release if self.values['CONF'].exists() else self.values['OLD']), 'ExecStart': cutover.dropin()}[key]

    def fake_run(self, *args, **kwargs):
        import shutil
        args = [str(a) for a in args]
        self.calls.append(args)
        bare = args[1:] if args[0] == 'sudo' else args
        if bare[:2] == ['systemctl', 'stop']:
            self.active = False
        if bare[:2] == ['systemctl', 'start']:
            self.active = True
        if bare[:2] == ['systemctl', 'cat']:
            return NS(stdout='old private service')
        if bare[:2] == ['systemctl', 'is-active']:
            return NS(stdout='active')
        if bare[0] == 'sha256sum':
            return NS(stdout=common.sha(bare[1]) + '  file')
        if bare[:2] == ['du', '-sb']:
            return NS(stdout='10 data')
        if bare[0] == 'cp':
            shutil.copyfile(bare[-2], bare[-1])
        if bare[0] == 'install':
            shutil.copyfile(bare[-2], bare[-1])
        if bare[0] == 'mv':
            shutil.move(bare[-2], bare[-1])
        if bare[:3] == ['tar', '-I', 'gzip -1']:
            Path(bare[4]).write_bytes(b'fake snapshot fixture')
        return NS(stdout='')

    def contexts(self, activity=None):
        from contextlib import ExitStack
        s = ExitStack()
        s.enter_context(patch.object(cutover, 'state', self.state))
        s.enter_context(patch.object(cutover, 'run', self.fake_run))
        s.enter_context(patch.object(cutover, 'healthy', lambda : dict(self.health)))
        s.enter_context(patch.object(cutover, 'operational_metadata', lambda : activity or []))
        s.enter_context(patch.object(cutover, 'privileged_exists', lambda p: Path(p).exists()))
        s.enter_context(patch.object(cutover, 'local_json', lambda p: {'transport': 'livekit', 'livekit_enabled': True, 'livekit_available': True, 'mode': 'hosted'}))
        return s

    def test_cutover_success_preserves_data_environment_prior_dropins(self):
        self.prepare_cutover()
        with self.contexts():
            cutover.main()
        self.assertEqual((self.values['DATA'] / 'fixture').read_bytes(), b'preserve customer bytes')
        self.assertEqual(self.values['ENV'].read_text(), 'ENV secret fixture')
        self.assertTrue(self.values['CONF'].exists())
        self.assertTrue((self.receipt / 'app-cutover.completed').exists())

    def test_active_build_aborts_before_stop_or_data_write(self):
        self.prepare_cutover()
        with self.contexts([{'id': 'dm_fixture', 'active': True}]):
            with self.assertRaises(AssertionError):
                cutover.main()
        self.assertFalse(any(('stop' in c for c in self.calls)))
        self.assertFalse(self.values['CONF'].exists())

    def test_failed_cutover_restores_old_app_without_restoring_data(self):
        self.prepare_cutover()
        with self.contexts(), patch.object(cutover, 'local_json', side_effect=RuntimeError('failed new readiness')):
            with self.assertRaises(RuntimeError):
                cutover.main()
        self.assertTrue(self.active)
        self.assertFalse(self.values['CONF'].exists())
        self.assertEqual((self.values['DATA'] / 'fixture').read_bytes(), b'preserve customer bytes')
        rollback = json.loads(next(self.receipt.glob('app-rollback-*.json')).read_text())
        self.assertEqual(rollback['errors'], [])
        self.assertTrue((self.receipt / 'app-failed-release-service.conf').exists())

    def test_sigterm_enters_rollback_and_preserves_customer_data(self):
        self.prepare_cutover()
        previous = signal.getsignal(signal.SIGTERM)
        try:
            cutover.install_interrupt_handler()
            with self.contexts(), patch.object(cutover, 'local_json', side_effect=lambda _: signal.raise_signal(signal.SIGTERM)):
                with self.assertRaises(InterruptedError):
                    cutover.main()
        finally:
            signal.signal(signal.SIGTERM, previous)
        self.assertTrue(self.active)
        self.assertFalse(self.values['CONF'].exists())
        self.assertEqual((self.values['DATA'] / 'fixture').read_bytes(), b'preserve customer bytes')
        rollback = json.loads(next(self.receipt.glob('app-rollback-*.json')).read_text())
        self.assertEqual(rollback['errors'], [])
        self.assertTrue((self.receipt / 'app-failed-release-service.conf').exists())

    def test_service_commands_have_finite_default_and_explicit_deadlines(self):
        with patch.object(common.subprocess, 'run', return_value=NS(stdout='')) as execute:
            common.run('systemctl', 'start', 'demo-studio')
            self.assertEqual(execute.call_args.kwargs['timeout'], 120)
            common.run('systemctl', 'stop', 'demo-studio', timeout=None)
            self.assertEqual(execute.call_args.kwargs['timeout'], 120)
            common.run('tar', 'fixture', timeout=300)
            self.assertEqual(execute.call_args.kwargs['timeout'], 300)

if __name__ == '__main__':
    unittest.main(verbosity=2)
