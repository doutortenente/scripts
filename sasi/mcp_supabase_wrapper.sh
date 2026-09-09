#!/usr/bin/env bash
# Wrapper do MCP supabase do SASI — conserta 2 defeitos de uma vez:
#
# 1) SEGREDO EM REPO PÚBLICO. O .mcp.json do SASI é versionado e o repo
#    (github.com/doutortenente/SASI-V3-) é PÚBLICO. Nenhuma credencial
#    pode ficar em claro lá. Este wrapper carrega ~/projetos/.env em tempo de
#    execução, então o .mcp.json não guarda segredo nenhum.
#
# 2) CHAVE ERRADA. O .mcp.json passava SUPABASE_ACCESS_TOKEN=${SUPABASE_SECRET_KEY}.
#    São credenciais diferentes:
#      SUPABASE_SECRET_KEY  -> chave do PROJETO, para o app ler/gravar no banco
#      SUPABASE_ACCESS_TOKEN-> token da CONTA (sbp_...), que é o que a API de
#                              gestão exige. Sem ele o servidor responde
#                              "Unauthorized. Please provide a valid access token".
#    Ambas moram no cofre; aqui só a de conta é usada, e é o próprio nome que o
#    servidor MCP lê do ambiente.
#
# Node 24 é obrigatório: supabase-js exige WebSocket nativo (Node >= 22).
# Pós-rotação de credencial: basta atualizar o .env — este wrapper pega o valor novo.

# Sem 'set -e' ao redor do source: o cofre tem linhas de texto solto (sem '#' e
# sem 'VAR='), e o bash tenta executá-las. Com -e ligado o wrapper morre ali.
# O wrapper do MCP sasi já convive com isso do mesmo jeito.
set -a
# shellcheck disable=SC1091
source /home/dr/projetos/.env 2>/dev/null
set +a

set -uo pipefail

if [ -z "${SUPABASE_ACCESS_TOKEN:-}" ]; then
  echo "mcp_supabase_wrapper: SUPABASE_ACCESS_TOKEN vazio após carregar ~/projetos/.env" >&2
  exit 1
fi

NODE_BIN=/home/dr/.config/nvm/versions/node/v24.16.0/bin
export PATH="$NODE_BIN:$PATH"

exec "$NODE_BIN/npx" -y @supabase/mcp-server-supabase@latest \
  --project-ref=idswehsvvqczzkiatuzu "$@"
