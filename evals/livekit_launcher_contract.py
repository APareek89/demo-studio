"""Offline contracts for the optional trial's isolated local launcher."""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("trial_launcher", Path(__file__).resolve().parents[1] / "scripts/run_livekit_trial.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="livekit-launcher-contract-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source" / "dm_fixture"
        self.source.mkdir(parents=True)
        self.state = self.root / "trial"
        self.bundle = {"runtime": {"version": 1}, "knowledge_snapshot_id": "ks_fixture"}
        (self.source / "bundle.json").write_text(json.dumps(self.bundle))

    def tearDown(self):
        self.temp.cleanup()

    def test_01_copies_pinned_publication_without_source_changes(self):
        (self.source / "media").mkdir()
        (self.source / "media" / "feature.jpg").write_bytes(b"fixture photo")
        before = {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob("*") if p.is_file()}
        self.assertEqual(launcher.copy_publication(self.source, self.state), "dm_fixture")
        after = {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((self.state / "data/dm_fixture/media/feature.jpg").read_bytes(), b"fixture photo")

    def test_02_prior_private_visits_are_not_copied(self):
        for name in ("sessions", "leads", "logs", "runtime", "usage"):
            (self.source / name).mkdir()
            (self.source / name / "private.json").write_text("private")
        (self.source / "usage.json").write_text("private")
        launcher.copy_publication(self.source, self.state)
        self.assertEqual({p.name for p in (self.state / "data/dm_fixture").iterdir()}, {"bundle.json"})

    def test_03_relaunch_preserves_trial_visits(self):
        launcher.copy_publication(self.source, self.state)
        visit = self.state / "data/dm_fixture/sessions/own.json"
        visit.parent.mkdir()
        visit.write_text("own trial visit")
        launcher.copy_publication(self.source, self.state)
        self.assertEqual(visit.read_text(), "own trial visit")

    def test_04_changed_publication_requires_fresh_storage(self):
        launcher.copy_publication(self.source, self.state)
        (self.source / "bundle.json").write_text(json.dumps({**self.bundle, "version": 2}))
        with self.assertRaisesRegex(ValueError, "different publication"):
            launcher.copy_publication(self.source, self.state)

    def test_05_protected_demo_rejected(self):
        protected = self.source.with_name("dm_41513908")
        self.source.rename(protected)
        with self.assertRaisesRegex(ValueError, "protected"):
            launcher.copy_publication(protected, self.state)

    def test_06_unpublished_or_unpinned_rejected(self):
        for bundle in ({"runtime": {"version": 0}}, {"runtime": {"version": 1}}):
            (self.source / "bundle.json").write_text(json.dumps(bundle))
            with self.assertRaisesRegex(ValueError, "published"):
                launcher.copy_publication(self.source, self.state)

    def test_07_storage_cannot_contain_or_be_inside_source(self):
        for state in (self.source, self.source / "trial", self.source.parent):
            with self.assertRaisesRegex(ValueError, "separate"):
                launcher.copy_publication(self.source, state)

    def test_08_symlink_asset_rejected_and_partial_copy_removed(self):
        (self.source / "audio").symlink_to(self.source.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            launcher.copy_publication(self.source, self.state)
        self.assertFalse((self.state / "data/dm_fixture.copying").exists())
        self.assertTrue((self.source / "bundle.json").is_file())

    def test_09_state_cannot_link_back_to_original(self):
        self.state.mkdir()
        (self.state / "data").symlink_to(self.source.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "own storage"):
            launcher.copy_publication(self.source, self.state)

    def test_10_destination_cannot_link_back_to_original(self):
        (self.state / "data").mkdir(parents=True)
        (self.state / "data/dm_fixture").symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "own storage"):
            launcher.copy_publication(self.source, self.state)

    def test_11_protected_duplicate_and_privileged_ports_rejected_before_bind(self):
        with patch.object(socket, "socket") as factory:
            for ports in ([8920, 8896, 7882], [8920, 8920, 7882], [8920, 7880, 80]):
                with self.assertRaises(ValueError):
                    launcher.check_ports(ports)
            factory.assert_not_called()

    def test_12_checks_only_loopback_and_correct_protocol(self):
        with patch.object(socket, "socket") as factory:
            launcher.check_ports([8920, 7880, 7882])
            self.assertEqual([call.args for call in factory.call_args_list], [(socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET, socket.SOCK_DGRAM)])
            self.assertEqual([call.args[0] for call in factory.return_value.__enter__.return_value.bind.call_args_list], [("127.0.0.1", 8920), ("127.0.0.1", 7880), ("127.0.0.1", 7882)])

    def test_13_config_avoids_public_stun_and_wildcard_tcp(self):
        config = launcher.config_text("trial_key", "fixture_secret", 7880, 7882)
        self.assertIn("bind_addresses: [127.0.0.1]", config)
        self.assertIn("tcp_port: 0", config)
        self.assertIn("stun_servers: [127.0.0.1:7882]", config)
        self.assertIn("use_external_ip: false", config)
        self.assertIn("includes: [127.0.0.1/32]", config)

    def test_14_mock_network_guard_blocks_dns_tcp_and_udp(self):
        guard_spec = importlib.util.spec_from_file_location("trial_server", Path(__file__).resolve().parents[1] / "scripts/livekit_trial_server.py")
        guard = importlib.util.module_from_spec(guard_spec)
        guard_spec.loader.exec_module(guard)
        with ExitStack() as restore:
            for target, name in ((socket, "getaddrinfo"), (socket.socket, "connect"), (socket.socket, "connect_ex"), (socket.socket, "sendto")):
                restore.enter_context(patch.object(target, name, getattr(target, name)))
            guard.install_socket_guard()
            with self.assertRaisesRegex(OSError, "disabled"):
                socket.getaddrinfo("example.com", 443)
            with socket.socket() as sock:
                for method in (sock.connect, sock.connect_ex):
                    with self.assertRaisesRegex(OSError, "disabled"):
                        method(("1.1.1.1", 443))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                with self.assertRaisesRegex(OSError, "disabled"):
                    sock.sendto(b"blocked", ("1.1.1.1", 53))
            self.assertTrue(socket.getaddrinfo("127.0.0.1", 7880))
            left, right = socket.socketpair()
            try:
                left.send(b"local")
                self.assertEqual(right.recv(5), b"local")
            finally:
                left.close()
                right.close()

    def test_15_rtc_address_must_be_private_and_owned(self):
        with patch.object(socket, "socket") as factory:
            for host in ("127.0.0.1", "0.0.0.0", "1.1.1.1", "224.0.0.1", "169.254.1.1", "::1"):
                with self.assertRaises(ValueError):
                    launcher.validate_rtc_host(host)
            factory.assert_not_called()
            self.assertEqual(launcher.validate_rtc_host("192.168.12.34"), "192.168.12.34")
            factory.return_value.__enter__.return_value.bind.assert_called_once_with(("192.168.12.34", 0))
            factory.return_value.__enter__.return_value.bind.side_effect = OSError("not local")
            with self.assertRaises(OSError):
                launcher.validate_rtc_host("192.168.12.35")

    def test_16_private_rtc_does_not_expand_signaling_bind_or_stun(self):
        config = launcher.config_text("trial", "fixture", 7880, 7882, "192.168.12.34")
        self.assertIn("node_ip: 192.168.12.34", config)
        self.assertIn("includes: [192.168.12.34/32]", config)
        self.assertIn("bind_addresses: [127.0.0.1]", config)
        self.assertIn("stun_servers: [127.0.0.1:7882]", config)
        with patch.object(socket, "socket") as factory:
            launcher.check_ports([8920, 7880, 7882], "192.168.12.34")
            self.assertEqual([call.args[0] for call in factory.return_value.__enter__.return_value.bind.call_args_list], [("127.0.0.1", 8920), ("127.0.0.1", 7880), ("192.168.12.34", 7882)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
