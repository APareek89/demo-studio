"""Success latency cannot hide failures or mix endpoint receipts with voice estimates."""
import sys
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.runtime_metrics import aggregate,percentile

base={"voice_ended":1000,"answer_audio":3000,"endpoint_received_at":1700,"delivery_done":7000,"input_source":"realtime","speech_end_basis":"local_vad_estimate","answer_route":"model"}
rows=[base,{**base,"answer_audio":1001,"failed":True},{**base,"answer_audio":1002,"cancelled":True},{**base,"answer_audio":None},{**base,"speech_end_basis":"provider_endpoint_receipt","answer_audio":1500}]
backend=Mock();backend.iter_sessions.return_value=[{"version":1,"voice_provider":"sarvam","turns":rows,"interruptions":[{"detected_at":1000,"stopped_at":1030}]}]
with patch('server.runtime_metrics.storage.backend',return_value=backend):
 result=aggregate('demo')
groups={c['speech_end_basis']:c for c in result['cohorts']};c=groups['local_vad_estimate']
checks={
 'timing bases are separate':len(groups)==2,
 'failed and cancelled fast replies excluded':c['p50_ms']==2000 and c['complete_timings']==1,
 'failure cancellation missing remain visible':c['failed']==1 and c['cancelled']==1 and c['missing_timings']==1,
 'endpoint and completion measured separately':c['endpoint_delay_p50_ms']==700 and c['completion_p50_ms']==6000,
 'small samples labelled':c['small_sample'],
 'interruption basis is local stop request':result['interruption']['p95_ms']==30 and 'request' in result['interruption']['basis'],
 'empty sample is unavailable not zero':percentile([], .95) is None,
}
for name,ok in checks.items():print(('PASS ' if ok else 'FAIL ')+name)
assert all(checks.values())
print(f'{len(checks)}/{len(checks)} runtime metrics contracts passed')
