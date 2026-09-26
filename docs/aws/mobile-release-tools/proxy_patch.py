"""Exact optional-browser-asset patch; keep LiveKit/auth/provider settings unchanged."""
import argparse
import json
import urllib.error
import urllib.request
from app_common import *
from app_cutover import install_interrupt_handler,private_hash

ASSETS=['/favicon.ico','/apple-touch-icon.png','/apple-touch-icon-precomposed.png','/manifest.json']
def blocks(template):
    start=template.index('\t# Browsers may probe')
    end=template.index('\t@livekit_token {',start)
    matcher=template[start:end]
    start=template.index('\thandle @optional_browser_asset {')
    end=template.index('\thandle @runtime_transport {',start)
    handler=template[start:end]
    assert 'method GET HEAD' in matcher and all(p in matcher for p in ASSETS)
    assert matcher.count('path ')==1 and '* ' not in matcher and 'respond 404' in handler
    return matcher,handler

def prepare():
    assert verify_source()>0
    template=(RELEASE/'docs/aws/livekit-production-tools/Caddyfile.app-boundary.template').read_text()
    matcher,handler=blocks(template)
    current=run('sudo','cat',CADDY).stdout
    assert '@optional_browser_asset' not in current,'Do not overwrite an already changed live policy'
    assert current.count('\t@livekit_token {')==1 and current.count('\thandle @runtime_transport {')==1
    candidate=current.replace('\t@livekit_token {',matcher+'\t@livekit_token {',1).replace('\thandle @runtime_transport {',handler+'\thandle @runtime_transport {',1)
    assert candidate.replace(matcher,'',1).replace(handler,'',1)==current
    before=RECEIPT/'mobile-Caddyfile.before.private';after=RECEIPT/'mobile-Caddyfile.candidate.private'
    assert not before.exists() and not after.exists()
    before.write_text(current);before.chmod(0o600);after.write_text(candidate);after.chmod(0o600)
    run('sudo','/usr/bin/caddy','validate','--adapter','caddyfile','--config',after)
    save('proxy-prepared.json',{'commit':package()['commit'],'before_sha256':sha(before),'candidate_sha256':sha(after),'auth_sha256':private_hash(AUTH),'only_changes':'Exact four optional browser assets, GET/HEAD,404 without challenge'})
    print('Candidate proxy patch validated; active proxy unchanged.')

def fetch(path,method='GET'):
    request=urllib.request.Request('https://13-202-0-79.sslip.io'+path,method=method)
    try:response=urllib.request.urlopen(request,timeout=10)
    except urllib.error.HTTPError as error:response=error
    with response:return response.status,bool(response.headers.get('WWW-Authenticate'))

def rollback():
    plan=json.loads((RECEIPT/'proxy-prepared.json').read_text())
    current=private_hash(CADDY)
    assert current in {plan['before_sha256'],plan['candidate_sha256']},'Unexpected later proxy change; do not overwrite'
    assert sha(RECEIPT/'mobile-Caddyfile.before.private')==plan['before_sha256']
    run('sudo','install','-m','644',RECEIPT/'mobile-Caddyfile.before.private',CADDY)
    run('sudo','systemctl','reload','caddy')
    assert fetch('/api/health')[0]==200 and fetch('/api/demos')[0]==401
    save('proxy-rollback-'+str(time.time_ns())+'.json',{'old_proxy_restored':True,'auth_unchanged':private_hash(AUTH)==plan['auth_sha256'],'data_changed':False})

def apply():
    plan=json.loads((RECEIPT/'proxy-prepared.json').read_text())
    assert plan['commit']==package()['commit'] and private_hash(CADDY)==plan['before_sha256']
    candidate=RECEIPT/'mobile-Caddyfile.candidate.private'
    assert sha(candidate)==plan['candidate_sha256']
    assert private_hash(AUTH)==plan['auth_sha256']
    changed=False
    try:
        changed=True
        run('sudo','install','-m','644',candidate,CADDY)
        run('sudo','systemctl','reload','caddy')
        checks=[]
        for path in ASSETS:
            for method in ['GET','HEAD']:
                assert fetch(path,method)==(404,False);checks.append(method+' '+path)
            assert fetch(path,'POST')==(401,True);checks.append('POST '+path)
        for path in ['/favicon.ico/','/favicon.png','/apple-touch-icon-180x180.png','/site.webmanifest','/manifest.json.bak','/api/demos','/api/demos/dm_29df0418/sessions']:
            assert fetch(path)==(401,True);checks.append('protected '+path)
        assert fetch('/api/health')[0]==200;checks.append('public health')
        assert private_hash(AUTH)==plan['auth_sha256'] and private_hash(CADDY)==plan['candidate_sha256']
        save('proxy-applied.json',{'commit':package()['commit'],'passed':len(checks),'total':len(checks),'caddy_sha256':plan['candidate_sha256'],'auth_unchanged':True,'checks':checks,'provider_calls':0})
        print(json.dumps({'proxy_checks':len(checks),'optional_assets':404,'operator_auth_retained':True}))
    except BaseException:
        if changed:rollback()
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','apply','rollback']);args=parser.parse_args()
    os.umask(0o077);install_interrupt_handler();globals()[args.phase]()
