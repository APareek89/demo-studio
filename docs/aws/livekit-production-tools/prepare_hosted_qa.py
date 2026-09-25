"""Prepare only a disposable, credential-free BMW mock fixture; do not start it."""
from pathlib import Path
import json
import os
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
QA=Path('/opt/demo-studio-backups/20260925-livekit/hosted-qa')
SOURCE=Path('/opt/demo-studio/data/demos/dm_29df0418')
FILES={'demo.json','bundle.json','understanding.json','faq.json','deck.json',
       'plan.json','script.json','fillers.json','playbook.json','visual-audit.json'}
DIRS={'sources','derived','media','audio','knowledge'}
assert os.geteuid()==0
assert not QA.exists(), 'Refuse to overwrite existing QA fixture'
assert SOURCE.is_dir() and not SOURCE.is_symlink()
QA.mkdir(mode=0o700)
(QA/'demos').mkdir(mode=0o700)
# Same publication allowlist as the reviewed local trial. Never copy visits,
# leads, usage, chats, logs or mutable runtime; reject linked source assets.
destination=QA/'demos/dm_29df0418';destination.mkdir(mode=0o700)
for entry in SOURCE.iterdir():
    if entry.name not in FILES|DIRS:continue
    assert not any(p.is_symlink() for p in [entry,*entry.rglob('*')]),'Linked source asset rejected'
    if entry.is_dir():shutil.copytree(entry,destination/entry.name)
    else:shutil.copyfile(entry,destination/entry.name)
(QA/'mock.env').write_text('''MOCK_LLM=1
CLOUD_SYNC=0
STORAGE_BACKEND=local
AWS_EC2_METADATA_DISABLED=true
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
RUNWARE_API_KEY=
SARVAM_API_KEY=
GCLOUD_TTS_API_KEY=
TTS_PROVIDER=gemini
STT_PROVIDER=browser
LIVEKIT_ALLOWED_ORIGINS=http://127.0.0.1:8940
DEMO_STUDIO_DATA=/opt/demo-studio-backups/20260925-livekit/hosted-qa/demos
DEMO_STUDIO_GRAPH_DB=/opt/demo-studio-backups/20260925-livekit/hosted-qa/graph.sqlite
''')
(QA/'mock.env').chmod(0o600)
for path in [QA,*QA.rglob('*')]:
    if not path.is_symlink():shutil.chown(path,user='ec2-user',group='ec2-user')
shutil.copyfile(HERE/'hosted_mock.py','/opt/demo-livekit/hosted_mock.py')
Path('/opt/demo-livekit/hosted_mock.py').chmod(0o644)
unit=Path('/etc/systemd/system/demo-livekit-qa.service')
assert not unit.exists(),'Refuse to overwrite unrelated QA unit'
shutil.copyfile(HERE/unit.name,unit);unit.chmod(0o644)
subprocess.run(['systemctl','daemon-reload'],check=True,capture_output=True)
print(json.dumps({'prepared':True,'demo':'dm_29df0418','started':False,'production_data_written':False,'provider_keys_inherited':False}))
