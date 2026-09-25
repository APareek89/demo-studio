#!/usr/bin/env python3
"""Exercise the generated TLS edge on ephemeral loopback ports and fake upstreams.

Real Caddy/HAProxy, synthetic certificates/authentication, no application imports,
ACME, production requests, provider calls, or active service reloads.
"""
from pathlib import Path
import argparse
import http.server
import json
import os
import re
import secrets
import socket
import socketserver
import ssl
import struct
import subprocess
import tempfile
import threading
import time

from render_configs import render,APP,RTC,TURN,TLS,HTTP

class HTTPStub(http.server.BaseHTTPRequestHandler):
    seen=[]
    def log_message(self,*_):pass
    def request(self):
        self.seen.append((self.command,self.path,dict(self.headers)))
        self.rfile.read(int(self.headers.get('Content-Length','0')))
        payload=b'fixture'
        self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
        if self.command!='HEAD':self.wfile.write(payload)
    do_GET=do_POST=do_HEAD=do_PUT=do_PATCH=do_DELETE=do_OPTIONS=request

class TURNStub(socketserver.BaseRequestHandler):
    seen=[]
    def handle(self):
        self.request.settimeout(3)
        def exact(n):
            data=b''
            while len(data)<n:
                chunk=self.request.recv(n-len(data))
                if not chunk:raise OSError('Truncated fixture protocol')
                data+=chunk
            return data
        head=exact(16)
        assert head[:12]==b'\r\n\r\n\x00\r\nQUIT\n' and head[12:14]==b'\x21\x11'
        payload=exact(struct.unpack('!H',head[14:16])[0])
        source=socket.inet_ntoa(payload[:4])
        probe=exact(4);self.seen.append((source,probe));self.request.sendall(b'TURN fixture')

