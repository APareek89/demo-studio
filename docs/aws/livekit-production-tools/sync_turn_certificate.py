"""Copy the Caddy-managed TURN certificate privately and reload HAProxy only.

Execute as root. Does not restart LiveKit, print key material or alter Caddy.
Called after bootstrap and by the bounded systemd renewal timer.
"""
from pathlib import Path
import argparse
import fcntl
import os
import signal
import socket
import ssl
import subprocess
import tempfile
import time

DOMAIN='turn.13-202-0-79.sslip.io'
CERTS=Path('/var/lib/caddy/.local/share/caddy/certificates')
TARGET=Path('/etc/demo-livekit/turn.pem')

def run(*args):
    return subprocess.run(args,check=True,capture_output=True,timeout=10)

def replace_private(data):
    with tempfile.NamedTemporaryFile(dir=TARGET.parent,prefix='.turn-',delete=False) as stream:
        tmp=Path(stream.name);os.fchmod(stream.fileno(),0o600)
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    tmp.replace(TARGET)

def verify_served(expected_der):
    # Real SNI through the complete edge, validating hostname/trust and the new leaf.
    context=ssl.create_default_context()
    for attempt in range(5):
        try:
            with socket.create_connection(('127.0.0.1',443),timeout=2) as raw:
                with context.wrap_socket(raw,server_hostname=DOMAIN) as tls:
                    assert tls.getpeercert(binary_form=True)==expected_der
            return
        except (OSError,AssertionError):
            if attempt==4:raise RuntimeError('TURN edge did not serve the expected trusted certificate') from None
            time.sleep(0.5)

def sync(no_reload=False):
    assert os.geteuid()==0
    os.umask(0o077)
    with Path('/run/demo-livekit-cert-sync.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not TARGET.is_symlink()
        candidates=list(CERTS.glob('*/'+DOMAIN+'/'+DOMAIN+'.crt'))
        assert candidates, 'Caddy has not acquired the TURN certificate yet'
        candidates.sort(key=lambda path:path.stat().st_mtime,reverse=True)
        cert=candidates[0];key=cert.with_suffix('.key')
        assert cert.resolve().is_relative_to(CERTS.resolve()) and key.resolve().is_relative_to(CERTS.resolve())
        run('openssl','x509','-in',str(cert),'-noout','-checkend','604800')
        # Verify the exact hostname and matching key before replacing a working PEM.
        match=run('openssl','x509','-in',str(cert),'-noout','-checkhost',DOMAIN).stdout
        assert b'does match certificate' in match, 'Certificate hostname mismatch'
        expected_der=run('openssl','x509','-in',str(cert),'-outform','DER').stdout
        public=run('openssl','x509','-in',str(cert),'-pubkey','-noout').stdout.strip()
        private_public=run('openssl','pkey','-in',str(key),'-pubout').stdout.strip()
        assert public==private_public, 'Certificate and private key mismatch'
        new=cert.read_bytes().rstrip()+b'\n'+key.read_bytes().rstrip()+b'\n'
        old=TARGET.read_bytes() if TARGET.exists() else None
        if old==new:
            print('TURN certificate unchanged.');return
        try:
            replace_private(new)
            if not no_reload:
                run('/usr/sbin/haproxy','-c','-f','/etc/haproxy/haproxy.cfg')
                active=subprocess.run(['systemctl','is-active','--quiet','haproxy'],capture_output=True,timeout=5).returncode==0
                if active:
                    run('systemctl','reload','haproxy')
                    verify_served(expected_der)
        except BaseException:
            if old is not None:
                replace_private(old)
                if not no_reload:
                    # The reload may have succeeded but served the wrong certificate.
                    # Independently attempt to restore the prior working listener too.
                    subprocess.run(['systemctl','reload','haproxy'],capture_output=True,timeout=10)
            else:
                TARGET.unlink(missing_ok=True)
            raise
        print('TURN certificate synchronized; private key not displayed.')

if __name__=='__main__':
    def interrupted(*_):raise InterruptedError('Certificate synchronization interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    parser=argparse.ArgumentParser();parser.add_argument('--no-reload',action='store_true')
    sync(parser.parse_args().no_reload)
