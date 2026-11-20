#!/usr/bin/env bash
# LaunchScout VPS bootstrap for Ubuntu 22.04 / 24.04. Idempotent: safe to re-run.
#
#   curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/bootstrap.sh -o bootstrap.sh
#   sudo REPO_URL=git@github.com:<owner>/<repo>.git DOMAIN=example.com \n#        TRAEFIK_NETWORK=<traefik's docker network> TRAEFIK_CERTRESOLVER=<resolver name> bash bootstrap.sh
#
# Assumes Traefik already runs on the server and owns ports 80/443 (it issues the certificate).
#
# What it does:
#   1. creates a non-root deploy user (docker group, your SSH keys)
#   2. installs Docker Engine + Compose plugin (official apt repo)
#   3. firewall: UFW allows only 22, 80, 443 (tcp) and 443/udp (HTTP/3)
#   4. fail2ban for SSH, unattended security upgrades
#   5. clones the repo (prints a read-only deploy key to add on GitHub if needed)
#   6. creates .env interactively (secrets are typed, never echoed, never committed)
#   7. installs a nightly pg_dump backup cron with 7-day retention
#   8. starts the stack behind Traefik: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
REPO_URL="${REPO_URL:?set REPO_URL, e.g. git@github.com:owner/launchscout.git}"
DOMAIN="${DOMAIN:?set DOMAIN, e.g. launchscout.example.com}"
TRAEFIK_NETWORK="${TRAEFIK_NETWORK:?set TRAEFIK_NETWORK to the docker network Traefik is attached to}"
TRAEFIK_CERTRESOLVER="${TRAEFIK_CERTRESOLVER:?set TRAEFIK_CERTRESOLVER to the certresolver name in the Traefik config}"
TRAEFIK_ENTRYPOINT="${TRAEFIK_ENTRYPOINT:-websecure}"
APP_DIR="/home/${DEPLOY_USER}/launchscout"
BRANCH="${BRANCH:-main}"

log() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)."; exit 1; }
. /etc/os-release
[[ "$ID" == "ubuntu" ]] || { echo "Ubuntu 22.04/24.04 required (found $PRETTY_NAME)."; exit 1; }
export DEBIAN_FRONTEND=noninteractive

log "Base packages"
apt-get update -y
apt-get install -y ca-certificates curl gnupg git ufw fail2ban unattended-upgrades openssl

log "Deploy user: ${DEPLOY_USER}"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
AUTH="/home/${DEPLOY_USER}/.ssh/authorized_keys"
touch "$AUTH"
for src in /root/.ssh/authorized_keys "/home/${SUDO_USER:-root}/.ssh/authorized_keys"; do
  [[ -f "$src" ]] && cat "$src" >> "$AUTH"
done
sort -u "$AUTH" -o "$AUTH"
chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH" && chmod 600 "$AUTH"

log "Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$DEPLOY_USER"
# Docker publishes ports by editing iptables directly; our compose publishes none (Traefik owns 80/443).

log "Firewall (UFW): 22, 80, 443"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

log "fail2ban (sshd)"
cat > /etc/fail2ban/jail.d/launchscout.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

log "Unattended security upgrades"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
systemctl enable --now unattended-upgrades

log "Repository"
as_deploy() { sudo -u "$DEPLOY_USER" -H bash -c "$*"; }
KEY="/home/${DEPLOY_USER}/.ssh/id_ed25519"
if [[ "$REPO_URL" == git@* && ! -f "$KEY" ]]; then
  as_deploy "ssh-keygen -t ed25519 -N '' -C 'launchscout-deploy@$(hostname)' -f '$KEY' >/dev/null"
fi
if [[ "$REPO_URL" == git@* ]]; then
  as_deploy "ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null; sort -u ~/.ssh/known_hosts -o ~/.ssh/known_hosts"
fi
if [[ ! -d "$APP_DIR/.git" ]]; then
  until as_deploy "git clone --branch '$BRANCH' '$REPO_URL' '$APP_DIR'"; do
    echo
    echo "Clone failed. If the repo is private, add this READ-ONLY deploy key on GitHub:"
    echo "  Repo -> Settings -> Deploy keys -> Add deploy key (leave 'write access' unchecked)"
    echo
    cat "${KEY}.pub"
    echo
    read -rp "Press Enter once the key is added to retry (Ctrl+C to abort)... " _
  done
