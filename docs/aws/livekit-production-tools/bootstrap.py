#!/usr/bin/env python3
"""Bounded, root-operated LiveKit edge staging; never changes app data or AWS SGs.

Run each phase separately after review. All diagnostics are captured privately;
stdout contains only phase receipts. The prior application stays running.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import time
import urllib.request

from render_configs import render

HERE=Path(__file__).resolve().parent
RECEIPT=Path('/opt/demo-studio-backups/20260925-livekit/transport')
ROOT=Path('/opt/demo-livekit')
CONF=Path('/etc/demo-livekit')
CADDY=Path('/etc/caddy/Caddyfile')
EXPECTED_CADDY='60ba8ffeb9558bb6b22db7c822159de3d85027651b8d6c8e1948c4665c4fdb6e'
BINARY_SHA='bcf05dcdb093657208efb1d85ac54c02ab28561bf66774db7e6bb173d3736ff3'

def interrupted(*_):raise InterruptedError('Transport operation interrupted')

def run(*args,timeout=60):
    result=subprocess.run(args,capture_output=True,timeout=timeout)
    if result.returncode:
        # Never emit command output: validator diagnostics can contain secrets.
        raise RuntimeError('Command failed: '+Path(args[0]).name)
    return result.stdout

def active(name):return subprocess.run(['systemctl','is-active','--quiet',name],capture_output=True).returncode==0
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def directory(path,mode):
    # mkdir's mode is filtered by the operator's private umask. Explicitly apply
    # only the reviewed traversal permissions to new service-owned paths.
    path.mkdir(mode=mode)
    path.chmod(mode)
def private_copy(source,target,mode=0o600):
    assert not target.is_symlink()
    shutil.copyfile(source,target);target.chmod(mode)
def receipt(name,**data):
    path=RECEIPT/(name+'.json')
    path.write_text(json.dumps({'phase':name,'security_group_changes':False,'application_changed':False,**data},indent=2)+'\n')
    path.chmod(0o600)
    print(json.dumps({'phase':name,'ok':True,**data}))
def caddy_check(path):run('/usr/bin/caddy','validate','--adapter','caddyfile','--config',str(path))
def health():
    with urllib.request.urlopen('http://127.0.0.1:8877/api/health',timeout=5) as response:assert response.status==200

def stage(binary,resume=False):
    assert not (RECEIPT/'stage.json').exists(),'Staging already completed; do not generate different keys'
    assert digest(CADDY)==EXPECTED_CADDY,'Production proxy changed since reviewed snapshot'
    assert not CONF.exists(),'Refuse to overwrite pre-existing LiveKit configuration'
    if resume:
        assert (RECEIPT/'config/runtime.env').is_file() and digest(RECEIPT/'Caddyfile.before')==EXPECTED_CADDY
        assert (ROOT/'v1.13.7/livekit-server').is_file() and digest(ROOT/'v1.13.7/livekit-server')==BINARY_SHA
        assert set(p.name for p in ROOT.iterdir())=={'v1.13.7'},'Unrecognized partial installation'
    else:assert not ROOT.exists(),'Refuse to overwrite pre-existing LiveKit installation'
    assert not active('haproxy') and not active('demo-livekit')
    assert digest(binary)==BINARY_SHA,'Wrong SFU binary'
    RECEIPT.mkdir(parents=True,exist_ok=True,mode=0o700);RECEIPT.chmod(0o700)
    if not resume:private_copy(CADDY,RECEIPT/'Caddyfile.before')
    existing_haproxy=Path('/etc/haproxy/haproxy.cfg')
    if not resume and existing_haproxy.exists():private_copy(existing_haproxy,RECEIPT/'haproxy.cfg.before')
    # Package install alone does not enable/start HAProxy on Amazon Linux.
    run('dnf','install','-y','haproxy-3.0.23-2.amzn2023.0.1',timeout=300)
    assert not active('haproxy'),'Unexpected package auto-start; stop and review'
    try:run('id','demo-livekit')
    except RuntimeError:run('useradd','--system','--home-dir','/nonexistent','--shell','/sbin/nologin','demo-livekit')
    if not resume:
        directory(ROOT,0o755);directory(ROOT/'v1.13.7',0o755)
        private_copy(binary,ROOT/'v1.13.7/livekit-server',0o755)
    else:
        ROOT.chmod(0o755);(ROOT/'v1.13.7').chmod(0o755)
    version=run(str(ROOT/'v1.13.7/livekit-server'),'--version').decode().strip()
    assert version.endswith('1.13.7'), 'Unexpected compiled SFU version'
    if not resume:
        credentials={'api_key':secrets.token_urlsafe(24),'api_secret':secrets.token_urlsafe(48)}
        render(RECEIPT/'config',credentials)
    generated=RECEIPT/'config'
    ports=run(str(ROOT/'v1.13.7/livekit-server'),'--config',str(generated/'server.yaml'),'ports').decode()
    # Upstream main prints config errors without a nonzero exit; inspect expected output.
    assert all(s in ports for s in ['TCP Ports','7880 - HTTP service','7881 - ICE/TCP','5349 - TURN/TLS','3478 - TURN/UDP']), 'Strict SFU configuration parse failed'
    # Pinned upstream formats the scalar UDP port with %s rather than %d.
    assert '7882 - ICE/UDP' in ports or '%!s(int=7882) - ICE/UDP' in ports, 'Unexpected ICE/UDP configuration'
    caddy_check(generated/'Caddyfile.bootstrap');caddy_check(generated/'Caddyfile')
    directory(CONF,0o750);shutil.chown(CONF,group='demo-livekit')
    for name in ['server.yaml','runtime.env']:private_copy(generated/name,CONF/name)
    (CONF/'server.yaml').chmod(0o640);shutil.chown(CONF/'server.yaml',group='demo-livekit')
    run('runuser','-u','demo-livekit','--','test','-x',str(ROOT/'v1.13.7/livekit-server'))
    run('runuser','-u','demo-livekit','--','test','-r',str(CONF/'server.yaml'))
    private_copy(HERE/'sync_turn_certificate.py',ROOT/'sync_turn_certificate.py',0o755)
    for name in ['demo-livekit.service','demo-livekit-cert-sync.service','demo-livekit-cert-sync.timer']:
        target=Path('/etc/systemd/system')/name
        assert not target.exists(),'Refuse to overwrite pre-existing unit'
        private_copy(HERE/name,target,0o644)
    run('systemctl','daemon-reload')
    receipt('stage',binary_sha256=BINARY_SHA,version=version,strict_config_parse=True,caddy_configs_validated=True)

def rollback():
    # These independent actions deliberately continue even if an earlier stop fails.
    results={}
    def attempt(key,*args,timeout=40):
        try:results[key]=subprocess.run(args,capture_output=True,timeout=timeout).returncode==0
        except (OSError,subprocess.TimeoutExpired):results[key]=False
    for unit in ['demo-livekit-qa.service','haproxy','demo-livekit-cert-sync.timer','demo-livekit']:
        attempt('stop_'+unit,'systemctl','stop',unit)
    for unit in ['haproxy','demo-livekit-cert-sync.timer','demo-livekit']:
        attempt('disable_'+unit,'systemctl','disable',unit,timeout=20)
    if (RECEIPT/'haproxy.cfg.before').exists():
        try:
            private_copy(RECEIPT/'haproxy.cfg.before',Path('/etc/haproxy/haproxy.cfg'),0o644)
            results['restore_prior_haproxy_config']=True
        except (OSError,AssertionError):results['restore_prior_haproxy_config']=False
    try:
        private_copy(RECEIPT/'Caddyfile.before',CADDY,0o644)
        run('systemctl','reload','caddy');health()
        status=run('curl','--silent','--show-error','--max-time','10','--resolve','13-202-0-79.sslip.io:443:127.0.0.1','-o','/dev/null','-w','%{http_code}','https://13-202-0-79.sslip.io/api/health').decode()
        assert status=='200'
        results['old_caddy_and_app_healthy']=True
    except BaseException:results['old_caddy_and_app_healthy']=False
    # Never restore data, provider env, app release drop-ins, or authentication.
    receipt('rollback',**results)
    assert results['old_caddy_and_app_healthy'],'Original edge recovery requires operator attention'

def certificates():
    assert (RECEIPT/'stage.json').exists() and digest(CADDY)==EXPECTED_CADDY
    try:
        private_copy(RECEIPT/'config/Caddyfile.bootstrap',CADDY,0o644)
        run('systemctl','reload','caddy');health()
        certs=Path('/var/lib/caddy/.local/share/caddy/certificates')
        for _ in range(60):
            if all(list(certs.glob('*/'+domain+'/'+domain+'.crt')) for domain in ['rtc.13-202-0-79.sslip.io','turn.13-202-0-79.sslip.io']):break
            time.sleep(2)
        else:raise RuntimeError('New TLS certificates were not acquired')
        run('/usr/bin/python3',str(ROOT/'sync_turn_certificate.py'),'--no-reload')
        private_copy(RECEIPT/'config/haproxy.cfg',Path('/etc/haproxy/haproxy.cfg'),0o644)
        run('/usr/sbin/haproxy','-c','-f','/etc/haproxy/haproxy.cfg')
        receipt('certificates',https_app_retained=True,haproxy_config_valid=True)
    except BaseException:
        rollback();raise

def refresh_edge_config():
    """Refresh staging-only edge templates, proving the SFU/private env is identical."""
    assert (RECEIPT/'stage.json').exists() and not (RECEIPT/'certificates.json').exists()
    assert digest(CADDY)==EXPECTED_CADDY,'Do not refresh after live edge changes'
    current=RECEIPT/'config'
    values=dict(line.split('=',1) for line in (current/'runtime.env').read_text().splitlines() if '=' in line)
    updated=RECEIPT/'config-reviewed'
    render(updated,{'api_key':values['LIVEKIT_API_KEY'],'api_secret':values['LIVEKIT_API_SECRET']})
    for name in ['server.yaml','runtime.env','haproxy.cfg']:
        assert (current/name).read_bytes()==(updated/name).read_bytes(),'Refresh must not alter SFU, keys or HAProxy'
    for name in ['Caddyfile.bootstrap','Caddyfile']:caddy_check(updated/name)
    for name in ['Caddyfile.bootstrap','Caddyfile']:private_copy(updated/name,current/name)
    receipt('refresh-edge-config',active_files_changed=False,private_keys_retained=True)

def activate():
    assert (RECEIPT/'certificates.json').exists()
    try:
        run('systemctl','start','demo-livekit')
        for _ in range(60):
            try:
                with urllib.request.urlopen('http://127.0.0.1:7880',timeout=2) as r:assert r.status==200
                break
            except OSError:time.sleep(0.5)
        else:raise RuntimeError('Private SFU did not become healthy')
        caddy_check(RECEIPT/'config/Caddyfile')
        private_copy(RECEIPT/'config/Caddyfile',CADDY,0o644)
        run('systemctl','reload','caddy')
        run('systemctl','start','haproxy')
        # Verify the exact trusted TURN leaf through public SNI on the local edge.
        import importlib.util
        spec=importlib.util.spec_from_file_location('cert_sync',ROOT/'sync_turn_certificate.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        der=run('openssl','x509','-in',str(CONF/'turn.pem'),'-outform','DER')
        module.verify_served(der)
        for domain,path,expected in [('13-202-0-79.sslip.io','/api/health',200),('rtc.13-202-0-79.sslip.io','/not-rtc',404)]:
            status=run('curl','--silent','--show-error','--max-time','10','--resolve',domain+':443:127.0.0.1','-o','/dev/null','-w','%{http_code}','https://'+domain+path).decode()
            assert status==str(expected),'Trusted HTTPS edge failed'
        receipt('activate',old_app_still_active=True,turn_tls_trusted=True,rtc_private_routes_denied=True)
    except BaseException:
        rollback();raise

def enable():
    assert (RECEIPT/'activate.json').exists() and active('demo-livekit') and active('haproxy')
    run('systemctl','enable','demo-livekit','haproxy','demo-livekit-cert-sync.timer')
    run('systemctl','start','demo-livekit-cert-sync.timer')
    receipt('enable',boot_persistence=True,certificate_renewal_timer=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['stage','refresh-edge-config','certificates','activate','enable','rollback'])
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--resume-stage',action='store_true',help='Resume only the verified pre-configuration partial stage, retaining its keys')
    args=parser.parse_args();assert os.geteuid()==0,'Execute as root';os.umask(0o077)
    signal.signal(signal.SIGTERM,interrupted)
    if args.phase=='stage':assert args.binary;stage(args.binary,args.resume_stage)
    else:globals()[args.phase.replace('-','_')]()
