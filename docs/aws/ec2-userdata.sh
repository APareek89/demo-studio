#!/bin/bash
# Runs once, automatically, the first time the instance boots. Installs everything
# the app needs. The app code, the keys and the HTTPS hostname are pushed afterwards.
set -eux
exec > /var/log/demo-studio-setup.log 2>&1

# 1 GB of RAM is not enough for ffmpeg transcodes. A 2 GB swap file stops it being killed.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

dnf -y update
dnf -y install python3.11 python3.11-pip git tar gzip

# Caddy: the web server in front. It gets and renews the HTTPS certificate on its own,
# which is what lets the browser hand the microphone to the player.
ARCH=$(uname -m); case "$ARCH" in x86_64) CADDY_ARCH=amd64 ;; aarch64) CADDY_ARCH=arm64 ;; esac
curl -sSL "https://github.com/caddyserver/caddy/releases/download/v2.8.4/caddy_2.8.4_linux_${CADDY_ARCH}.tar.gz" \
  -o /tmp/caddy.tgz
tar -xzf /tmp/caddy.tgz -C /tmp caddy && install -m 0755 /tmp/caddy /usr/bin/caddy
useradd --system --home /var/lib/caddy --create-home caddy || true
mkdir -p /etc/caddy

install -d -o ec2-user -g ec2-user /opt/demo-studio

# The app runs as a normal user on localhost:8877; Caddy is the only thing exposed.
cat > /etc/systemd/system/demo-studio.service <<'UNIT'
[Unit]
Description=Demo Studio
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/demo-studio
EnvironmentFile=-/opt/demo-studio/.env
ExecStart=/opt/demo-studio/.venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8877
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/caddy.service <<'UNIT'
[Unit]
Description=Caddy
After=network.target

[Service]
User=caddy
Group=caddy
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --force
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
touch /var/lib/demo-studio-base-ready
