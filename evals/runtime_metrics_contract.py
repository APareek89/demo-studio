"""Success latency cannot hide failures or mix endpoint receipts with voice estimates."""
import sys
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.runtime_metrics import aggregate,percentile,response_kind

base={"answered":True,"response_kind":"answer","voice_ended":1000,"answer_audio":3000,"endpoint_received_at":1700,"delivery_done":7000,"input_source":"realtime","speech_end_basis":"local_vad_estimate","answer_route":"model"}
rows=[base,{**base,"answer_audio":1001,"failed":True},{**base,"answer_audio":1002,"cancelled":True},{**base,"answer_audio":None},{**base,"speech_end_basis":"provider_endpoint_receipt","answer_audio":1500}]
backend=Mock();backend.iter_sessions.return_value=[{"version":1,"voice_provider":"sarvam","turns":rows,"interruptions":[{"detected_at":1000,"stopped_at":1030}]}]
with patch('server.runtime_metrics.storage.backend',return_value=backend):
 result=aggregate('demo')
groups={(c['speech_end_basis'],c['response_kind']):c for c in result['cohorts']};c=groups[('local_vad_estimate','answer')]
checks={
 'timing bases are separate':len(groups)==2,
 'failed and cancelled fast replies excluded':c['p50_ms']==2000 and c['complete_timings']==1,
 'failure cancellation missing remain visible':c['failed']==1 and c['cancelled']==1 and c['missing_timings']==1,
 'endpoint and completion measured separately':c['endpoint_delay_p50_ms']==700 and c['completion_p50_ms']==6000,
 'small samples labelled':c['small_sample'],
 'interruption basis is local stop request':result['interruption']['p95_ms']==30 and 'request' in result['interruption']['basis'],
 'empty sample is unavailable not zero':percentile([], .95) is None,
}

# A very fast spoken decline or clarification must not improve factual-answer timing.
legacy={k:v for k,v in base.items() if k not in ('answered','response_kind')}
extra=[{**base,'answered':False,'response_kind':'decline','answer_audio':1001}, {**base,'answered':False,'response_kind':'clarification','answer_audio':1100}, {**legacy,'answer_audio':1200}]
backend.iter_sessions.return_value=[{'version':1,'provider':'sarvam','turns':[base,*extra]}]
with patch('server.runtime_metrics.storage.backend',return_value=backend):
 separated=aggregate('demo')
by_kind={c['response_kind']:c for c in separated['cohorts']}
checks.update({
 'substantive answer alone determines useful-answer timing':by_kind['answer']['p50_ms']==2000 and by_kind['answer']['useful_answer_timings']==1,
 'spoken decline count and measurement retained but latency excluded':by_kind['decline']['declined']==1 and by_kind['decline']['measured_responses']==1 and by_kind['decline']['p50_ms'] is None,
 'clarification is labelled separately with no answer completion claim':by_kind['clarification']['p50_ms']==100 and by_kind['clarification']['useful_answer_timings']==0 and by_kind['clarification']['completion_p50_ms'] is None,
 'legacy unclassified responses are not inferred as declines or useful answers':by_kind['legacy_all_responses']['p50_ms']==200 and by_kind['legacy_all_responses']['declined']==0 and by_kind['legacy_all_responses']['useful_answer_timings']==0,
 'legacy answered flag alone does not invent clarification or decline identity':response_kind({**legacy,'answered':False})=='legacy_all_responses',
 'actual player provider provenance retained':all(c['voice_provider']=='sarvam' for c in separated['cohorts']),
})
from server.app import _latency
with patch('server.app.storage.backend',return_value=backend):
 top=_latency('demo')
checks['dashboard useful-answer headline excludes clarification decline and legacy']=top['scope']=='useful_answers' and top['stages']['total']['p50']==2000 and top['eligible_turns']==1 and top['turns']==4
backend.iter_sessions.return_value=[{'turns':[legacy]}]
with patch('server.app.storage.backend',return_value=backend):
 old=_latency('demo')
checks['legacy-only headline is labelled all responses']=old['scope']=='legacy_all_responses' and old['stages']['total']['p50']==2000 and old['response_counts']['decline']==0

unlabelled={key:value for key,value in base.items() if key not in ('input_source','speech_end_basis')}
backend.iter_sessions.return_value=[
    {'input_mode':'voice','runtime_version':1,'turns':[{**base,'input_source':'typed'},unlabelled]},
    {'input_mode':'text','turns':[unlabelled]},
    {'input_mode':'voice','runtime_version':0,'turns':[unlabelled]},
    {'turns':[unlabelled]},
]
with patch('server.runtime_metrics.storage.backend',return_value=backend):
 mode_cohorts=aggregate('demo')['cohorts']
counts={source:sum(row['turns'] for row in mode_cohorts if row['input']==source) for source in ('typed','realtime','voice','unknown')}
checks.update({
 'typed turns in voice mode retain actual typed provenance':counts['typed']==2,
 'missing live turn source falls back to voice session mode':counts['realtime']==1,
 'legacy voice mode cannot invent realtime transport':counts['voice']==1,
 'missing historical mode stays unknown':counts['unknown']==1,
})

for name,ok in checks.items():print(('PASS ' if ok else 'FAIL ')+name)
assert all(checks.values())
print(f'{len(checks)}/{len(checks)} runtime metrics contracts passed')
