#!/usr/bin/env bash
set -euo pipefail
umask 077

N8N_WORKFLOWS_DIR="${N8N_WORKFLOWS_DIR:-/home/dr/.local/share/n8n/workflows}"
N8N_HOME_DIR="${N8N_HOME_DIR:-/home/dr/.local/share/n8n/.n8n}"
N8N_CONFIG_DIR="${N8N_CONFIG_DIR:-/home/dr/.config/n8n}"
HERMES_ENV_FILE="${HERMES_ENV_FILE:-/home/dr/.hermes/.env}"
N8N_ENV_FILE="$N8N_CONFIG_DIR/n8n.env"
OWNER_ENV_FILE="$N8N_CONFIG_DIR/owner.env"
WEBHOOK_ENV_FILE="$N8N_CONFIG_DIR/webhook.env"
N8N_NODE="/home/dr/.local/share/nvm/versions/node/v24.16.0/bin/node"
N8N_CLI="/home/dr/.local/share/nvm/versions/node/v24.16.0/lib/node_modules/n8n/bin/n8n"
HERMES_PYTHON="/home/dr/.hermes/hermes-agent/venv/bin/python"
EXPECTED_N8N_VERSION="2.32.5"
HERMES_CREDENTIAL_ID="cc3af26f-27e8-4ca7-9d55-0734fd9d182a"
WEBHOOK_CREDENTIAL_ID="50b4af75-020e-41c1-84a9-aec2572cc4f1"
HEALTH_WORKFLOW_ID="429bfc89-c8cc-4112-b817-9366e507cf6f"
ASK_WORKFLOW_ID="8ecf1c92-959b-45a8-a5e8-7bbb50b57f8f"
TEMP_DIR="$(mktemp -d /tmp/tijolao-n8n.XXXXXX)"
SERVICE_STOPPED=0
MUTATION_STARTED=0
INSTALL_SUCCESS=0
backup_path=""

cleanup() {
  local status=$?
  if (( status != 0 && MUTATION_STARTED && ! INSTALL_SUCCESS )) && [[ -f "$backup_path" ]]; then
    echo "Falha durante a instalação; restaurando o backup validado do n8n." >&2
    systemctl --user stop n8n.service >/dev/null 2>&1 || true
    SERVICE_STOPPED=1
    "$HERMES_PYTHON" - "$backup_path" "$N8N_HOME_DIR/database.sqlite" <<'PY' || true
import os
import sqlite3
import sys

source_path, target_path = sys.argv[1:]
temporary_path = f"{target_path}.rollback"
if os.path.exists(temporary_path):
    os.unlink(temporary_path)
source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
target = sqlite3.connect(temporary_path)
try:
    source.backup(target)
    target.commit()
    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Restauração do banco n8n falhou no integrity_check")
finally:
    target.close()
    source.close()
os.chmod(temporary_path, 0o600)
os.replace(temporary_path, target_path)
for suffix in ("-wal", "-shm"):
    stale_path = f"{target_path}{suffix}"
    if os.path.exists(stale_path):
        os.unlink(stale_path)
PY
  fi
  if (( SERVICE_STOPPED )); then
    systemctl --user start n8n.service >/dev/null 2>&1 || true
  fi
  if [[ -n "$TEMP_DIR" && "$TEMP_DIR" == /tmp/tijolao-n8n.* && -d "$TEMP_DIR" ]]; then
    rm -rf -- "$TEMP_DIR"
  fi
  return "$status"
}
trap cleanup EXIT

configure_user_bus() {
  if systemctl --user show-environment >/dev/null 2>&1; then
    return 0
  fi

  local runtime_dir="/run/user/$(id -u)"
  if [[ ! -S "$runtime_dir/bus" ]]; then
    echo "Barramento systemd do usuário indisponível em $runtime_dir/bus" >&2
    return 1
  fi

  export XDG_RUNTIME_DIR="$runtime_dir"
  export DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus"
  systemctl --user show-environment >/dev/null
}

