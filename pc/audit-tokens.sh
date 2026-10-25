#!/usr/bin/env bash
set -euo pipefail

HERMES_BIN="${HERMES_BIN:-/home/dr/.local/bin/hermes}"  # ponte pro contêiner hermes-agent
DAYS="${1:-30}"

if [[ ! "$DAYS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Uso: $0 [dias]" >&2
  exit 2
fi

command -v jq >/dev/null
[[ -x "$HERMES_BIN" ]]

report="$($HERMES_BIN prompt-size --json)"
printf '%s\n' "$report" | jq '{
  platform,
  model,
  system_prompt_bytes: .system_prompt.bytes,
  skills_index_bytes_included_in_system: .skills_index.bytes,
  memory_bytes_included_in_system: .memory.bytes,
  tool_count: .tools.count,
  tool_schema_bytes: .tools.json_bytes,
  fixed_request_bytes: (.system_prompt.bytes + .tools.json_bytes)
}'

printf 'compression.enabled='
"$HERMES_BIN" config get compression.enabled
printf 'compression.threshold='
"$HERMES_BIN" config get compression.threshold
printf 'compression.in_place='
"$HERMES_BIN" config get compression.in_place
printf 'compression.tail_mode='
"$HERMES_BIN" config get compression.tail_mode
printf 'compression.proactive_prune_tokens='
"$HERMES_BIN" config get compression.proactive_prune_tokens

"$HERMES_BIN" insights --days "$DAYS"
