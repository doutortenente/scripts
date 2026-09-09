#!/usr/bin/env bash
# ===================== DESATIVADO EM 11-AGO-2026 =====================
# O SASI v2 (~/projetos/sasi) foi substituído pelo SASI v3
# (~/projetos/SASI-V3, Next.js + pnpm). O diretório mcp-server/
# não existe em disco nenhum — não há binário para este wrapper executar.
# A entrada 'sasi' foi removida de ~/projetos/.mcp.json na mesma data.
# Para reativar: reconstruir o mcp-server e reapontar a linha exec abaixo.
# =====================================================================
echo "mcp_sasi_wrapper.sh: DESATIVADO — mcp-server não existe mais. Veja o cabeçalho." >&2
exit 1
# Wrapper do MCP sasi — conserta 2 defeitos de uma vez:
# 1) carrega ~/projetos/.env (o processo MCP não herdava SASI_SERVICE_ROLE_KEY)
# 2) força Node 24 do nvm (Node <22 não tem WebSocket nativo -> supabase-js recusava e a escrita falhava).
#    03-jul-2026: TUDO unificado no 24 — nvm default, Vercel e este MCP. Node 20 = EOL abr/2026.
# Pos-rotacao de credenciais: basta atualizar o .env, este wrapper pega o valor novo sozinho.
set -a
source /home/dr/projetos/.env
set +a
exec /home/dr/.config/nvm/versions/node/v24.16.0/bin/node /home/dr/projetos/sasi/mcp-server/dist/index.js
