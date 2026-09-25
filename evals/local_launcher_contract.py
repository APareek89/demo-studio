"""Normal local workspace launcher; fake processes and no network/provider calls."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "scripts"))
spec=importlib.util.spec_from_file_location("local_launcher",ROOT / "scripts/run_local.py")
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
from run_livekit_trial import check_ports as real_check_ports


class LocalLauncher(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="normal-local-launcher-")
        self.root=Path(self.temp.name).resolve()
        self.data=self.root / "workspace/demos";self.data.mkdir(parents=True)
        (self.data / "existing.txt").write_bytes(b"existing publication and visits")
        self.graph=self.root / "workspace/graph.sqlite";self.graph.write_bytes(b"existing graph")
        self.state=self.root / "launcher"
        self.binary=self.root / "livekit-server";self.binary.write_bytes(b"fake server");self.binary.chmod(0o700)
        self.args=launcher.parser().parse_args(["--data",str(self.data),"--graph-db",str(self.graph),"--state-dir",str(self.state),"--livekit-server",str(self.binary),"--rtc-host","192.168.12.34"])
        self.blocks=ExitStack()
        for name in ("socket.create_connection","socket.getaddrinfo","socket.socket.connect","socket.socket.connect_ex","socket.socket.sendto"):
            self.blocks.enter_context(patch(name,side_effect=AssertionError("No launcher network calls")))

    def tearDown(self):
        self.blocks.close();self.temp.cleanup()

    def argv(self):
        return ["--data",str(self.data),"--graph-db",str(self.graph),"--state-dir",str(self.state),"--livekit-server",str(self.binary),"--rtc-host","192.168.12.34"]

    def mocked_main(self, *, spawn=None, stop=None):
        stack=ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(launcher,"require_runtime",return_value=self.binary))
        stack.enter_context(patch.object(launcher,"rtc_host",return_value="192.168.12.34"))
        ports=stack.enter_context(patch.object(launcher,"check_ports"))
        process=stack.enter_context(patch.object(launcher.subprocess,"Popen",side_effect=spawn))
        wait=stack.enter_context(patch.object(launcher,"wait_http"))
        stops=stack.enter_context(patch.object(launcher,"stop_owned",side_effect=stop))
        guard=stack.enter_context(patch.object(launcher,"install_socket_guard"))
        stack.enter_context(patch.object(launcher.time,"sleep",side_effect=KeyboardInterrupt))
        stack.enter_context(patch.object(launcher.signal,"signal"))
        output=stack.enter_context(patch("builtins.print"))
        return process,wait,stops,guard,ports,output

    def test_defaults_keep_normal_app_port_and_avoid_existing_trial_ports(self):
        with patch.dict(os.environ,{},clear=True):
            args=launcher.parser().parse_args([])
        self.assertEqual((args.port,args.signal_port,args.rtc_udp_port),(8910,7890,7892))
        self.assertEqual(args.data,ROOT / "data/demos")
        self.assertFalse(args.live_providers)

    def test_environment_paths_honored_and_graph_default_sits_beside_demos(self):
        with patch.dict(os.environ,{"DEMO_STUDIO_DATA":str(self.data),"DEMO_STUDIO_GRAPH_DB":str(self.graph)}):
            args=launcher.parser().parse_args(["--state-dir",str(self.state)])
        self.assertEqual(launcher.storage_paths(args),(self.state,self.data,self.graph))
        args.graph_db=None
        self.assertEqual(launcher.storage_paths(args)[2],self.data.parent / "graph.sqlite")

    def test_state_cannot_overlap_data_graph_repository_or_protected_demo(self):
        for state in (self.data,self.data / "local",self.data.parent,self.graph.parent,ROOT / "output/local",ROOT,self.root / "dm_41513908/local"):
            with self.subTest(state=state):
                self.args.state_dir=state
                with self.assertRaises(ValueError):launcher.storage_paths(self.args)
        self.args.state_dir=self.state
        self.args.data=self.root / "dm_41513908"
        with self.assertRaisesRegex(ValueError,"protected"):launcher.storage_paths(self.args)

    def test_state_symlink_and_parent_symlink_are_rejected(self):
        real=self.root / "real";real.mkdir()
        link=self.root / "redirect";link.symlink_to(real,target_is_directory=True)
        for path in (link,link / "child"):
            self.args.state_dir=path
            with self.assertRaisesRegex(ValueError,"symlinks"):launcher.storage_paths(self.args)

    def test_state_and_private_files_have_owner_only_permissions(self):
        launcher.prepare_state(self.state)
        with launcher.private_file(self.state,"livekit.private.yaml",truncate=True) as config:config.write(b"private config")
        self.assertEqual(self.state.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.state / "livekit.private.yaml").stat().st_mode & 0o777,0o600)

    def test_private_state_files_reject_symlink_and_hardlink_before_writing(self):
        launcher.prepare_state(self.state)
        linked=self.state / "livekit.private.yaml";linked.symlink_to(self.graph)
        with self.assertRaisesRegex(ValueError,"symlinks"):launcher.prepare_state(self.state)
        linked.unlink();os.link(self.graph,linked)
        with self.assertRaisesRegex(ValueError,"singly linked"):launcher.private_file(self.state,"livekit.private.yaml",truncate=True)
        self.assertEqual(self.graph.read_bytes(),b"existing graph")

    def test_mock_mode_overrides_inherited_hosted_and_provider_configuration(self):
        with patch.dict(os.environ,{"LIVEKIT_ENABLED":"1","LIVEKIT_INTERNAL_URL":"wss://private.example","GEMINI_API_KEY":"private-test-key","MODEL_TIER":"customer"}):
            env=launcher.application_environment(self.args,self.data,self.graph,"fake-secret")
        self.assertEqual((env["LIVEKIT_ENABLED"],env["LIVEKIT_TRIAL_ENABLED"],env["MOCK_LLM"]),("0","1","1"))
        self.assertEqual(env["LIVEKIT_INTERNAL_URL"],"")
        self.assertEqual(env["LIVEKIT_TRIAL_STUN_URL"],"stun:127.0.0.1:7892")
        self.assertTrue(all(env[key]=="" for key in launcher.KEYS))
        self.assertEqual((env["CLOUD_SYNC"],env["STORAGE_BACKEND"]),("0","local"))

    def test_live_mode_preserves_selected_provider_flags_and_workspace_paths(self):
        self.args.live_providers=True
        with patch.dict(os.environ,{"MODEL_TIER":"customer","BUILD_PROVIDERS":"runware,gemini,claude","GEMINI_API_KEY":"fixture-key"}):
            env=launcher.application_environment(self.args,self.data,self.graph,"fake-secret")
        self.assertEqual(env["MOCK_LLM"],"0")
        self.assertEqual(env["GEMINI_API_KEY"],"fixture-key")
        self.assertEqual(env["BUILD_PROVIDERS"],"runware,gemini,claude")
        self.assertEqual(env["MODEL_TIER"],"customer")
        self.assertEqual((env["DEMO_STUDIO_DATA"],env["DEMO_STUDIO_GRAPH_DB"]),(str(self.data),str(self.graph)))

    def test_mac_auto_detection_validates_en0_then_en1_without_public_probe(self):
        with patch.object(launcher.sys,"platform","darwin"),patch.object(launcher.subprocess,"run",side_effect=[subprocess.CalledProcessError(1,"ipconfig"),MagicMock(stdout="192.168.12.34\n")]) as run,patch.object(launcher,"validate_rtc_host",return_value="192.168.12.34") as validate:
            self.assertEqual(launcher.rtc_host(None),"192.168.12.34")
        self.assertEqual([call.args[0] for call in run.call_args_list],[["/usr/sbin/ipconfig","getifaddr","en0"],["/usr/sbin/ipconfig","getifaddr","en1"]])
        validate.assert_called_once_with("192.168.12.34")

    def test_linux_requires_explicit_private_host_and_never_discovers_via_internet(self):
        with patch.object(launcher.sys,"platform","linux"),patch.object(launcher.subprocess,"run") as run:
            with self.assertRaisesRegex(ValueError,"--rtc-host"):launcher.rtc_host(None)
            run.assert_not_called()
        with patch.object(launcher,"validate_rtc_host",return_value="192.168.12.34") as validate:
            self.assertEqual(launcher.rtc_host("192.168.12.34"),"192.168.12.34")
            validate.assert_called_once()

    def test_port_conflict_or_protected_port_never_stops_an_existing_process(self):
        process,wait,stops,guard,ports,output=self.mocked_main()
        ports.side_effect=OSError("Address already in use")
        with self.assertRaises(SystemExit):launcher.main(self.argv())
        process.assert_not_called();stops.assert_not_called()
        self.assertFalse(self.state.exists())
        with patch.object(socket,"socket") as factory:
            for values in ([8910,8896,7892],[8910,8910,7892],[80,7890,7892]):
                with self.assertRaises(ValueError):real_check_ports(values)
            factory.assert_not_called()

    def test_launcher_uses_workspace_without_copy_and_stops_only_its_children(self):
        first,second=MagicMock(),MagicMock()
        first.poll.return_value=second.poll.return_value=None
        process,wait,stops,guard,ports,output=self.mocked_main(spawn=[first,second])
        launcher.main(self.argv())
        self.assertEqual([call.args[0] for call in stops.call_args_list],[second,first])
        self.assertTrue(all(call.kwargs["start_new_session"] for call in process.call_args_list))
        app=process.call_args_list[1]
        self.assertEqual(app.kwargs["env"]["DEMO_STUDIO_DATA"],str(self.data))
        self.assertEqual(app.kwargs["env"]["DEMO_STUDIO_GRAPH_DB"],str(self.graph))
        guard.assert_called_once()
        self.assertEqual((self.data / "existing.txt").read_bytes(),b"existing publication and visits")
        self.assertEqual(self.graph.read_bytes(),b"existing graph")
        self.assertFalse((self.state / "data").exists())
        visible=" ".join(str(call.args) for call in output.call_args_list)
        self.assertIn("http://127.0.0.1:8910/",visible)
        self.assertNotIn("voice_transport=",visible)
        self.assertNotIn(app.kwargs["env"]["LIVEKIT_API_SECRET"],visible)

    def test_second_process_start_failure_stops_only_first_owned_child(self):
        first=MagicMock();first.poll.return_value=None
        process,wait,stops,guard,ports,output=self.mocked_main(spawn=[first,OSError("Cannot launch app")])
        with self.assertRaisesRegex(OSError,"Cannot launch app"):launcher.main(self.argv())
        stops.assert_called_once_with(first)

    def test_exclusive_state_lock_does_not_overwrite_running_configuration(self):
        launcher.prepare_state(self.state)
        config=self.state / "livekit.private.yaml";config.write_bytes(b"running configuration")
        process,wait,stops,guard,ports,output=self.mocked_main()
        with launcher.private_file(self.state,"launcher.lock") as lock:
            launcher.fcntl.flock(lock,launcher.fcntl.LOCK_EX|launcher.fcntl.LOCK_NB)
            with self.assertRaises(SystemExit):launcher.main(self.argv())
        self.assertEqual(config.read_bytes(),b"running configuration")
        process.assert_not_called();stops.assert_not_called()

    def test_cleanup_attempts_both_owned_children_despite_exit_race(self):
        first,second=MagicMock(),MagicMock();first.poll.return_value=second.poll.return_value=None
        process,wait,stops,guard,ports,output=self.mocked_main(spawn=[first,second],stop=[ProcessLookupError(),None])
        launcher.main(self.argv())
        self.assertEqual([call.args[0] for call in stops.call_args_list],[second,first])


if __name__=="__main__":unittest.main(verbosity=2)
