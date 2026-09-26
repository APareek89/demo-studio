"""Package an exact committed revision locally; never deploy or include user data."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    commit=subprocess.check_output(['git','rev-parse',args.commit+'^{commit}'],text=True).strip()
    args.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    raw=subprocess.check_output(['git','archive','--format=tar',commit])
    manifest={};archive=args.output/'source.tar.gz'
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as source,tarfile.open(archive,'w:gz') as dest:
        for entry in source:
            parts=Path(entry.name).parts
            assert parts and not entry.name.startswith('/') and '..' not in parts
            if parts[0] in {'.git','data','output','.venv','.agentlane','.playwright-cli'} or '.env' in parts:continue
            assert entry.isdir() or entry.isfile(),'Refuse source links or special files'
            if entry.isdir():continue
            assert entry.name!='SOURCE_COMMIT'
            contents=source.extractfile(entry).read();manifest[entry.name]=hashlib.sha256(contents).hexdigest()
            info=tarfile.TarInfo(entry.name);info.size=len(contents);info.mode=0o755 if entry.mode&0o111 else 0o644
            dest.addfile(info,io.BytesIO(contents))
    assert manifest
    (args.output/'source-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    metadata={'commit':commit,'archives':{'source.tar.gz':{'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}}}
    (args.output/'package.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'commit':commit,'source_files':len(manifest),'source_bytes':archive.stat().st_size,'data_included':False}))

if __name__=='__main__':main()
