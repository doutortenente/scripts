#!/usr/bin/env bash
# Confere a stack do Tijolão. Desde out-2026 o Hermes e o Workspace rodam em Docker
# (receita em ~/.config/hermes-stack, sobe com `tijolao up`); os antigos serviços
# systemd hermes-*.service não existem mais. n8n só é conferido se estiver no ar.
# Saída: número de FAILs (0 = tudo certo). Uso: verify-stack.sh [--deep]
set -uo pipefail

FAILURES=0
DEEP=false
COFRE=/home/dr/.local/secrets/.env

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
skip() { printf 'SKIP %s\n' "$1"; }

check_container() {
  local estado saude
  estado=$(docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null)
  saude=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$1" 2>/dev/null)
  if [[ "$estado" == running && ( -z "$saude" || "$saude" == healthy ) ]]; then
    ok "contêiner $1 (${saude:-sem healthcheck})"
  else
    fail "contêiner $1 (${estado:-ausente}${saude:+/$saude})"
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

n8n_no_ar() { curl --silent --max-time 3 http://127.0.0.1:5678/healthz >/dev/null 2>&1; }

check_container hermes-agent
check_container hermes-workspace

check_http "Hermes API :8642" "http://127.0.0.1:8642/health"
check_http "Dashboard :9119" "http://127.0.0.1:9119/api/status"
check_http "Workspace :3000" "http://127.0.0.1:3000/api/sessions"

if n8n_no_ar; then
  ok "n8n :5678"
  check_http "webhook n8n → Hermes (saúde)" "http://127.0.0.1:5678/webhook/hermes-health"
else
  skip "n8n :5678 desligado (não é serviço nem contêiner hoje)"
fi

# Captura antes do grep: com pipefail, o grep -q fecha o cano cedo e o SIGPIPE vira falso FAIL.
auth_out=$(/home/dr/.local/bin/hermes auth list </dev/null 2>/dev/null)
if grep -q 'credentials' <<<"$auth_out"; then
  ok "Hermes tem credencial de modelo"
else
  fail "Hermes tem credencial de modelo"
fi

for secret_spec in \
  "$COFRE|API_SERVER_KEY" \
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

# O Workspace recebe HERMES_API_TOKEN do compose (= API_SERVER_KEY do cofre).
# Compara só o hash, para o valor nunca aparecer na tela.
hermes_hash=$(sed -n 's/^API_SERVER_KEY=//p' "$COFRE" 2>/dev/null | tail -n 1 | sha256sum)
workspace_hash=$(docker exec hermes-workspace printenv HERMES_API_TOKEN 2>/dev/null | sha256sum)
if [[ -n "$(sed -n 's/^API_SERVER_KEY=//p' "$COFRE" 2>/dev/null)" && "$hermes_hash" == "$workspace_hash" ]]; then
  ok "token Hermes ↔ Workspace coincide"
else
  fail "token Hermes ↔ Workspace coincide"
fi
unset hermes_hash workspace_hash

if $DEEP; then
  API_SERVER_KEY=$(sed -n 's/^API_SERVER_KEY=//p' "$COFRE" 2>/dev/null | tail -n 1)
  payload='{"model":"hermes-agent","messages":[{"role":"user","content":"Responda exatamente STACK_OK"}]}'
  if [[ -n ${API_SERVER_KEY:-} ]] &&
    curl --silent --show-error --fail --max-time 120 \
      -H "Authorization: Bearer ${API_SERVER_KEY}" \
      -H "Content-Type: application/json" \
      --data "$payload" \
      http://127.0.0.1:8642/v1/chat/completions |
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["choices"][0]["message"]["content"].strip()=="STACK_OK"'
  then
    ok "chamada profunda Hermes → modelo"
  else
    fail "chamada profunda Hermes → modelo"
  fi
  unset API_SERVER_KEY payload

  if ! n8n_no_ar; then
    skip "chamada profunda n8n → Hermes (n8n desligado)"
  elif [[ ! -f /home/dr/.config/n8n/webhook.env ]]; then
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
      ok "chamada profunda n8n → Hermes → modelo"
    else
      fail "chamada profunda n8n → Hermes → modelo"
    fi
    unset N8N_HERMES_WEBHOOK_SECRET n8n_payload
  fi
fi

exit "$FAILURES"
