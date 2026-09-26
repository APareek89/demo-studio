"""Finite local-only contracts for the one-file CSS overlay; no network or live files."""
import contextlib
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('css_patch', Path(__file__).with_name('static_css_patch.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
BASE = subprocess.check_output(['git', 'show', p.BASE_COMMIT + ':' + p.RELATIVE])
assert p.digest(BASE) == p.BASE_DIGEST
checks = []


def check(name, value):
    assert value, name
    checks.append(name); print('PASS ' + name)


@contextlib.contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='css-overlay-contract-') as temp:
        root = Path(temp); release = root / 'release'; receipt = root / 'receipt'; package = root / 'package'
        (release / 'web').mkdir(parents=True); receipt.mkdir(); package.mkdir()
        (release / 'SOURCE_COMMIT').write_text(p.BASE_COMMIT + '\n')
        (release / p.RELATIVE).write_bytes(BASE); (release / p.RELATIVE).chmod(0o644)
        (release / 'retained.py').write_text('retained source\n')
        manifest = {p.RELATIVE: p.BASE_DIGEST, 'retained.py': p.digest((release / 'retained.py').read_bytes())}
        (receipt / 'source-manifest.json').write_text(json.dumps(manifest))
        new = BASE + b'\n/* local overlay fixture */\n'
        info = {'base_commit': p.BASE_COMMIT, 'new_commit': 'a' * 40, 'path': p.RELATIVE,
                'old_sha256': p.BASE_DIGEST, 'new_sha256': p.digest(new)}
        (package / 'overlay.json').write_text(json.dumps(info)); (package / 'player-ui.css').write_bytes(new)
        yield release, receipt, package, info, lambda: (release / p.RELATIVE).read_bytes()


def rejected(action):
    try: action()
    except (AssertionError, FileExistsError): return True
    return False


with fixture() as (r, b, k, i, get):
    result = p.apply(k, r, b, get); verified = p.verify(r, b, i, get)
    check('atomically installs exact CSS and verifies all remaining source', verified['verified_source_files'] == 2 and get() == (k / 'player-ui.css').read_bytes())
    check('preserves original CSS mode and base source marker', (r / p.RELATIVE).stat().st_mode & 0o777 == 0o644 and (r / 'SOURCE_COMMIT').read_text().strip() == p.BASE_COMMIT)
    private = Path(result['receipt'])
    check('private backup and overlay truth retain both versions', (private / 'player-ui.css.before').read_bytes() == BASE and (private / 'player-ui.css.before').stat().st_mode & 0o777 == 0o600 and json.loads((r / 'SOURCE_OVERLAY.json').read_text()) == i)
    check('rejects duplicate overlay without disturbing installed bytes', rejected(lambda:p.apply(k,r,b,get)) and get() != BASE)
    p.rollback(r, private, i, get)
    check('explicit rollback restores original bytes and removes own overlay marker', get() == BASE and not (r / 'SOURCE_OVERLAY.json').exists())

for name, mutate in [
    ('rejects an unallowlisted file path', lambda r,b,k,i: (i.update(path='web/player/player.js'), (k / 'overlay.json').write_text(json.dumps(i)))),
    ('rejects wrong base source marker', lambda r,b,k,i: (r / 'SOURCE_COMMIT').write_text('b' * 40)),
    ('rejects modified current CSS', lambda r,b,k,i: (r / p.RELATIVE).write_text('unexpected')),
    ('rejects altered new CSS payload', lambda r,b,k,i: (k / 'player-ui.css').write_text('unexpected')),
    ('rejects unrelated base source drift before writing CSS', lambda r,b,k,i: (r / 'retained.py').write_text('unexpected')),
    ('rejects original manifest disagreement', lambda r,b,k,i: (b / 'source-manifest.json').write_text(json.dumps({p.RELATIVE:'0'*64}))),
]:
    with fixture() as (r,b,k,i,get):
        mutate(r,b,k,i);before=get()
        check(name,rejected(lambda:p.apply(k,r,b,get)) and get()==before and not (r/'SOURCE_OVERLAY.json').exists())

with fixture() as (r,b,k,i,get):
    original=r/'original.css';(r/p.RELATIVE).rename(original);(r/p.RELATIVE).symlink_to(original)
    check('rejects symlink target without touching linked bytes',rejected(lambda:p.apply(k,r,b,get)) and original.read_bytes()==BASE)

with fixture() as (r,b,k,i,get):
    calls=[]
    def mismatch():
        calls.append(1);return b'wrong response' if len(calls)==1 else get()
    check('HTTP mismatch triggers rollback and independently rechecks public CSS',rejected(lambda:p.apply(k,r,b,mismatch)) and get()==BASE and len(calls)==2 and not (r/'SOURCE_OVERLAY.json').exists())

with fixture() as (r,b,k,i,get):
    calls=[];previous=signal.signal(signal.SIGTERM,p.terminate)
    def terminate_once():
        calls.append(1)
        if len(calls)==1:signal.raise_signal(signal.SIGTERM)
        return get()
    try:
        terminated=False
        try:p.apply(k,r,b,terminate_once)
        except SystemExit:terminated=True
        check('actual SIGTERM during verification restores CSS before propagating',terminated and get()==BASE and len(calls)==2 and not (r/'SOURCE_OVERLAY.json').exists())
    finally:signal.signal(signal.SIGTERM,previous)

with fixture() as (r,b,k,i,get):
    result=p.apply(k,r,b,get);(r/'retained.py').write_text('unreviewed')
    check('overlay-aware verification rejects unrelated source drift',rejected(lambda:p.verify(r,b,i,get)))

print('Static CSS overlay: '+str(len(checks))+'/'+str(len(checks)))
