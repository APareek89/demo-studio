from pathlib import Path
import subprocess, json, os, re, sys, time
repo=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
python='/Users/macbook/Documents/demo-studio/.venv/bin/python'
wrapper='''import os,runpy,socket,sys,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory(prefix="feedback-gate-") as d:
 os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0",STORAGE_BACKEND="local",MODEL_TIER="eval",DEMO_STUDIO_DATA=d+"/demos",DEMO_STUDIO_GRAPH_DB=d+"/graph.sqlite",SHARE_SECRET="isolated-mock-only",ANTHROPIC_API_KEY="",GEMINI_API_KEY="",RUNWARE_API_KEY="",GCLOUD_TTS_API_KEY="",SARVAM_API_KEY="",AWS_EC2_METADATA_DISABLED="true")
 attempts=[]
 def blocked(*args,**kwargs):
  attempts.append(True)
  raise AssertionError("Feedback validation forbids outbound sockets")
 socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=socket.create_connection=socket.getaddrinfo=blocked
 target=sys.argv[1];sys.argv=[target];sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/"evals")]
 try:runpy.run_path(target,run_name="__main__")
 finally:
  print("OUTBOUND_ATTEMPTS",len(attempts),flush=True)
  assert not attempts
'''
results=[]
for name in sys.argv[3:]:
 target='evals/'+name+'.py'; start=time.monotonic()
 with (out/(name+'.log')).open('w') as log:
  result=subprocess.run([python,'-c',wrapper,target],cwd=repo,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 log=(out/(name+'.log')).read_text()
 summary=[line for line in log.splitlines() if re.search(r'\d+/\d+|SMOKE OK|OUTBOUND_ATTEMPTS|AssertionError|FAILED',line)]
 row=dict(suite=name,exit=result.returncode,seconds=round(time.monotonic()-start,2),summary=summary[-8:])
 results.append(row); print(json.dumps(row),flush=True)
 (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 if result.returncode: print(log[-7000:],flush=True)
raise SystemExit(any(r['exit'] for r in results))
