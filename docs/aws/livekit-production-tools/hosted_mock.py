"""Isolated hosted browser-QA entrypoint; only Python loopback SFU connections.

The native RTC SDK uses host/private media sockets separately. There are no
provider credentials; mock mode and cloud-off are asserted before app import.
"""
import ipaddress
import os
from pathlib import Path
import socket
import sys

assert os.environ.get('MOCK_LLM')=='1'
assert os.environ.get('CLOUD_SYNC')=='0'
for name in ['ANTHROPIC_API_KEY','GEMINI_API_KEY','RUNWARE_API_KEY','SARVAM_API_KEY','GCLOUD_TTS_API_KEY']:
    assert os.environ.get(name,'')==''
qa=Path('/opt/demo-studio-backups/20260925-livekit/hosted-qa').resolve()
for name in ['DEMO_STUDIO_DATA','DEMO_STUDIO_GRAPH_DB']:
    assert Path(os.environ[name]).resolve().is_relative_to(qa)
assert os.environ.get('LIVEKIT_INTERNAL_URL')=='ws://127.0.0.1:7880'
real_connect=socket.socket.connect
real_connect_ex=socket.socket.connect_ex
real_getaddrinfo=socket.getaddrinfo

def allowed(sock,address):
    if sock.family==socket.AF_UNIX:return True
    return isinstance(address,tuple) and str(address[0])=='127.0.0.1' and address[1]==7880

def connect(sock,address):
    if not allowed(sock,address):raise OSError('Hosted mock QA blocks Python outbound connections')
    return real_connect(sock,address)

def connect_ex(sock,address):
    if not allowed(sock,address):raise OSError('Hosted mock QA blocks Python outbound connections')
    return real_connect_ex(sock,address)

def resolve(host,port,*args,**kwargs):
    try:ipaddress.ip_address(str(host))
    except ValueError:raise OSError('Hosted mock QA blocks DNS') from None
    return real_getaddrinfo(host,port,*args,**kwargs)

def sendto(*args,**kwargs):raise OSError('Hosted mock QA blocks Python UDP')

socket.socket.connect=connect
socket.socket.connect_ex=connect_ex
socket.getaddrinfo=resolve
socket.socket.sendto=sendto

import uvicorn
sys.path.insert(0,'/opt/demo-studio-releases/20260925-livekit')
uvicorn.run('server.app:app',host='127.0.0.1',port=18877,proxy_headers=False,access_log=False)
