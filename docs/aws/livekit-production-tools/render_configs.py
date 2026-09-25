"""Render the reviewed single-host TLS-relay deployment; never install/reload it.

Private credentials are read from a0600 JSON file. Generated server.yaml and
runtime.env contain credentials and must never be logged, committed or copied
into the application source archive. All output files are0600 in a0700 folder.
"""
from pathlib import Path
import argparse
import ipaddress
import json
import os
import re

HERE = Path(__file__).resolve().parent
APP = '13-202-0-79.sslip.io'
RTC = 'rtc.' + APP
TURN = 'turn.' + APP
PRIVATE_IP = '172.31.13.9'

TLS = '''tls {
        issuer acme {
            disable_tlsalpn_challenge
        }
    }'''
RTC_SITE = f'''{RTC} {{
    __BIND__
    {TLS}
    @signal {{
        method GET
        path /rtc /rtc/v1 /rtc/validate /rtc/v1/validate
    }}
    handle @signal {{
        reverse_proxy 127.0.0.1:7880 {{
            transport http {{
                read_timeout 600s
                write_timeout 600s
                response_header_timeout 30s
            }}
        }}
    }}
    handle {{
        respond 404
    }}
}}

{TURN} {{
    __BIND__
    {TLS}
    respond 404
}}
'''
LOG = '''
    log {
        format filter {
            wrap json
            fields {
                request>uri delete
                request>headers>Authorization delete
                request>headers>Cookie delete
            }
        }
    }
'''
GLOBAL = '''{
    https_port 8443
    auto_https disable_redirects
'''+LOG+'''
    servers 127.0.0.1:8443 {
        protocols h1 h2
        listener_wrappers {
            proxy_protocol {
                timeout 5s
                fallback_policy require
            }
            tls
        }
    }
}
'''
HTTP = f'''http:// {{
    bind 0.0.0.0
    @known host {APP} {RTC} {TURN}
    redir @known https://{{host}}{{uri}} 308
    respond 404
}}
'''

def render(out: Path, credentials: dict):
    api_key, secret = credentials['api_key'], credentials['api_secret']
    assert re.fullmatch(r'[A-Za-z0-9_-]{12,80}', api_key)
    assert re.fullmatch(r'[A-Za-z0-9_-]{40,160}', secret)
    assert not out.is_symlink()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out, 0o700)
    def write(name, text):
        path=out/name
        assert not path.exists() and not path.is_symlink(), 'Refuse to overwrite prepared configuration'
        path.write_text(text);path.chmod(0o600)
    boundary=(HERE/'Caddyfile.app-boundary.template').read_text()
    # Bootstrap retains production443 until both certificates exist.
    bootstrap=boundary.replace(APP+' {', APP+' {\n    '+TLS, 1)
    write('Caddyfile.bootstrap', '{\n'+LOG+'}\n'+bootstrap+'\n'+RTC_SITE.replace('__BIND__',''))
    final=boundary.replace(APP+' {', APP+' {\n    bind 127.0.0.1\n    '+TLS, 1)
    write('Caddyfile', GLOBAL+'\n'+final+'\n'+RTC_SITE.replace('__BIND__','bind 127.0.0.1')+'\n'+HTTP)
    write('haproxy.cfg', f'''global
    maxconn 256
    nbthread 1
    user haproxy
    group haproxy
    ssl-default-bind-options ssl-min-ver TLSv1.2

defaults
    mode tcp
    timeout connect 5s
    timeout client 1h
    timeout server 1h

frontend public_tls
    bind 0.0.0.0:443
    tcp-request inspect-delay 5s
    tcp-request content accept if {{ req_ssl_hello_type 1 }}
    use_backend turn_tls if {{ req.ssl_sni -i {TURN} }}
    default_backend caddy_tls

backend caddy_tls
    server caddy 127.0.0.1:8443 send-proxy-v2

backend turn_tls
    server turn_tls_terminator 127.0.0.1:9443 send-proxy-v2

frontend turn_tls_terminator
    bind 127.0.0.1:9443 accept-proxy ssl crt /etc/demo-livekit/turn.pem
    default_backend turn_plaintext

backend turn_plaintext
    server turn {PRIVATE_IP}:5349 send-proxy-v2
''')
    denied=[str(n) for n in ipaddress.IPv4Network('0.0.0.0/0').address_exclude(ipaddress.IPv4Network(PRIVATE_IP+'/32'))]+['::/0']
    deny_yaml=''.join('    - '+cidr+'\n' for cidr in denied)
    write('server.yaml', f'''port: 7880
bind_addresses: ["127.0.0.1"]
rtc:
  node_ip: "{PRIVATE_IP}"
  use_external_ip: false
  advertise_internal_ip: true
  udp_port: 7882
  tcp_port: 7881
  ips:
    includes: ["{PRIVATE_IP}/32"]
  stun_servers: ["{PRIVATE_IP}:3478"]
  data_channel_max_buffered_amount: 2097152
keys:
  {api_key}: {secret}
logging:
  level: warn
  pion_level: error
  sample: true
room:
  max_participants: 2
  empty_timeout: 30
  departure_timeout: 20
limit:
  num_tracks: 12
  bytes_per_sec: 4194304
  signal_message_size_limit: 262144
  max_api_request_body_size: 262144
turn:
  enabled: true
  domain: "{TURN}"
  bind_addresses: ["{PRIVATE_IP}"]
  tls_port: 5349
  udp_port: 3478
  external_tls: true
  proxy_protocol: true
  proxy_protocol_trusted_cidrs: ["{PRIVATE_IP}/32", "127.0.0.1/32"]
  relay_range_start: 20000
  relay_range_end: 20100
  per_user_relay_allocation_limit: 6
  ttl_seconds: 300
  allow_restricted_peer_cidrs: ["{PRIVATE_IP}/32"]
  deny_peer_cidrs:
{deny_yaml}''')
    write('runtime.env', f'''LIVEKIT_ENABLED=1
LIVEKIT_TRIAL_ENABLED=0
LIVEKIT_URL=wss://{RTC}
LIVEKIT_INTERNAL_URL=ws://127.0.0.1:7880
LIVEKIT_ALLOWED_ORIGINS=https://{APP}
LIVEKIT_ICE_TRANSPORT_POLICY=relay
LIVEKIT_MAX_ROOMS=2
LIVEKIT_API_KEY={api_key}
LIVEKIT_API_SECRET={secret}
''')
    write('configuration-summary.json', json.dumps({'app_origin':'https://'+APP,'public_signalling':'wss://'+RTC,
          'turn_tls':TURN+':443','private_sfu':PRIVATE_IP,'max_rooms':2,'browser_ice_policy':'relay',
          'security_group_changes':False,'new_billed_resources':False,'turn_peers':[PRIVATE_IP+'/32'],
          'worker_url':'ws://127.0.0.1:7880'},indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    args=parser.parse_args()
    assert args.credentials.stat().st_mode & 0o077 == 0, 'Credentials must be private'
    render(args.output,json.loads(args.credentials.read_text()))
    print('Prepared configuration files; no secrets displayed and no services changed.')
