"""Trial-only ASGI runner: mocked provider mode also denies external Python sockets.

The native LiveKit RTC library does not use Python sockets; the launcher pins its
ICE configuration separately to this machine’s selected private host. This is not a system-wide firewall.
"""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import socket
import sys


def loopback_host(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


def install_socket_guard() -> None:
    def require_local(host):
        if not loopback_host(host):
            print("LIVEKIT_TRIAL_BLOCKED_EXTERNAL_SOCKET", file=sys.stderr, flush=True)
            raise OSError("External network access is disabled in the mocked LiveKit trial.")

    original_resolve = socket.getaddrinfo
    def resolve(host, *args, **kwargs):
        if host is not None:
            require_local(host)
        result = original_resolve(host, *args, **kwargs)
        if host is not None:
            for row in result:
                require_local(row[4][0])
        return result
    socket.getaddrinfo = resolve

    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)
        def connect(sock, address, _original=original):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                require_local(address[0])
            return _original(sock, address)
        setattr(socket.socket, method, connect)

    original_sendto = socket.socket.sendto
    def sendto(sock, data, *args):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            require_local(args[-1][0])
        return original_sendto(sock, data, *args)
    socket.socket.sendto = sendto


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if os.environ.get("MOCK_LLM") == "1":
        install_socket_guard()
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=int(sys.argv[1]),
                proxy_headers=False, loop="asyncio")
