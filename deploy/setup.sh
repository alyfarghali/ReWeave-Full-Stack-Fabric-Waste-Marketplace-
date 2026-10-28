#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 26.04 portfolio server. Run as root:
#
#   scp deploy/{setup.sh,compose.yml,Caddyfile} root@SERVER:/root/
#   ssh root@SERVER 'DEPLOY_PUBKEY="ssh-ed25519 AAAA..." bash /root/setup.sh'
#
# DEPLOY_PUBKEY is the public half of the key GitHub Actions deploys with.
# Safe to re-run: existing secrets and data are kept.
set -euo pipefail

APP_DIR=/opt/portfolio
: "${DEPLOY_PUBKEY:?Set DEPLOY_PUBKEY to the public half of the CI deploy key}"

echo "==> System packages and automatic security updates"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -yq
apt-get install -yq ca-certificates curl ufw unattended-upgrades
cat > /etc/apt/apt.conf.d/52portfolio-upgrades <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
systemctl enable --now unattended-upgrades

echo "==> Docker from Docker's own repository"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
cat > /etc/docker/daemon.json <<'EOF'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
EOF
systemctl restart docker

echo "==> Firewall: SSH, HTTP, HTTPS only"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "==> SSH: keys only"
cat > /etc/ssh/sshd_config.d/99-portfolio.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
systemctl reload ssh

echo "==> Deploy user for GitHub Actions"
id deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --groups docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
grep -qxF "$DEPLOY_PUBKEY" /home/deploy/.ssh/authorized_keys 2>/dev/null \
  || echo "$DEPLOY_PUBKEY" >> /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

echo "==> Stack files and secrets in $APP_DIR"
install -d -m 750 -o deploy -g deploy "$APP_DIR" "$APP_DIR/backups"
install -m 640 -o deploy -g deploy /root/compose.yml "$APP_DIR/compose.yml"
install -m 640 -o deploy -g deploy /root/Caddyfile "$APP_DIR/Caddyfile"
if [ ! -f "$APP_DIR/.env" ]; then
  umask 077
  cat > "$APP_DIR/.env" <<EOF
REWEAVE_DB_PASSWORD=$(openssl rand -hex 24)
REWEAVE_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
# Paid AI keys. Leave empty until spend caps are set in each provider's dashboard.
REWEAVE_OPENROUTER_API_KEY=
REWEAVE_REPLICATE_API_TOKEN=
EOF
  chown deploy:deploy "$APP_DIR/.env"
fi

echo "==> Nightly database backup (14 days kept) and weekly image cleanup"
cat > /etc/cron.d/portfolio <<EOF
15 3 * * * deploy cd $APP_DIR && docker compose exec -T reweave-db pg_dump -U reweave reweave | gzip > backups/reweave-\$(date +\%F).sql.gz && find backups -name '*.sql.gz' -mtime +14 -delete
30 4 * * 0 root docker image prune -af --filter until=168h >/dev/null
EOF

echo "==> Starting Caddy and the database (the first CI deploy starts Reweave)"
cd "$APP_DIR"
sudo -u deploy docker compose up -d caddy reweave-db

echo "Done. Server is ready for the GitHub Actions deploy."
