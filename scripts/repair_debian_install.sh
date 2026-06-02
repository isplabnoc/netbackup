#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/netbackup-pro}"
APP_PORT="${APP_PORT:-8080}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-netaudit}"
POSTGRES_USER="${POSTGRES_USER:-netaudit}"
RESET_DB="${RESET_DB:-false}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_NAME="${ADMIN_NAME:-Admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

log() {
  printf '\033[1;34m[repair]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

random_hex_secret() {
  openssl rand -hex 32
}

random_fernet_key() {
  python3 - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
}

random_secret() {
  openssl rand -base64 48 | tr -d '\n'
}

env_value() {
  local file="$1"
  local key="$2"
  grep -E "^${key}=" "${file}" | tail -n 1 | cut -d= -f2- || true
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "${file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${file}"
  fi
}

require_project() {
  [[ -d "${APP_DIR}" ]] || fail "Diretorio nao encontrado: ${APP_DIR}"
  [[ -f "${APP_DIR}/docker-compose.yml" ]] || fail "docker-compose.yml nao encontrado em ${APP_DIR}"
  cd "${APP_DIR}"
}

update_code() {
  if [[ -d .git ]]; then
    log "Atualizando codigo via Git"
    git fetch origin main
    git reset --hard origin/main
  fi
}

write_consistent_env() {
  local env_file="${APP_DIR}/.env"
  local postgres_password
  postgres_password="${POSTGRES_PASSWORD:-$(env_value "${env_file}" "POSTGRES_PASSWORD")}"
  if [[ "${RESET_DB}" == "true" || -z "${postgres_password}" ]]; then
    postgres_password="$(random_hex_secret)"
  fi

  touch "${env_file}"
  chmod 600 "${env_file}"
  set_env_value "${env_file}" "APP_NAME" "NetBackup Pro"
  set_env_value "${env_file}" "ENVIRONMENT" "production"
  set_env_value "${env_file}" "APP_PORT" "${APP_PORT}"
  set_env_value "${env_file}" "POSTGRES_DB" "${POSTGRES_DB}"
  set_env_value "${env_file}" "POSTGRES_USER" "${POSTGRES_USER}"
  set_env_value "${env_file}" "POSTGRES_PASSWORD" "${postgres_password}"
  set_env_value "${env_file}" "POSTGRES_PORT" "${POSTGRES_PORT}"
  set_env_value "${env_file}" "DATABASE_URL" "postgresql+psycopg://${POSTGRES_USER}:${postgres_password}@postgres:5432/${POSTGRES_DB}"

  if [[ -z "$(env_value "${env_file}" "SECRET_KEY")" ]]; then
    set_env_value "${env_file}" "SECRET_KEY" "$(random_secret)"
  fi
  if [[ -z "$(env_value "${env_file}" "FERNET_KEY")" ]]; then
    set_env_value "${env_file}" "FERNET_KEY" "$(random_fernet_key)"
  fi
  set_env_value "${env_file}" "ACCESS_TOKEN_EXPIRE_MINUTES" "480"
  set_env_value "${env_file}" "BACKUP_ROOT" "/app/backups"
  set_env_value "${env_file}" "BACKUP_WORKERS" "${BACKUP_WORKERS:-30}"
  set_env_value "${env_file}" "DAILY_BACKUP_CRON_HOUR" "${DAILY_BACKUP_CRON_HOUR:-2}"
  set_env_value "${env_file}" "DAILY_BACKUP_CRON_MINUTE" "${DAILY_BACKUP_CRON_MINUTE:-0}"
}

restart_stack() {
  if [[ "${RESET_DB}" == "true" ]]; then
    log "Recriando stack e volume do Postgres"
    docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" down -v --remove-orphans
  else
    log "Recriando containers sem apagar volumes"
    docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" down --remove-orphans
  fi
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" build --no-cache app
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" up -d
}

wait_for_app() {
  log "Aguardando /docs"
  for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:${APP_PORT}/docs" >/dev/null 2>&1; then
      log "Aplicacao respondeu em http://127.0.0.1:${APP_PORT}/docs"
      return
    fi
    sleep 2
  done
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" logs app
  fail "Aplicacao nao respondeu dentro do tempo esperado"
}

bootstrap_admin() {
  if [[ -z "${ADMIN_PASSWORD}" ]]; then
    ADMIN_PASSWORD="$(random_hex_secret)"
  fi
  local payload status
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
  status="$(curl -sS -o /tmp/netbackup-bootstrap-admin.json -w "%{http_code}" \
    -X POST "http://127.0.0.1:${APP_PORT}/api/auth/bootstrap-admin" \
    -H "Content-Type: application/json" \
    -d "${payload}" || true)"
  if [[ "${status}" == "201" ]]; then
    log "Admin criado: ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}"
  elif [[ "${status}" == "409" ]]; then
    log "Admin inicial ja existe"
  else
    log "Bootstrap admin retornou HTTP ${status}"
  fi
}

main() {
  require_project
  update_code
  write_consistent_env
  restart_stack
  wait_for_app
  bootstrap_admin
  log "Reparo concluido"
}

main "$@"
