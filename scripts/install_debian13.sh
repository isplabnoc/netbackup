#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-NetBackup Pro}"
APP_DIR="${APP_DIR:-/opt/netbackup-pro}"
APP_PORT="${APP_PORT:-8080}"
REPO_URL="${REPO_URL:-}"
REPO_REF="${REPO_REF:-main}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_NAME="${ADMIN_NAME:-Admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-netaudit}"
POSTGRES_USER="${POSTGRES_USER:-netaudit}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
BACKUP_WORKERS="${BACKUP_WORKERS:-30}"
DAILY_BACKUP_CRON_HOUR="${DAILY_BACKUP_CRON_HOUR:-2}"
DAILY_BACKUP_CRON_MINUTE="${DAILY_BACKUP_CRON_MINUTE:-0}"
INSTALL_UFW="${INSTALL_UFW:-false}"
START_STACK="${START_STACK:-true}"

log() {
  printf '\033[1;34m[install]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Execute como root: sudo bash scripts/install_debian13.sh"
  fi
}

detect_debian() {
  if [[ ! -r /etc/os-release ]]; then
    fail "Nao foi possivel detectar o sistema operacional."
  fi
  . /etc/os-release
  if [[ "${ID:-}" != "debian" ]]; then
    fail "Este instalador foi feito para Debian. Detectado: ${PRETTY_NAME:-desconhecido}"
  fi
  if [[ "${VERSION_ID:-}" != "13" ]]; then
    warn "Debian 13 era esperado. Detectado: ${PRETTY_NAME:-desconhecido}. Continuando mesmo assim."
  fi
  DEBIAN_CODENAME="${VERSION_CODENAME:-trixie}"
}

random_urlsafe_fernet_key() {
  python3 - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
}

random_secret() {
  openssl rand -base64 48 | tr -d '\n'
}

install_base_packages() {
  log "Atualizando pacotes base"
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release git rsync openssl python3
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker e Docker Compose ja estao instalados"
    return
  fi

  log "Instalando Docker Engine e Docker Compose plugin"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${DEBIAN_CODENAME} stable
EOF

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

prepare_app_dir() {
  log "Preparando diretorio ${APP_DIR}"
  mkdir -p "${APP_DIR}"

  if [[ -n "${REPO_URL}" ]]; then
    if [[ -d "${APP_DIR}/.git" ]]; then
      log "Atualizando repositorio existente"
      git -C "${APP_DIR}" fetch --all --prune
      git -C "${APP_DIR}" checkout "${REPO_REF}"
      git -C "${APP_DIR}" pull --ff-only origin "${REPO_REF}"
    else
      log "Clonando ${REPO_URL}"
      rm -rf "${APP_DIR:?}/"*
      git clone --branch "${REPO_REF}" "${REPO_URL}" "${APP_DIR}"
    fi
  elif [[ -f "./docker-compose.yml" && -d "./app" ]]; then
    log "Copiando projeto do diretorio atual para ${APP_DIR}"
    rsync -a \
      --exclude ".git" \
      --exclude ".env" \
      --exclude "backups" \
      --exclude "logs" \
      --exclude "work" \
      --exclude "outputs" \
      ./ "${APP_DIR}/"
  elif [[ -f "${APP_DIR}/docker-compose.yml" && -d "${APP_DIR}/app" ]]; then
    log "Projeto ja existe em ${APP_DIR}"
  else
    fail "Informe REPO_URL ou execute este script dentro da pasta do projeto."
  fi

  mkdir -p "${APP_DIR}/backups" "${APP_DIR}/logs"
}

write_env() {
  local env_file="${APP_DIR}/.env"

  if [[ -z "${POSTGRES_PASSWORD}" ]]; then
    POSTGRES_PASSWORD="$(random_secret)"
  fi
  if [[ -z "${ADMIN_PASSWORD}" ]]; then
    ADMIN_PASSWORD="$(random_secret)"
  fi

  log "Gerando ${env_file}"
  cat >"${env_file}" <<EOF
APP_NAME=${APP_NAME}
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
SECRET_KEY=$(random_secret)
FERNET_KEY=$(random_urlsafe_fernet_key)
ACCESS_TOKEN_EXPIRE_MINUTES=480
BACKUP_ROOT=/app/backups
BACKUP_WORKERS=${BACKUP_WORKERS}
DAILY_BACKUP_CRON_HOUR=${DAILY_BACKUP_CRON_HOUR}
DAILY_BACKUP_CRON_MINUTE=${DAILY_BACKUP_CRON_MINUTE}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}
EVOLUTION_API_URL=${EVOLUTION_API_URL:-}
EVOLUTION_API_TOKEN=${EVOLUTION_API_TOKEN:-}
EVOLUTION_API_INSTANCE=${EVOLUTION_API_INSTANCE:-}
EOF

  chmod 600 "${env_file}"
}

