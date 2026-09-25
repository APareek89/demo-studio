"""Read-only post-release identity, bytes, public routes and no-input WSS probe."""
import asyncio
import hashlib
import json
import urllib.error
import urllib.request
from release_common import *

BASE = 'https://13-202-0-79.sslip.io'
checks = []
def check(name, ok, **details):
    checks.append({'name': name, 'passed': bool(ok), **details})
    assert ok, name
def get(path, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=headers or {}), timeout=30) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, b'', {}

check('Correct source release active', state('WorkingDirectory') == str(RELEASE) and state('ActiveState') == 'active')
check('All committed source bytes match', verify_source() == json.loads((RECEIPT / 'stage-verified.json').read_text())['source_files'])
preflight = json.loads((RECEIPT / 'preflight.json').read_text())
check('Shared environment unchanged', sha(ENV) == preflight['environment_sha256'])
check('Caddy unchanged', run('sudo', 'sha256sum', CADDY).stdout.split()[0] == preflight['caddy_sha256'])
check('Caddy active', run('systemctl', 'is-active', 'caddy').stdout.strip() == 'active')
status, body, _ = get('/api/health')
health = json.loads(body)
check('Public health uses real providers', status == 200 and health.get('mock') is False)
status, _, _ = get('/')
check('Public shell loads', status == 200)
web = {path: digest for path, digest in source_manifest().items() if path.startswith('web/')}
web_results = []
for path, digest in web.items():
    status, body, _ = get('/' + path)
    web_results.append({'path': path, 'matched': status == 200 and hashlib.sha256(body).hexdigest() == digest})
check('Every frontend file matches source', all(row['matched'] for row in web_results), files=len(web_results))
status, body, _ = get('/api/demos/dm_29df0418/bundle')
expected = json.loads((DATA / 'demos/dm_29df0418/bundle.json').read_text())
check('Published BMW bundle retained', status == 200 and json.loads(body) == expected)
for path in ('/api/demos', '/api/demos/dm_29df0418/sessions', '/api/demos/dm_29df0418/trace',
             '/media/dm_29df0418/demo.json', '/media/dm_29df0418/knowledge/published.json', '/openapi.json'):
    status, _, _ = get(path)
    check('Private path still needs operator login: ' + path, status == 401)
async def probe():
    import websockets
    async with websockets.connect(BASE.replace('https:', 'wss:') + '/api/demos/dm_29df0418/run/live?session_id=s_release_runtime_gallery_probe',
                                  origin=BASE, open_timeout=20) as ws:
        await ws.send(json.dumps({'type': 'session.start', 'session_id': 's_release_runtime_gallery_probe',
                                 'language': 'en-IN', 'input_mode': 'text', 'mic': False}))
        event = json.loads(await asyncio.wait_for(ws.recv(), 10))
        check('Existing live transport handshakes without provider input',
              event.get('type') == 'session.ready' and event.get('microphone') is False and event.get('input_mode') == 'text')
asyncio.run(probe())
before = json.loads((RECEIPT / 'data.before.json').read_text())
after = data_manifest()
missing = sorted(set(before) - set(after))
changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
added = sorted(set(after) - set(before))
check('Read-only deployment checks preserve all demo files', set(missing + changed + added) <= SQLITE)
save('public-verification.json', {'commit': package()['commit'], 'passed': len(checks), 'total': len(checks),
     'checks': checks, 'web_files': web_results, 'paid_calls': 0, 'data_missing': missing,
     'data_changed': changed, 'data_added': added, 'transport': 'existing_websocket', 'livekit_adopted': False})
print(json.dumps({'passed': len(checks), 'total': len(checks), 'frontend_files': len(web), 'paid_calls': 0}))
