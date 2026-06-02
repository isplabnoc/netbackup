#!/usr/bin/env bash
set -Eeuo pipefail

REPO_NAME="${REPO_NAME:-netbackup-pro}"
PRIVATE="${PRIVATE:-true}"
GITHUB_ORG="${GITHUB_ORG:-}"
GITHUB_API="${GITHUB_API:-https://api.github.com}"

log() {
  printf '\033[1;34m[github]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

require_token() {
  if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    fail "Defina GITHUB_TOKEN com permissao para criar repositorios e fazer push."
  fi
}

api() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  if [[ -n "${body}" ]]; then
    curl -fsS \
      -X "${method}" \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      -H "Content-Type: application/json" \
      -d "${body}" \
      "${GITHUB_API}${path}"
  else
    curl -fsS \
      -X "${method}" \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${GITHUB_API}${path}"
  fi
}

json_value() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

ensure_git_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git init
    git branch -M main
  fi

  if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    git add .
    git commit -m "Initial NetBackup Pro platform"
  fi
}

create_repo() {
  local private_json="false"
  if [[ "${PRIVATE}" == "true" ]]; then
    private_json="true"
  fi

  local payload
  payload="$(python3 - "${REPO_NAME}" "${private_json}" <<'PY'
import json
import sys
print(json.dumps({
    "name": sys.argv[1],
    "private": sys.argv[2] == "true",
    "description": "Enterprise network device backup and audit platform",
    "has_issues": True,
    "has_projects": False,
    "has_wiki": False,
}))
PY
)"

  local response owner
  if [[ -n "${GITHUB_ORG}" ]]; then
    log "Criando repositorio ${GITHUB_ORG}/${REPO_NAME}"
    response="$(api POST "/orgs/${GITHUB_ORG}/repos" "${payload}" || true)"
    owner="${GITHUB_ORG}"
  else
    log "Criando repositorio pessoal ${REPO_NAME}"
    response="$(api POST "/user/repos" "${payload}" || true)"
    owner="$(api GET "/user" | json_value login)"
  fi

  if [[ -z "${response}" ]]; then
    warn_existing_repo "${owner}"
    return
  fi

  if printf '%s' "${response}" | grep -q '"full_name"'; then
    log "Repositorio criado"
  else
    printf '%s\n' "${response}" >&2
    fail "Falha ao criar repositorio. Veja a resposta acima."
  fi
}

warn_existing_repo() {
  local owner="$1"
  log "Se o repositorio ja existir, vou tentar usar ${owner}/${REPO_NAME}"
}

configure_remote_and_push() {
  local owner
  if [[ -n "${GITHUB_ORG}" ]]; then
    owner="${GITHUB_ORG}"
  else
    owner="$(api GET "/user" | json_value login)"
  fi

  local remote_url="https://github.com/${owner}/${REPO_NAME}.git"

  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "${remote_url}"
  else
    git remote add origin "${remote_url}"
  fi

  log "Publicando branch main em ${remote_url}"
  git -c credential.helper= \
    -c "http.https://github.com/.extraheader=AUTHORIZATION: Bearer ${GITHUB_TOKEN}" \
    push -u origin main

  log "Pronto: ${remote_url}"
}

main() {
  require_token
  ensure_git_repo
  create_repo
  configure_remote_and_push
}

main "$@"
