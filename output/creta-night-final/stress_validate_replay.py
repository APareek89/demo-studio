"""Pure validator replay of explicit captured/agent-authored decisions; zero API.

Input schema: {decisions:[{id,question,customer_text,requested_scope,evidence,
decision,provenance, expected?:{contains:[], excludes:[], answered:bool}}]}.
No decision is reconstructed from the final spoken answer. An agent-authored
decision is never renamed a captured provider output or a new live result.
"""
import argparse, copy, hashlib, json, os, socket, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
network_attempts=[]
def blocked(*a,**kw):network_attempts.append(True);raise AssertionError('Offline replay forbids outbound network')
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local')
TEMP=tempfile.TemporaryDirectory(prefix='creta-stress-validator-')
os.environ['DEMO_STUDIO_DATA']=str(Path(TEMP.name)/'demos')
os.environ['DEMO_STUDIO_GRAPH_DB']=str(Path(TEMP.name)/'graph.sqlite')
from server.runtime_graph import validate_decision

SNAPSHOT=ROOT/'data/demos/dm_41513908/knowledge/snapshots/kb_2d616ba1bcec1469e8c7ab40.json'
EXPECTED_SNAPSHOT_SHA='fa8bfa54b9c1fd23e0f042b76d89b49efb35fc3b50f4ad04817f4856925f33fc'
DYNAMIC=('applicability_projection','runtime_variant_boundary','entity','competition')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def replay(path):
    if sha(SNAPSHOT)!=EXPECTED_SNAPSHOT_SHA:raise RuntimeError('Pinned source snapshot changed')
    registry={f['id']:f for f in json.loads(SNAPSHOT.read_text())['facts']}
    payload=json.loads(path.read_text());rows=[]
    for c in payload['decisions']:
        if c.get('provenance') not in {'captured_original_provider_decision','offline_agent_authored_decision'}:raise ValueError('Every decision needs explicit provenance')
        if c['provenance']=='captured_original_provider_decision' and not c.get('raw_trace_row_sha256'):raise ValueError('Captured decisions require original trace-row hash')
        if c['decision'].get('action') not in {'answer','clarify'}:raise ValueError('This pure validator runner takes answer/clarify decisions only; audited tools must already be present as captured evidence, never silently executed')
        evidence=[]
        for f in c['evidence']:
            fact=copy.deepcopy(registry.get(f['id'],f))
            if f['id'] in registry:fact.update({k:copy.deepcopy(f[k]) for k in DYNAMIC if k in f})
            evidence.append(fact)
        feedback=[];limits=[]
        result,errors=validate_decision(c['decision'],evidence,c['question'],c.get('customer_text',''),c.get('requested_scope'),row_feedback=feedback,validated_limits=limits)
        checks=[];expect=c.get('expected',{})
        for text in expect.get('contains',[]):checks.append({'contains':text,'passed':text in result['answer']})
        for text in expect.get('excludes',[]):checks.append({'excludes':text,'passed':text not in result['answer']})
        if 'answered' in expect:checks.append({'answered':expect['answered'],'passed':result['answered'] is expect['answered']})
        rows.append({'id':c['id'],'provenance':c['provenance'],'question':c['question'],'decision':c['decision'],'result':result,'errors':errors,'feedback':feedback,'validated_limits':limits,'checks':checks,'semantic_quality_not_inferred_from_flag':True})
    return {'mode':'offline_pure_validator_replay','input_sha256':sha(path),'snapshot_id':SNAPSHOT.stem,'snapshot_sha256':sha(SNAPSHOT),'graph_sha256':sha(ROOT/'server/runtime_graph.py'),'outbound_socket_attempts':len(network_attempts),'rows':rows,'counts':{'decisions':len(rows),'assertions':sum(len(r['checks']) for r in rows),'failed_assertions':sum(not x['passed'] for r in rows for x in r['checks'])},'boundary':'Deterministic validator behavior only. No new LLM/source/voice call or customer session write. Independent semantic adjudication remains necessary.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Refuse to overwrite a prior replay')
    result=replay(args.input);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['counts']));print('OUTBOUND_SOCKET_ATTEMPTS='+str(len(network_attempts)))
    raise SystemExit(1 if result['counts']['failed_assertions'] or network_attempts else 0)
