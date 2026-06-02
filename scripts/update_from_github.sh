#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/netbackup-pro}"
OWNER="${OWNER:-isplabnoc}"
REPOSITORY="${REPOSITORY:-netbackup}"
BRANCH="${BRANCH:-main}"
APP_PORT="${APP_PORT:-8080}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

log() {
  printf '\033[1;34m[update]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Execute como root."
  fi
}

require_project() {
  [[ -d "${APP_DIR}" ]] || fail "Diretorio nao encontrado: ${APP_DIR}"
  [[ -f "${APP_DIR}/.env" ]] || fail ".env nao encontrado em ${APP_DIR}"
  command -v curl >/dev/null 2>&1 || fail "curl nao instalado"
  command -v tar >/dev/null 2>&1 || fail "tar nao instalado"
  command -v docker >/dev/null 2>&1 || fail "docker nao instalado"
}

download_source() {
  local tmp_dir="$1"
  local archive="${tmp_dir}/source.tar.gz"
  local url="https://github.com/${OWNER}/${REPOSITORY}/archive/refs/heads/${BRANCH}.tar.gz"
  local curl_args=(-fsSL "${url}" -o "${archive}")

  if [[ -n "${GITHUB_TOKEN}" ]]; then
    curl_args=(-fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" "${url}" -o "${archive}")
  fi

  log "Baixando codigo de ${OWNER}/${REPOSITORY}:${BRANCH}"
  if ! curl "${curl_args[@]}"; then
    fail "Download falhou. Se o repositorio for privado, execute com GITHUB_TOKEN=seu_token."
  fi

  tar -xzf "${archive}" -C "${tmp_dir}"
  local extracted="${tmp_dir}/${REPOSITORY}-${BRANCH}"
  [[ -d "${extracted}" ]] || fail "Arquivo baixado nao contem ${REPOSITORY}-${BRANCH}"
  printf '%s\n' "${extracted}"
}

replace_code() {
  local source_dir="$1"
  local env_backup backup_dir logs_dir
  env_backup="$(mktemp)"
  backup_dir="$(mktemp -d)"
  logs_dir="$(mktemp -d)"

  cp "${APP_DIR}/.env" "${env_backup}"
  if [[ -d "${APP_DIR}/backups" ]]; then
    cp -a "${APP_DIR}/backups/." "${backup_dir}/"
  fi
  if [[ -d "${APP_DIR}/logs" ]]; then
    cp -a "${APP_DIR}/logs/." "${logs_dir}/"
  fi

  log "Substituindo codigo em ${APP_DIR}"
  find "${APP_DIR}" -mindepth 1 \
    ! -name ".env" \
    ! -name "backups" \
    ! -name "logs" \
    ! -name "postgres_data" \
    -exec rm -rf {} +

  cp -a "${source_dir}/." "${APP_DIR}/"
  cp "${env_backup}" "${APP_DIR}/.env"
  mkdir -p "${APP_DIR}/backups" "${APP_DIR}/logs"
  cp -a "${backup_dir}/." "${APP_DIR}/backups/" || true
  cp -a "${logs_dir}/." "${APP_DIR}/logs/" || true
  chmod +x "${APP_DIR}/scripts/"*.sh
}

rebuild_stack() {
  log "Recriando imagem e containers"
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" down --remove-orphans
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" build --no-cache app
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" run --rm --entrypoint alembic app upgrade head
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" up -d --force-recreate
}

verify() {
  log "Aguardando aplicacao"
  for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:${APP_PORT}/health" >/dev/null 2>&1; then
      log "Aplicacao respondeu em /health"
      return
    fi
    sleep 2
  done
  docker compose --env-file "${APP_DIR}/.env" -f "${APP_DIR}/docker-compose.yml" logs --tail=160 app
  fail "Aplicacao nao respondeu em /health"
}

main() {
  require_root
  require_project
  local tmp_dir source_dir
  tmp_dir="$(mktemp -d)"
  source_dir="$(download_source "${tmp_dir}")"
  replace_code "${source_dir}"
  rebuild_stack
  verify
  log "Atualizacao concluida: http://SEU_SERVIDOR:${APP_PORT}"
}

main "$@"