wait_http() {
  local url="$1"
  local attempts="${2:-45}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl --silent --show-error --fail --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

for dependency in curl jq stat; do
  command -v "$dependency" >/dev/null
done
for required_file in "$HERMES_ENV_FILE" "$N8N_ENV_FILE" "$N8N_NODE" "$N8N_CLI" "$HERMES_PYTHON"; do
  [[ -e "$required_file" ]] || { echo "Arquivo obrigatório ausente: $required_file" >&2; exit 1; }
done
n8n_version="$("$N8N_NODE" "$N8N_CLI" --version)"
if [[ "$n8n_version" != "$EXPECTED_N8N_VERSION" ]]; then
  echo "Versão do n8n incompatível: esperada $EXPECTED_N8N_VERSION, encontrada $n8n_version" >&2
  exit 1
fi

configure_user_bus
install -d -m 0700 "$N8N_CONFIG_DIR" "$N8N_HOME_DIR"
if [[ ! -f "$WEBHOOK_ENV_FILE" ]]; then
  "$HERMES_PYTHON" - "$WEBHOOK_ENV_FILE" <<'PY'
import os
import secrets
import sys

path = sys.argv[1]
content = f"N8N_HERMES_WEBHOOK_SECRET={secrets.token_hex(32)}\n"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(content)
PY
fi
chmod 0600 "$WEBHOOK_ENV_FILE"

systemctl --user stop n8n.service
SERVICE_STOPPED=1

backup_dir="$N8N_HOME_DIR/backups"
install -d -m 0700 "$backup_dir"
backup_path="$backup_dir/database-pre-hermes-$(date +%Y%m%dT%H%M%S)-$$.sqlite"
if [[ -f "$N8N_HOME_DIR/database.sqlite" ]]; then
  "$HERMES_PYTHON" - "$N8N_HOME_DIR/database.sqlite" "$backup_path" <<'PY'
import os
import sqlite3
import sys

source_path, backup_path = sys.argv[1:]
source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
try:
    source_check = source.execute("PRAGMA quick_check").fetchone()[0]
    if source_check != "ok":
        raise SystemExit("Banco n8n de origem falhou no quick_check")
    backup = sqlite3.connect(backup_path)
    try:
        source.backup(backup)
        backup.commit()
        backup_check = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if backup_check != "ok":
            raise SystemExit("Backup do banco n8n falhou no integrity_check")
    finally:
        backup.close()
finally:
    source.close()
os.chmod(backup_path, 0o600)
PY
fi

systemctl --user start n8n.service
SERVICE_STOPPED=0
wait_http "http://127.0.0.1:5678/healthz"
wait_http "http://127.0.0.1:5678/rest/settings" 60

settings_json="$(curl --silent --show-error --fail --max-time 8 http://127.0.0.1:5678/rest/settings)"
if jq -e '.data.userManagement.showSetupOnFirstLoad == true' >/dev/null <<<"$settings_json"; then
  if [[ ! -f "$OWNER_ENV_FILE" ]]; then
    "$HERMES_PYTHON" - "$OWNER_ENV_FILE" <<'PY'
import os
import secrets
import sys

path = sys.argv[1]
content = "\n".join([
    "N8N_OWNER_EMAIL=doutortenente@users.noreply.github.com",
    "N8N_OWNER_FIRST_NAME=Nícholas",
    "N8N_OWNER_LAST_NAME=Nagaita",
    f"N8N_OWNER_PASSWORD=A1{secrets.token_hex(31)}",
    "",
])
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(content)
PY
  fi
  chmod 0600 "$OWNER_ENV_FILE"

  owner_payload="$TEMP_DIR/owner.json"
  "$HERMES_PYTHON" - "$OWNER_ENV_FILE" "$owner_payload" <<'PY'
import json
import os
import sys
from dotenv import dotenv_values

values = dotenv_values(sys.argv[1])
output_path = sys.argv[2]
required = ["N8N_OWNER_EMAIL", "N8N_OWNER_FIRST_NAME", "N8N_OWNER_LAST_NAME", "N8N_OWNER_PASSWORD"]
if any(not values.get(key) for key in required):
    raise SystemExit("owner.env incompleto")
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump({
        "email": values["N8N_OWNER_EMAIL"],
        "firstName": values["N8N_OWNER_FIRST_NAME"],
        "lastName": values["N8N_OWNER_LAST_NAME"],
        "password": values["N8N_OWNER_PASSWORD"],
    }, handle)
os.chmod(output_path, 0o600)
PY
  MUTATION_STARTED=1
  curl --silent --show-error --fail --max-time 30 \
    -H 'Content-Type: application/json' \
    --data-binary "@$owner_payload" \
    http://127.0.0.1:5678/rest/owner/setup >/dev/null
  echo "Proprietário local do n8n configurado; credenciais em $OWNER_ENV_FILE (0600)."
fi
unset settings_json

credential_file="$TEMP_DIR/n8n-credentials.json"
"$HERMES_PYTHON" - \
  "$HERMES_ENV_FILE" \
  "$WEBHOOK_ENV_FILE" \
  "$credential_file" \
  "$HERMES_CREDENTIAL_ID" \
  "$WEBHOOK_CREDENTIAL_ID" <<'PY'
import json
import os
import sys
from dotenv import dotenv_values

hermes_env_path, webhook_env_path, output_path, hermes_credential_id, webhook_credential_id = sys.argv[1:]
api_key = dotenv_values(hermes_env_path).get("API_SERVER_KEY")
webhook_secret = dotenv_values(webhook_env_path).get("N8N_HERMES_WEBHOOK_SECRET")
if not api_key:
    raise SystemExit("API_SERVER_KEY ausente no ambiente do Hermes")
if not webhook_secret:
    raise SystemExit("N8N_HERMES_WEBHOOK_SECRET ausente no ambiente do webhook")
payload = [
    {
        "id": hermes_credential_id,
        "name": "Hermes Local API",
        "type": "httpHeaderAuth",
        "data": {"name": "Authorization", "value": f"Bearer {api_key}"},
    },
    {
        "id": webhook_credential_id,
        "name": "Tijolão Webhook",
        "type": "httpHeaderAuth",
        "data": {"name": "X-Tijolao-Webhook", "value": webhook_secret},
    },
]
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
os.chmod(output_path, 0o600)
PY

systemctl --user stop n8n.service
SERVICE_STOPPED=1
MUTATION_STARTED=1

"$HERMES_PYTHON" - \
  "$N8N_HOME_DIR/database.sqlite" \
  "$HERMES_CREDENTIAL_ID" \
  "$WEBHOOK_CREDENTIAL_ID" \
  "$HEALTH_WORKFLOW_ID" \
  "$ASK_WORKFLOW_ID" <<'PY'
import sqlite3
import sys

database_path, hermes_credential_id, webhook_credential_id, health_workflow_id, ask_workflow_id = sys.argv[1:]
checks = [
    ("credentials_entity", hermes_credential_id, "Hermes Local API"),
    ("credentials_entity", webhook_credential_id, "Tijolão Webhook"),
    ("workflow_entity", health_workflow_id, "Hermes - Health"),
    ("workflow_entity", ask_workflow_id, "Hermes - Ask"),
]
connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
try:
    for table, entity_id, expected_name in checks:
        row = connection.execute(f'SELECT name FROM "{table}" WHERE id = ?', (entity_id,)).fetchone()
        if row and row[0] != expected_name:
            raise SystemExit(f"ID reservado já usado em {table}: {entity_id}")
        duplicate = connection.execute(
            f'SELECT id FROM "{table}" WHERE name = ? AND id <> ?',
            (expected_name, entity_id),
        ).fetchone()
        if duplicate:
            raise SystemExit(f"Nome reservado já usado em {table}: {expected_name}")
finally:
    connection.close()
PY

set -a
# shellcheck disable=SC1090
source "$N8N_ENV_FILE"
set +a

"$N8N_NODE" "$N8N_CLI" import:credentials \
  --input="$credential_file" \
  --include=id,name,type,data
"$N8N_NODE" "$N8N_CLI" import:workflow \
  --separate \
  --input="$N8N_WORKFLOWS_DIR"

for workflow_file in \
  "$N8N_WORKFLOWS_DIR/hermes-health.json" \
  "$N8N_WORKFLOWS_DIR/hermes-ask.json"; do
  workflow_id="$(jq -er '.id' "$workflow_file")"
  "$N8N_NODE" "$N8N_CLI" publish:workflow --id="$workflow_id"
done

for database_file in \
  "$N8N_HOME_DIR/database.sqlite" \
  "$N8N_HOME_DIR/database.sqlite-wal" \
  "$N8N_HOME_DIR/database.sqlite-shm"; do
  [[ ! -e "$database_file" ]] || chmod 0600 "$database_file"
done
systemctl --user start n8n.service
SERVICE_STOPPED=0
wait_http "http://127.0.0.1:5678/healthz"
wait_http "http://127.0.0.1:5678/rest/settings" 60
wait_http "http://127.0.0.1:5678/webhook/hermes-health" 60

set -a
# shellcheck disable=SC1090
source "$WEBHOOK_ENV_FILE"
set +a
if [[ -z ${N8N_HERMES_WEBHOOK_SECRET:-} ]]; then
  echo "N8N_HERMES_WEBHOOK_SECRET ausente" >&2
  exit 1
fi

curl --silent --show-error --fail --max-time 15 \
  http://127.0.0.1:5678/webhook/hermes-health |
  jq -e '.status == "ok"' >/dev/null

printf '%s' '{"message":"Responda exatamente N8N_HERMES_OK"}' |
  curl --silent --show-error --fail --max-time 120 \
    -H 'Content-Type: application/json' \
    -H "X-Tijolao-Webhook: ${N8N_HERMES_WEBHOOK_SECRET}" \
    --data-binary @- \
    http://127.0.0.1:5678/webhook/hermes-ask |
  jq -e '((.choices[0].message.content // "") | gsub("^[[:space:]]+|[[:space:]]+$"; "")) == "N8N_HERMES_OK"' >/dev/null
unset N8N_HERMES_WEBHOOK_SECRET

INSTALL_SUCCESS=1
echo "Integração n8n → Hermes instalada, publicada e testada."
if [[ -f ${backup_path:-} ]]; then
  echo "Backup anterior: $backup_path"
fi
