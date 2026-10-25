#!/usr/bin/env bash
set -uo pipefail

FAILURES=0
DEEP=false

if (( $# > 1 )); then
  echo "Uso: $0 [--deep]" >&2
  exit 2
fi
case "${1:-}" in
  "") ;;
  --deep) DEEP=true ;;
  *) echo "Uso: $0 [--deep]" >&2; exit 2 ;;
esac

ok() { printf 'OK   %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

configure_user_bus() {
  if systemctl --user show-environment >/dev/null 2>&1; then
    return 0
  fi

  local runtime_dir="/run/user/$(id -u)"
  if [[ -S "$runtime_dir/bus" ]]; then
    export XDG_RUNTIME_DIR="$runtime_dir"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus"
  fi
}

check_service() {
  if systemctl --user is-active --quiet "$1"; then
    ok "serviço $1"
  else
    fail "serviço $1"
  fi
}

check_http() {
  if curl --silent --show-error --fail --max-time 8 "$2" >/dev/null; then
    ok "$1"
  else
    fail "$1"
  fi
}

has_env_value() {
  local file="$1"
  local key="$2"
  awk -F= -v wanted="$key" '
    $1 == wanted && length(substr($0, index($0, "=") + 1)) > 0 { found=1 }
    END { exit(found ? 0 : 1) }
  ' "$file"
}

configure_user_bus

check_service hermes-gateway.service
check_service hermes-dashboard.service
check_service hermes-workspace.service
check_service n8n.service

check_http "Hermes API :8642" "http://127.0.0.1:8642/health"
dashboard_host=$(systemctl --user show hermes-dashboard.service -p ExecStart --value 2>/dev/null |
  sed -n 's/.*--host \([^ ;}]*\).*/\1/p')
dashboard_host=${dashboard_host:-127.0.0.1}
check_http "Dashboard :9119" "http://${dashboard_host}:9119/api/status"
check_http "Workspace :3000" "http://127.0.0.1:3000/api/sessions"
check_http "n8n :5678" "http://127.0.0.1:5678/healthz"
check_http "webhook n8n → Hermes (saúde)" "http://127.0.0.1:5678/webhook/hermes-health"

if codex login status >/dev/null 2>&1; then
  ok "OAuth do Codex"
else
  fail "OAuth do Codex"
fi

if hermes auth list openai-codex >/dev/null 2>&1; then
  ok "credencial openai-codex do Hermes"
else
  fail "credencial openai-codex do Hermes"
fi

for secret_spec in \
  '/home/dr/.hermes/.env|API_SERVER_KEY' \
  '/home/dr/src/hermes-workspace/.env|HERMES_API_TOKEN' \
  '/home/dr/.config/n8n/n8n.env|N8N_ENCRYPTION_KEY' \
  '/home/dr/.config/n8n/webhook.env|N8N_HERMES_WEBHOOK_SECRET'; do
  secret_file="${secret_spec%%|*}"
  secret_key="${secret_spec#*|}"
  if [[ -f "$secret_file" && $(stat -Lc '%a' "$secret_file" 2>/dev/null) == "600" ]]; then
    ok "permissão 0600 em $secret_file"
  else
    fail "permissão 0600 em $secret_file"
  fi
  if [[ -f "$secret_file" ]] && has_env_value "$secret_file" "$secret_key"; then
    ok "$secret_key presente"
  else
    fail "$secret_key presente"
  fi
done

if [[ -f /home/dr/.hermes/.env && -f /home/dr/src/hermes-workspace/.env ]]; then
  hermes_key=$(sed -n 's/^API_SERVER_KEY=//p' /home/dr/.hermes/.env | tail -n 1)
  workspace_key=$(sed -n 's/^HERMES_API_TOKEN=//p' /home/dr/src/hermes-workspace/.env | tail -n 1)
  if [[ -n "$hermes_key" && "$hermes_key" == "$workspace_key" ]]; then
    ok "token Hermes ↔ Workspace coincide"
  else
    fail "token Hermes ↔ Workspace coincide"
  fi
  unset hermes_key workspace_key
fi

if $DEEP; then
  if [[ ! -f /home/dr/.hermes/.env ]]; then
    fail "arquivo de ambiente do Hermes para teste profundo"
  else
    set -a
    # shellcheck disable=SC1091
    source /home/dr/.hermes/.env
    set +a
    payload='{"model":"hermes-agent","messages":[{"role":"user","content":"Responda exatamente STACK_OK"}]}'
    if [[ -n ${API_SERVER_KEY:-} ]] &&
      curl --silent --show-error --fail --max-time 120 \
        -H "Authorization: Bearer ${API_SERVER_KEY}" \
        -H "Content-Type: application/json" \
        --data "$payload" \
        http://127.0.0.1:8642/v1/chat/completions |
      python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["choices"][0]["message"]["content"].strip()=="STACK_OK"'
    then
      ok "chamada profunda Hermes → 9Router → Codex"
    else
      fail "chamada profunda Hermes → 9Router → Codex"
    fi
    unset API_SERVER_KEY payload
  fi

  if [[ ! -f /home/dr/.config/n8n/webhook.env ]]; then
    fail "arquivo de ambiente do webhook n8n para teste profundo"
  else
    set -a
    # shellcheck disable=SC1091
    source /home/dr/.config/n8n/webhook.env
    set +a
    n8n_payload='{"message":"Responda exatamente N8N_HERMES_OK"}'
    if [[ -n ${N8N_HERMES_WEBHOOK_SECRET:-} ]] &&
      curl --silent --show-error --fail --max-time 120 \
        -H "Content-Type: application/json" \
        -H "X-Tijolao-Webhook: ${N8N_HERMES_WEBHOOK_SECRET}" \
        --data "$n8n_payload" \
        http://127.0.0.1:5678/webhook/hermes-ask |
      python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["choices"][0]["message"]["content"].strip()=="N8N_HERMES_OK"'
    then
      ok "chamada profunda n8n → Hermes → 9Router → Codex"
    else
      fail "chamada profunda n8n → Hermes → 9Router → Codex"
    fi
    unset N8N_HERMES_WEBHOOK_SECRET n8n_payload
  fi
fi

exit "$FAILURES"
