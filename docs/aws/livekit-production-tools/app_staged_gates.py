"""Run isolated, socket-blocked application release gates; preserve every attempt."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from app_common import RECEIPT, RELEASE, RUNTIME, PYTHON, package, sha, save, verify_source

PY_SUITES = ['qa_deck', 'qa_accept', 'smoke_mock', 'release_mock_contract',
 'knowledge_contract', 'retrieval_io_contract', 'runtime_visuals_contract',
 'runtime_graph_contract', 'runtime_repair_contract', 'runtime_delivery_contract',
 'runtime_hedge_contract', 'runtime_hedge_config_contract', 'runtime_operational_failure_contract',
 'runtime_domain_contract', 'runtime_customer_sites_contract', 'runtime_web_search_contract',
 'runtime_live_table_contract', 'runtime_transmission_conditions_contract',
 'faq_cache_contract', 'live_transport_contract', 'sarvam_stream_contract',
 'session_checkpoint_contract', 'session_input_mode_contract', 'explore_cancellation_contract',
 'speech_style_contract', 'voice_lock_contract', 'livekit_trial_contract',
 'livekit_hosted_contract', 'livekit_launcher_contract', 'local_launcher_contract']
JS_SUITES = ['live_voice_contract', 'livekit_voice_contract', 'voice_transport_contract', 'question_ack_contract']

WRAPPER = 'import ipaddress, os, runpy, socket, sys, tempfile\nfrom pathlib import Path\nwith tempfile.TemporaryDirectory(prefix="livekit-release-stage-") as d:\n os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", MODEL_TIER="eval", DEMO_STUDIO_DATA=d+"/demos", DEMO_STUDIO_GRAPH_DB=d+"/graph.sqlite", SHARE_SECRET="isolated-mock-only", ANTHROPIC_API_KEY="", GEMINI_API_KEY="", RUNWARE_API_KEY="", GCLOUD_TTS_API_KEY="", SARVAM_API_KEY="", AWS_EC2_METADATA_DISABLED="true", LIVEKIT_ENABLED="0", LIVEKIT_TRIAL_ENABLED="0", LIVEKIT_ALLOWED_ORIGINS="", LIVEKIT_INTERNAL_URL="", LIVEKIT_URL="", LIVEKIT_API_KEY="", LIVEKIT_API_SECRET="")\n attempts=[]\n def blocked(*args,**kwargs):\n  attempts.append(True)\n  raise AssertionError("Staged validation forbids outbound sockets")\n # Numeric IP parsing performs no DNS/network I/O; SSRF tests need its real result.\n native_getaddrinfo=socket.getaddrinfo\n def numeric_only(host, port, family=0, type=0, proto=0, flags=0):\n  try: ipaddress.ip_address(host)\n  except (ValueError, TypeError): return blocked()\n  return native_getaddrinfo(host,port,family,type,proto,flags | socket.AI_NUMERICHOST)\n socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=socket.create_connection=blocked\n socket.getaddrinfo=numeric_only\n target=sys.argv[1];sys.argv=[target];sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/"evals")]\n try: runpy.run_path(target,run_name="__main__")\n finally:\n  print("STAGED_OUTBOUND_ATTEMPTS",len(attempts),flush=True)\n  assert not attempts\n'

NODE_GUARD = r"""let attempts=0;
function blocked(){attempts++;throw new Error('Staged validation forbids outbound sockets');}
for(const name of ['node:net','node:tls','node:http','node:https']){
 const mod=require(name);for(const key of ['connect','createConnection','request','get'])if(typeof mod[key]==='function')mod[key]=blocked;
 if(mod.Socket?.prototype)mod.Socket.prototype.connect=blocked;
}
for(const mod of [require('node:dns'),require('node:dns').promises])for(const key of Object.keys(mod))if(key==='lookup'||key==='lookupService'||key.startsWith('resolve'))mod[key]=blocked;
const dgram=require('node:dgram');dgram.Socket.prototype.send=blocked;dgram.Socket.prototype.connect=blocked;
globalThis.fetch=blocked;globalThis.WebSocket=class{constructor(){blocked();}};
process.on('exit',()=>{console.log('STAGED_OUTBOUND_ATTEMPTS',attempts);if(attempts)process.exitCode=1;});
"""


def main():
    os.umask(0o077)
    count = verify_source()
    assert not (RELEASE / '.env').exists() and not (RELEASE / 'data').exists(), 'Stage before shared links or cutover'
    assert not (RECEIPT / 'app-staged-gates.ok.json').exists(), 'Do not overwrite successful staging proof'
    suites = [('python', s, 'py') for s in PY_SUITES] + [('node', s, 'mjs') for s in JS_SUITES]
    assert all((RELEASE / 'evals' / (s + '.' + suffix)).is_file() for _, s, suffix in suites)
    attempt = RECEIPT / ('app-gates-' + time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + str(time.time_ns() % 1000000000))
    attempt.mkdir(mode=0o700)
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(RUNTIME / 'browser-cache'))
    node = shutil.which('node', path=env.get('PATH'))
    if not node:
        found = subprocess.run([str(PYTHON), '-c', 'import pathlib,playwright;print(pathlib.Path(playwright.__file__).parent/"driver/node")'], check=True, text=True, capture_output=True)
        node = found.stdout.strip()
        assert Path(node).is_file(), 'Parser parity requires Playwright bundled Node'
        env['PATH'] = str(Path(node).parent) + os.pathsep + env.get('PATH', '')
    guard = attempt / 'node-network-guard.cjs'
    guard.write_text(NODE_GUARD)
    results = []
    for kind, suite, suffix in suites:
        started = time.monotonic()
        log_path = attempt / (suite + '.log')
        command = [str(PYTHON), '-c', WRAPPER, 'evals/' + suite + '.py'] if kind == 'python' else [node, '--require', str(guard), 'evals/' + suite + '.mjs']
        with log_path.open('w') as log:
            try:
                result = subprocess.run(command, cwd=RELEASE, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        row = {'suite': suite, 'kind': kind, 'exit_code': code, 'seconds': round(time.monotonic()-started, 2),
               'log': str(log_path.relative_to(RECEIPT)), 'log_sha256': sha(log_path)}
        results.append(row)
        save(str(attempt.relative_to(RECEIPT) / ('progress-' + str(len(results)) + '.json')), results)
        print(json.dumps(row), flush=True)
        assert code == 0, 'Gate failed; preserve this attempt and inspect its private log'
        assert 'STAGED_OUTBOUND_ATTEMPTS 0' in log_path.read_text(), 'Missing zero-outbound gate proof'
    assert verify_source() == count
    result_name = str(attempt.relative_to(RECEIPT) / 'results.json')
    save(result_name, results)
    save('app-staged-gates.ok.json', {'commit': package()['commit'],
         'source_manifest_sha256': sha(RECEIPT / 'source-manifest.json'),
         'suites': [s for _, s, _ in suites], 'passed': len(results), 'total': len(suites),
         'mock': True, 'isolated': True, 'outbound_attempts': 0,
         'results': result_name, 'results_sha256': sha(RECEIPT / result_name)})


if __name__ == '__main__':
    main()
