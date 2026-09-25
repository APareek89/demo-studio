"""Run finite free release gates on extracted source, isolated from production."""
import json
import os
import subprocess
import time
from release_common import RECEIPT, RELEASE, RUNTIME, PYTHON, package, sha, save, verify_source

SUITES = ['qa_deck', 'qa_accept', 'smoke_mock', 'release_mock_contract',
          'knowledge_contract', 'retrieval_io_contract', 'runtime_visuals_contract',
          'runtime_graph_contract', 'runtime_repair_contract', 'runtime_delivery_contract',
          'runtime_hedge_contract', 'runtime_hedge_config_contract', 'runtime_operational_failure_contract',
          'runtime_domain_contract', 'runtime_customer_sites_contract', 'runtime_web_search_contract',
          'runtime_live_table_contract', 'runtime_transmission_conditions_contract',
          'faq_cache_contract', 'live_transport_contract', 'sarvam_stream_contract',
          'session_checkpoint_contract', 'session_input_mode_contract', 'explore_cancellation_contract',
          'speech_style_contract', 'voice_lock_contract', 'livekit_trial_contract']

WRAPPER = '''import os, runpy, socket, sys, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory(prefix="runtime-release-stage-") as d:
 os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", MODEL_TIER="eval", DEMO_STUDIO_DATA=d+"/demos", DEMO_STUDIO_GRAPH_DB=d+"/graph.sqlite", SHARE_SECRET="isolated-mock-only", ANTHROPIC_API_KEY="", GEMINI_API_KEY="", RUNWARE_API_KEY="", GCLOUD_TTS_API_KEY="", SARVAM_API_KEY="", AWS_EC2_METADATA_DISABLED="true", LIVEKIT_TRIAL_ENABLED="0", LIVEKIT_URL="", LIVEKIT_API_KEY="", LIVEKIT_API_SECRET="")
 attempts=[]
 def blocked(*args,**kwargs):
  attempts.append(True)
  raise AssertionError("Staged validation forbids outbound sockets")
 socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=socket.create_connection=socket.getaddrinfo=blocked
 target=sys.argv[1];sys.argv=[target];sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/"evals")]
 try: runpy.run_path(target,run_name="__main__")
 finally:
  print("STAGED_OUTBOUND_ATTEMPTS",len(attempts),flush=True)
  assert not attempts
'''

os.umask(0o077)
count = verify_source()
assert all((RELEASE / 'evals' / (suite + '.py')).is_file() for suite in SUITES)
marker = RECEIPT / 'staged-gates.ok.json'
assert not marker.exists(), 'Do not reuse a prior successful staging marker'
env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(RUNTIME / 'browser-cache'))
results = []
for suite in SUITES:
    started = time.monotonic()
    with (RECEIPT / (suite + '.log')).open('w') as log:
        result = subprocess.run([str(PYTHON), '-c', WRAPPER, 'evals/' + suite + '.py'],
                                cwd=RELEASE, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    row = {'suite': suite, 'exit_code': result.returncode, 'seconds': round(time.monotonic()-started, 2),
           'log_sha256': sha(RECEIPT / (suite + '.log'))}
    results.append(row)
    save('staged-gates.json', results)
    print(json.dumps(row), flush=True)
    if result.returncode:
        print('Gate failed; inspect the named private receipt log.', flush=True)
        raise SystemExit(result.returncode)
assert verify_source() == count
save('staged-gates.ok.json', {'commit': package()['commit'],
     'source_manifest_sha256': sha(RECEIPT / 'source-manifest.json'),
     'suites': SUITES, 'passed': len(results), 'total': len(SUITES),
     'mock': True, 'isolated': True, 'outbound_attempts': 0,
     'results_sha256': sha(RECEIPT / 'staged-gates.json')})