else
  as_deploy "cd '$APP_DIR' && git fetch origin '$BRANCH' && git reset --hard 'origin/$BRANCH'"
fi

log "Environment file (.env)"
ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  ask_secret() { local v; read -rsp "$1: " v; echo >&2; printf '%s' "$v"; }
  echo "Enter secrets (input hidden). Leave blank to skip an optional one."
  LLM_MODEL_IN=""; read -rp "LLM_MODEL [openai/gpt-4.1]: " LLM_MODEL_IN
  SERPER=$(ask_secret "SERPER_API_KEY")
  OPENAI=$(ask_secret "OPENAI_API_KEY (if using openai/*)")
  ANTHROPIC=$(ask_secret "ANTHROPIC_API_KEY (if using anthropic/*)")
  GEMINI=$(ask_secret "GEMINI_API_KEY (if using gemini/*)")
  PGPASS=$(openssl rand -hex 24)
  sed \
    -e "s#^LLM_MODEL=.*#LLM_MODEL=${LLM_MODEL_IN:-openai/gpt-4.1}#" \
    -e "s#^SERPER_API_KEY=.*#SERPER_API_KEY=${SERPER}#" \
    -e "s#^OPENAI_API_KEY=.*#OPENAI_API_KEY=${OPENAI}#" \
    -e "s#^ANTHROPIC_API_KEY=.*#ANTHROPIC_API_KEY=${ANTHROPIC}#" \
    -e "s#^GEMINI_API_KEY=.*#GEMINI_API_KEY=${GEMINI}#" \
    -e "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=${PGPASS}#" \
    -e "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://launchscout:${PGPASS}@postgres:5432/launchscout#" \
    -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=https://${DOMAIN}#" \
    -e "s#^TRUST_PROXY_HEADERS=.*#TRUST_PROXY_HEADERS=true#" \
    -e "s#^NEXT_PUBLIC_API_BASE=.*#NEXT_PUBLIC_API_BASE=#" \
    -e "s#^NEXT_PUBLIC_SITE_URL=.*#NEXT_PUBLIC_SITE_URL=https://${DOMAIN}#" \
    -e "s#^DOMAIN=.*#DOMAIN=${DOMAIN}#" \
    -e "s#^TRAEFIK_NETWORK=.*#TRAEFIK_NETWORK=${TRAEFIK_NETWORK}#" \
    -e "s#^TRAEFIK_CERTRESOLVER=.*#TRAEFIK_CERTRESOLVER=${TRAEFIK_CERTRESOLVER}#" \
    -e "s#^TRAEFIK_ENTRYPOINT=.*#TRAEFIK_ENTRYPOINT=${TRAEFIK_ENTRYPOINT}#" \
    "$APP_DIR/.env.example" > "$ENV_FILE"
  unset SERPER OPENAI ANTHROPIC GEMINI PGPASS
  chown "$DEPLOY_USER:$DEPLOY_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Wrote $ENV_FILE (mode 600)."
else
  echo ".env already exists, left unchanged."
fi

log "Nightly Postgres backup (7-day retention)"
install -d -m 750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/backups"
CRON_LINE="17 3 * * * ${APP_DIR}/deploy/backup.sh >> /home/${DEPLOY_USER}/backups/backup.log 2>&1"
( crontab -u "$DEPLOY_USER" -l 2>/dev/null | grep -v 'deploy/backup.sh' ; echo "$CRON_LINE" ) | crontab -u "$DEPLOY_USER" -
chmod +x "$APP_DIR/deploy/backup.sh"

log "Starting the stack"
docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 || { echo "Docker network $TRAEFIK_NETWORK not found. Is Traefik running?"; exit 1; }
as_deploy "cd '$APP_DIR' && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"

log "Done"
echo "Check:  curl -fsS https://${DOMAIN}/api/health"
echo "Logs:   sudo -u ${DEPLOY_USER} docker compose -f ${APP_DIR}/docker-compose.yml -f ${APP_DIR}/docker-compose.prod.yml logs -f"
