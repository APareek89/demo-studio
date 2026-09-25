#!/usr/bin/env python3
"""Fault injection for edge recovery; private temporary files, no real services."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import tempfile
from unittest import mock

import bootstrap as b
import sync_turn_certificate as c

def main():
    checks=[]
    def check(name,value):checks.append({'name':name,'pass':bool(value)});assert value,name
    with tempfile.TemporaryDirectory(prefix='transport-recovery-contract-') as raw:
        tmp=Path(raw);receipt=tmp/'receipt';receipt.mkdir();(receipt/'config').mkdir()
        previous_umask=os.umask(0o077)
        try:
            b.directory(tmp/'service-code',0o755)
            b.directory(tmp/'service-config',0o750)
            secret=tmp/'service-config/private.env';secret.write_text('synthetic=fixture')
        finally:os.umask(previous_umask)
        check('private operator umask cannot remove service directory traversal',(tmp/'service-code').stat().st_mode&0o777==0o755 and (tmp/'service-config').stat().st_mode&0o777==0o750)
        check('explicit service traversal does not broaden secret file permissions',secret.stat().st_mode&0o777==0o600)
        caddy=tmp/'Caddyfile';caddy.write_bytes(b'new edge')
        (receipt/'Caddyfile.before').write_bytes(b'original edge')
        (receipt/'haproxy.cfg.before').write_bytes(b'old inactive config')
        (receipt/'stage.json').write_text('{}')
        (receipt/'config/Caddyfile.bootstrap').write_bytes(b'bootstrap edge')
        actions=[];reports=[]
        real_copy=b.private_copy
        def private_copy(source,target,mode=0o600):
            if target==Path('/etc/haproxy/haproxy.cfg'):raise OSError('Injected prior HAProxy restoration failure')
            return real_copy(source,target,mode)
        def systemctl(args,**kwargs):
            args=list(args)
            actions.append(args)
            if args[:3]==['systemctl','stop','demo-livekit-qa.service']:
                raise subprocess.TimeoutExpired(args,40)
            return subprocess.CompletedProcess(args,0,b'',b'')
        def run(*args,**kwargs):actions.append(list(args));return b'200' if args[0]=='curl' else b''
        with mock.patch.multiple(b,RECEIPT=receipt,CADDY=caddy,health=lambda:None,run=run,
                                 private_copy=private_copy,receipt=lambda name,**data:reports.append((name,data))),mock.patch.object(b.subprocess,'run',side_effect=systemctl):
            b.rollback()
            check('a timed-out stop cannot prevent original Caddy recovery',caddy.read_bytes()==b'original edge')
            check('prior HAProxy copy failure cannot prevent public HTTPS verification',any(a[0]=='curl' for a in actions))
            check('all newly owned persistent services are disabled',sum(a[:2]==['systemctl','disable'] for a in actions)==3)
            check('recovery receipt records independent failures',reports[-1][1]['stop_demo-livekit-qa.service'] is False and reports[-1][1]['restore_prior_haproxy_config'] is False)
            # A real signal is delivered inside the protected live-write phase.
            caddy.write_bytes(b'original edge');b.EXPECTED_CADDY=hashlib.sha256(caddy.read_bytes()).hexdigest()
            old_handler=signal.signal(signal.SIGTERM,b.interrupted);first_reload=[True]
            def terminate_on_reload(*args,**kwargs):
                if args==('systemctl','reload','caddy') and first_reload[0]:
                    first_reload[0]=False;os.kill(os.getpid(),signal.SIGTERM)
                return run(*args,**kwargs)
            try:
                with mock.patch.object(b,'run',side_effect=terminate_on_reload):
                    try:b.certificates()
                    except InterruptedError:pass
                    else:raise AssertionError('SIGTERM should interrupt the certificate phase')
            finally:signal.signal(signal.SIGTERM,old_handler)
            check('SIGTERM after live Caddy replacement restores original edge',caddy.read_bytes()==b'original edge')

        certs=tmp/'certificates';domain_dir=certs/'issuer'/c.DOMAIN;domain_dir.mkdir(parents=True)
        cert=domain_dir/(c.DOMAIN+'.crt');key=cert.with_suffix('.key')
        cert.write_bytes(b'new certificate');key.write_bytes(b'new private key')
        target=tmp/'turn.pem';target.write_bytes(b'previous working PEM');calls=[]
        def fake_run(*args):
            calls.append(args)
            if '-checkhost' in args:out=b'Hostname does match certificate'
            elif '-pubkey' in args or '-pubout' in args:out=b'matching public key'
            elif '-outform' in args:out=b'new DER'
            else:out=b''
            return subprocess.CompletedProcess(args,0,out,b'')
        def fake_systemctl(args,**kwargs):calls.append(tuple(args));return subprocess.CompletedProcess(args,0,b'',b'')
        def safe_path(value):return tmp/'sync.lock' if value=='/run/demo-livekit-cert-sync.lock' else Path(value)
        with mock.patch.multiple(c,CERTS=certs,TARGET=target,Path=safe_path,run=fake_run),mock.patch.object(c.os,'geteuid',return_value=0),mock.patch.object(c.subprocess,'run',side_effect=fake_systemctl),mock.patch.object(c,'verify_served',side_effect=RuntimeError('Injected bad served leaf')):
            try:c.sync()
            except RuntimeError:pass
            else:raise AssertionError('Served-leaf mismatch must fail renewal')
        check('failed served-leaf validation restores previous private PEM',target.read_bytes()==b'previous working PEM')
        check('failed served-leaf validation reloads the previous working certificate',sum(a==('systemctl','reload','haproxy') for a in calls)==2)
        check('restored private PEM remains0600',target.stat().st_mode&0o777==0o600)
    print(json.dumps({'passed':len(checks),'total':len(checks),'checks':checks,'production_mutations':False,'paid_calls':0},indent=2))

if __name__=='__main__':main()
