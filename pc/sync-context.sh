#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_HOME="${TIJOLAO_HOME:-/home/dr}"
MODE="${1:---dry-run}"

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

if [[ "$MODE" != "--dry-run" && "$MODE" != "--apply" ]]; then
  echo "Uso: $0 [--dry-run|--apply]" >&2
  exit 2
fi

MAPPINGS=(
  "0644|codex/AGENTS.md|.codex/AGENTS.md"
  "0600|hermes/memories/USER.md|.hermes/memories/USER.md"
  "0600|hermes/memories/MEMORY.md|.hermes/memories/MEMORY.md"
  "0644|services/hermes-dashboard.service|.config/systemd/user/hermes-dashboard.service"
  "0644|services/hermes-workspace.service|.config/systemd/user/hermes-workspace.service"
  "0644|services/n8n.service|.config/systemd/user/n8n.service"
)

for mapping in "${MAPPINGS[@]}"; do
  file_mode="${mapping%%|*}"
  remainder="${mapping#*|}"
  source_rel="${remainder%%|*}"
  [[ "$file_mode" =~ ^0[0-7]{3}$ ]] || { echo "Modo inválido: $file_mode" >&2; exit 1; }
  [[ -f "$REPO_DIR/$source_rel" && -r "$REPO_DIR/$source_rel" ]] || {
    echo "Fonte ausente ou ilegível: $REPO_DIR/$source_rel" >&2
    exit 1
  }
done

if [[ "$MODE" == "--apply" ]]; then
  configure_user_bus
fi

for mapping in "${MAPPINGS[@]}"; do
  file_mode="${mapping%%|*}"
  remainder="${mapping#*|}"
  source_rel="${remainder%%|*}"
  target_rel="${remainder#*|}"
  source_path="$REPO_DIR/$source_rel"
  target_path="$TARGET_HOME/$target_rel"

  if [[ "$MODE" == "--dry-run" ]]; then
    if [[ -e "$target_path" ]]; then
      diff --unified "$target_path" "$source_path" || true
    else
      printf 'CREATE %s\n' "$target_path"
    fi
  else
    install -D -m "$file_mode" "$source_path" "$target_path"
    printf 'APPLIED %s\n' "$target_path"
  fi
done

if [[ "$MODE" == "--apply" ]]; then
  systemctl --user daemon-reload
  echo "Projeções aplicadas; reinicie apenas os serviços afetados."
else
  echo "Prévia concluída. Use --apply para gravar."
fi
