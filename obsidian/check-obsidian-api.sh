#!/usr/bin/env bash
# Verifica Obsidian Local REST API (vault celebro). Uso: bash ~/projetos/scripts/obsidian/check-obsidian-api.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
[ -f "$ROOT/.env" ] && source "$ROOT/.env"

URL="${OBSIDIAN_REST_URL:-http://127.0.0.1:27123}"
KEY="${OBSIDIAN_API_KEY:-}"

if [ -z "$KEY" ]; then
  echo "ERRO: OBSIDIAN_API_KEY ausente em $ROOT/.env"
  exit 1
fi

if ! pgrep -x obsidian >/dev/null 2>&1; then
  echo "AVISO: Obsidian não está rodando. Abra o vault celebro em /home/dr/vaults/celebro"
fi

code=$(curl -s -o /tmp/obsidian_health.txt -w "%{http_code}" \
  -H "Authorization: Bearer $KEY" "$URL/" || echo "000")

if [ "$code" = "200" ] || [ "$code" = "404" ]; then
  echo "OK: Local REST API respondeu (HTTP $code) em $URL"
  head -c 200 /tmp/obsidian_health.txt 2>/dev/null; echo
  exit 0
fi

echo "FALHA: HTTP $code em $URL — plugin Local REST API ativo no Obsidian?"
exit 1