patch_compose_for_production() {
  log "Ajustando docker-compose.yml para porta ${APP_PORT} e senha do PostgreSQL"
  python3 - "${APP_DIR}/docker-compose.yml" "${APP_PORT}" "${POSTGRES_DB}" "${POSTGRES_USER}" "${POSTGRES_PASSWORD}" <<'PY'
from pathlib import Path
import sys

compose = Path(sys.argv[1])
app_port, db, user, password = sys.argv[2:6]
text = compose.read_text()
text = text.replace('      POSTGRES_DB: netaudit', f'      POSTGRES_DB: {db}')
text = text.replace('      POSTGRES_USER: netaudit', f'      POSTGRES_USER: {user}')
text = text.replace('      POSTGRES_PASSWORD: netaudit', f'      POSTGRES_PASSWORD: {password}')
text = text.replace('      - "8080:80"', f'      - "{app_port}:80"')
compose.write_text(text)
PY
}

configure_firewall() {
  if [[ "${INSTALL_UFW}" != "true" ]]; then
    return
  fi

  log "Configurando UFW"
  apt-get install -y ufw
  ufw allow OpenSSH
  ufw allow "${APP_PORT}/tcp"
  ufw --force enable
}

start_stack() {
  if [[ "${START_STACK}" != "true" ]]; then
    warn "START_STACK=false, containers nao foram iniciados."
    return
  fi

  log "Subindo containers"
  docker compose -f "${APP_DIR}/docker-compose.yml" --env-file "${APP_DIR}/.env" up -d --build

  log "Aguardando aplicacao responder"
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${APP_PORT}/docs" >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done

  warn "A aplicacao ainda nao respondeu em /docs. Verifique: docker compose -f ${APP_DIR}/docker-compose.yml logs app"
}

bootstrap_admin() {
  if [[ "${START_STACK}" != "true" ]]; then
    return
  fi

  log "Criando usuario administrador inicial se ainda nao existir"
  local payload
  payload="$(python3 - "${ADMIN_EMAIL}" "${ADMIN_NAME}" "${ADMIN_PASSWORD}" <<'PY'
import json
import sys
print(json.dumps({
    "email": sys.argv[1],
    "full_name": sys.argv[2],
    "password": sys.argv[3],
    "role": "Admin",
}))
PY
)"

  local status
  status="$(curl -sS -o /tmp/netbackup-bootstrap-admin.json -w "%{http_code}" \
    -X POST "http://127.0.0.1:${APP_PORT}/api/auth/bootstrap-admin" \
    -H "Content-Type: application/json" \
    -d "${payload}" || true)"

  if [[ "${status}" == "201" ]]; then
    log "Administrador criado com sucesso"
  elif [[ "${status}" == "409" ]]; then
    warn "Administrador inicial ja existe, bootstrap ignorado"
  else
    warn "Nao foi possivel criar admin inicial. HTTP ${status}. Resposta em /tmp/netbackup-bootstrap-admin.json"
  fi
}

print_summary() {
  cat <<EOF

Instalacao concluida.

URL:              http://SEU_SERVIDOR:${APP_PORT}
Diretorio:        ${APP_DIR}
Usuario admin:    ${ADMIN_EMAIL}
Senha admin:      ${ADMIN_PASSWORD}

Comandos uteis:
  docker compose -f ${APP_DIR}/docker-compose.yml ps
  docker compose -f ${APP_DIR}/docker-compose.yml logs -f app
  docker compose -f ${APP_DIR}/docker-compose.yml restart
  docker compose -f ${APP_DIR}/docker-compose.yml exec app alembic upgrade head

Arquivos importantes:
  ${APP_DIR}/.env
  ${APP_DIR}/backups
  ${APP_DIR}/logs

EOF
}

main() {
  require_root
  detect_debian
  install_base_packages
  install_docker
  prepare_app_dir
  write_env
  patch_compose_for_production
  configure_firewall
  start_stack
  bootstrap_admin
  print_summary
}

main "$@"