def port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
def run(*args,**kwargs):return subprocess.run(args,check=True,capture_output=True,timeout=20,**kwargs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    checks=[];processes=[];servers=[]
    def check(name,value):
        checks.append({'name':name,'pass':bool(value)})
        assert value,name
    try:
        with tempfile.TemporaryDirectory(prefix='livekit-edge-contract-') as raw:
            tmp=Path(raw);generated=tmp/'rendered'
            render(generated,{'api_key':'synthetic_fixture_key','api_secret':'x'*48})
            cert,key=tmp/'cert.pem',tmp/'key.pem'
            run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN='+APP,
                '-addext','subjectAltName=DNS:'+APP+',DNS:'+RTC+',DNS:'+TURN,'-keyout',str(key),'-out',str(cert))
            pem=tmp/'combined.pem';pem.write_bytes(cert.read_bytes()+key.read_bytes());pem.chmod(0o600)
            password=secrets.token_urlsafe(20)
            hashed=run('/usr/bin/caddy','hash-password','--plaintext',password).stdout.decode().strip()
            auth=tmp/'admin.auth';auth.write_text('fixture_admin '+hashed+'\n');auth.chmod(0o600)
            upstream=http.server.ThreadingHTTPServer(('127.0.0.1',0),HTTPStub)
            turn=socketserver.ThreadingTCPServer(('127.0.0.1',0),TURNStub)
            for server in [upstream,turn]:
                servers.append(server);threading.Thread(target=server.serve_forever,daemon=True).start()
            public,caddy_port,turn_tls=port(),port(),port()
            caddy=(generated/'Caddyfile').read_text().replace('{\n','{\n    admin off\n',1)
            caddy=caddy.replace(HTTP,'').replace(TLS,'tls '+str(cert)+' '+str(key))
            caddy=caddy.replace('8443',str(caddy_port))
            for name in [APP,RTC,TURN]:
                caddy=re.sub(r'(?m)^'+re.escape(name)+r' \{','https://'+name+':'+str(caddy_port)+' {',caddy)
            caddy=caddy.replace('127.0.0.1:8877','127.0.0.1:'+str(upstream.server_port))
            caddy=caddy.replace('127.0.0.1:7880','127.0.0.1:'+str(upstream.server_port))
            caddy=caddy.replace('/etc/caddy/demo-studio-admin.auth',str(auth))
            caddy_file=tmp/'Caddyfile';caddy_file.write_text(caddy)
            haproxy=(generated/'haproxy.cfg').read_text().replace('bind 0.0.0.0:443','bind 127.0.0.1:'+str(public))
            haproxy=haproxy.replace('127.0.0.1:8443','127.0.0.1:'+str(caddy_port)).replace('127.0.0.1:9443','127.0.0.1:'+str(turn_tls))
            haproxy=haproxy.replace('/etc/demo-livekit/turn.pem',str(pem)).replace('172.31.13.9:5349','127.0.0.1:'+str(turn.server_address[1]))
            haproxy_file=tmp/'haproxy.cfg';haproxy_file.write_text(haproxy)
            env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(tmp/'config'),XDG_DATA_HOME=str(tmp/'data'))
            adapted=run('/usr/bin/caddy','adapt','--config',str(caddy_file),'--adapter','caddyfile',env=env)
            parsed=json.loads(adapted.stdout)
            check('global JWT URI and header redaction configured',all(v in json.dumps(parsed) for v in ['request>uri','request>headers>Authorization','request>headers>Cookie']))
            run('/usr/sbin/haproxy','-c','-f',str(haproxy_file))
            check('real HAProxy configuration valid',True)
            log=tmp/'caddy.log'
            with log.open('wb') as stream:
                processes.append(subprocess.Popen(['/usr/bin/caddy','run','--config',str(caddy_file),'--adapter','caddyfile'],stdout=stream,stderr=stream,env=env))
                processes.append(subprocess.Popen(['/usr/sbin/haproxy','-db','-f',str(haproxy_file)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
                context=ssl.create_default_context(cafile=str(cert))
                def request(host,path,method='GET',spoof=False):
                    with socket.socket() as raw_socket:
                        raw_socket.settimeout(5);raw_socket.bind(('127.0.0.2',0));raw_socket.connect(('127.0.0.1',public))
                        with context.wrap_socket(raw_socket,server_hostname=host) as stream_socket:
                            headers='X-Forwarded-For: 198.51.100.99\r\nX-Forwarded-Proto: http\r\n' if spoof else ''
                            message=f'{method} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\nContent-Length: 0\r\n{headers}\r\n'
                            stream_socket.sendall(message.encode());response=b''
                            while True:
                                chunk=stream_socket.recv(4096)
                                if not chunk:break
                                response+=chunk
                    return int(response.split(b'\r\n',1)[0].split()[1])
                for attempt in range(30):
                    try:
                        if request(APP,'/api/health')==200:break
                    except OSError:time.sleep(0.1)
                else:raise RuntimeError('Fixture edge did not start')
                check('trusted app TLS through SNI mux',True)
                check('public capability GET',request(APP,'/api/runtime/transport')==200)
                for method in ['HEAD','POST','PUT','DELETE','PATCH','OPTIONS']:
                    check('capability blocks '+method,request(APP,'/api/runtime/transport',method)==401)
                path='/api/demos/dm_29df0418/run/livekit/token'
                check('exact public token POST',request(APP,path,'POST')==200)
                for method in ['GET','HEAD','PUT','DELETE','PATCH','OPTIONS']:
                    check('token blocks '+method,request(APP,path,method)==401)
                for path in ['/api/demos/dm_29df0418/run/livekit/token/','/api/demos/dm_29df0418/run/livekit/admin','/api/demos/dm_29df0418/settings','/api/demos','/api/runtime/transport/']:
                    check('private boundary '+path,request(APP,path,'POST')==401)
                request(APP,'/api/health',spoof=True)
                headers={k.lower():v for k,v in HTTPStub.seen[-1][2].items()}
                check('actual client IP retained and spoofed XFF discarded',headers.get('x-forwarded-for')=='127.0.0.2')
                check('spoofed forwarded scheme discarded',headers.get('x-forwarded-proto')=='https')
                for path in ['/rtc','/rtc/v1','/rtc/validate','/rtc/v1/validate']:
                    check('RTC GET '+path,request(RTC,path)==200)
                    check('RTC POST blocked '+path,request(RTC,path,'POST')==404)
                for path in ['/','/twirp/livekit.RoomService/ListRooms','/api/health','/settings']:
                    check('RTC private path blocked '+path,request(RTC,path)==404)
                try:
                    with socket.create_connection(('127.0.0.1',caddy_port),timeout=2) as raw_socket:
                        with context.wrap_socket(raw_socket,server_hostname=APP):pass
                    no_proxy=False
                except (OSError,ssl.SSLError):no_proxy=True
                check('private Caddy requires PROXY header',no_proxy)
                with socket.socket() as raw_socket:
                    raw_socket.settimeout(5);raw_socket.bind(('127.0.0.2',0));raw_socket.connect(('127.0.0.1',public))
                    with context.wrap_socket(raw_socket,server_hostname=TURN) as tls:
                        tls.sendall(b'ping');answer=tls.recv(30)
                check('TURN SNI reaches TLS terminator',answer==b'TURN fixture')
                check('TURN PROXYv2 retains actual peer IP',TURNStub.seen[-1]==('127.0.0.2',b'ping'))
                # Deliberate upstream refusal creates a proxy error containing a secret
                # query in the request; the configured logger must remove that URI.
                upstream.shutdown();upstream.server_close();servers.remove(upstream)
                marker='sensitive-fixture-token-'+secrets.token_hex(12)
                check('signal upstream error is bounded',request(RTC,'/rtc?access_token='+marker)==502)
                time.sleep(0.1)
                check('JWT query absent from captured proxy errors',marker not in log.read_text())
            result={'passed':sum(c['pass'] for c in checks),'total':len(checks),'production_mutations':False,'paid_calls':0,'checks':checks}
            if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    finally:
        for p in processes:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for server in servers:server.shutdown();server.server_close()

if __name__=='__main__':main()
