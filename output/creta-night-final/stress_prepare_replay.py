"""Prepare immutable, explicitly offline review inputs from ONE captured session.

Reads local artifacts only. Never calls a model, fetches a URL, writes app data,
or silently turns a missing/cancelled live answer into a synthetic success.
"""
import argparse, ast, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_new(path,value):
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.exists() and path.read_text()!=text:raise RuntimeError(f'Immutable replay artifact already exists: {path}')
    if not path.exists():path.write_text(text)

def prepare(directory):
    directory=Path(directory);events_path=directory/'stress-events.jsonl';result_path=directory/'stress-browser-result.json'
    events=[json.loads(line) for line in events_path.read_text().splitlines()]
    result=json.loads(result_path.read_text());provenance=json.loads((directory/'stress-provenance.json').read_text())
    if provenance['mode']!='live_caption_only':raise ValueError('An initial synthetic harness run is not a captured live session')
    requests=[r for r in events if r['kind']=='client_message' and r['body'].get('type')=='turn.ask']
    replies={r['body']['turn_id']:r for r in events if r['kind']=='live_turn_result'}
    cases=[]
    for index,row in enumerate(requests,1):
        payload=row['body'];reply=replies.get(payload['turn_id'])
        cases.append({'index':index,'session_id':payload['session_id'],'turn_id':payload['turn_id'],'request_at_ms':row['at_ms'],'request':payload,
            'result_at_ms':reply['at_ms'] if reply else None,'result':reply['body']['answer'] if reply else None,
            'status':'captured_live_result' if reply else 'no_live_result_captured_do_not_invent',
            'delay_ms':reply['at_ms']-row['at_ms'] if reply else None})
    pitch_requests=[r for r in events if r['kind']=='http_request' and r['path'].endswith('/run/pitch')]
    pitch_results=[r for r in events if r['kind']=='http_result' and r['path'].endswith('/run/pitch')]
    fixture={'mode':'offline_exact_session_replay_inputs','not_new_live_api_results':True,'source_session_id':result['session_id'],
        'source_artifact_hashes':{p.name:sha(p) for p in [events_path,result_path,directory/'stress-provenance.json']},'provenance':provenance,
        'qa':cases,'pitch':[{'request':r['body'],'result':pitch_results[i]['body'] if i<len(pitch_results) else None} for i,r in enumerate(pitch_requests)],
        'persisted_session':result.get('persisted_session'),'checks':result['checks'],'issues':result['issues'],
        'instructions':'Replay each ordered request against its captured result. Missing/cancelled results remain missing. Agent-proposed corrected outputs are a separate fixture namespace and never counted as paid/live responses. Do not execute providers, source fetch, TTS/STT, summary regeneration or writes to customer session storage.'}
    write_new(directory/'stress-runtime-replay.json',fixture)
    return fixture

def system_snapshot():
    graph=ROOT/'server/runtime_graph.py';tree=ast.parse(graph.read_text())
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in node.targets))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path,nargs='?');parser.add_argument('--snapshot-system',action='store_true');args=parser.parse_args()
    if args.snapshot_system:
        path=Path(__file__).with_name('stress-runtime-system.txt');text=system_snapshot()+'\n'
        if path.exists() and path.read_text()!=text:raise RuntimeError('System changed: preserve prior snapshot and create a dated version explicitly')
        path.write_text(text);print(json.dumps({'system_sha256':sha(path),'source_graph_sha256':sha(ROOT/'server/runtime_graph.py')}))
    if args.directory:
        fixture=prepare(args.directory);print(json.dumps({'session_id':fixture['source_session_id'],'captured_requests':len(fixture['qa']),'captured_results':sum(x['result'] is not None for x in fixture['qa'])}))
