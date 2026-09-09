#!/usr/bin/env bash
set -euo pipefail

echo "=== Docker ==="
docker info 2>/dev/null | grep -E "Server Version|Containers|Running|Images" || echo "Docker indisponível"
echo ""
echo "=== Containers ==="
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true
echo ""

echo "=== SASI / Supabase local ==="
if command -v supabase >/dev/null 2>&1; then
  (cd /home/dr/dev/sasi && supabase status 2>/dev/null) || echo "Supabase local parado"
fi