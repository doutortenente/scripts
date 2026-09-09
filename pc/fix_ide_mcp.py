#!/usr/bin/env python3
"""Religa e mantém o MCP da IDE JetBrains no Claude Code — sempre com NOME NEUTRO.

Por que existe (em português comum):
  O "MCP" é o cabo que liga o Claude Code à IDE (PyCharm/WebStorm). Esse cabo usa
  uma "porta" (um número de canal na rede local). Dois problemas crônicos:

  1) NOME MENTIROSO: o plugin embutido da IDE se auto-registra no arquivo de
     configuração do Claude usando o NOME DO PRODUTO (ex.: "pycharm"). Mas qualquer
     IDE JetBrains viva atende a mesma porta — o rótulo "pycharm" mente. A casa fixou
     nomes NEUTROS: "jetbrains" (controle completo da IDe) e "jetbrains-index"
     (navegação de código). Este script funde/renomeia/poda qualquer variante de
     produto (pycharm/webstorm/intellij/idea/goland/...) de volta pro nome neutro.

  2) PORTA MUDA: quando a IDE reinicia e a porta velha está ocupada, ela escolhe
     outra. O Claude fica falando na porta velha e a ligação cai. Este script
     descobre as portas VIVAS sozinho (dá um "alô" de MCP em cada porta em escuta) e
     reaponta a configuração pras vivas.

  Idempotente: rodar 2x seguidas não muda nada na 2ª (converge e para).

Onde as entradas moram (convenção travada 03-jul-2026):
  - global  ~/.claude.json                  -> jetbrains + jetbrains-index (ÚNICO lugar delas)
  - projeto ~/projetos/.mcp.json            -> supabase/sasi/obsidian (NUNCA MCP de IDE aqui)
  - junie   ~/.junie/mcp/mcp.json           -> SÓ jetbrains (ver "orçamento de ferramentas")
  - junie/proj ~/projetos/.junie/mcp/mcp.json -> NUNCA MCP de IDE (a global do Junie já traz)
  Se um MCP de IDE aparecer em qualquer zona de projeto (o plugin às vezes escreve
  lá), é removido.

Orçamento de ferramentas do Junie (medido 31-jul-2026):
  O Claude Code carrega ferramenta de MCP sob demanda; o Junie NÃO — ele joga TODAS
  no prompt de uma vez. Com jetbrains-index (45 ferramentas) + playwright (24) +
  jetbrains (1) o próprio Junie avisava: "70 MCP tools are enabled — some models may
  fail or degrade when more than 40 tools are exposed". Por isso a zona do Junie fica
  SEM jetbrains-index: o Junie é produto JetBrains e já navega o código nativamente,
  então as 45 ferramentas ide_* eram duplicação pura.

  ATENÇÃO — as duas configs do Junie SOMAM: a global (~/.junie/mcp/mcp.json) e a do
  projeto (<projeto>/.junie/mcp/mcp.json). Podar só a global não baixa o orçamento.
  Contagem medida por sonda tools/list em 31-jul-2026, com ~/projetos aberto:
      global : playwright 24 + jetbrains 1                          = 25
      projeto: obsidian 12 + jetbrains-steroid 8 + webstorm 1       = 21
               (supabase e sasi responderam 0 — 403 e conexão morta)
      TOTAL 46, acima do limite de 40 -> o aviso volta.
  A entrada "webstorm" do projeto é duplicata LITERAL do "jetbrains" da global (mesma
  URL 127.0.0.1:<porta>/stream) e é podada aqui. O corte do que sobra (playwright e
  supabase são os pesos-pesados) é decisão do operador, não deste script.

Automação (sem mão humana, POR EVENTO, zero polling):
  Um par de unidades do systemd de usuário observa os arquivos que a IDE grava ao
  (re)iniciar — ~/.config/JetBrains/<IDE>/.lock e options/mcp*.xml — e roda este
  script em modo --quiet só quando eles mudam. Instaladas em ~/.config/systemd/user/
  (fix-ide-mcp.service + fix-ide-mcp.path). Limitação honesta: sessão do Claude Code
  JÁ ABERTA quando a IDE reinicia ainda precisa de um /mcp (o cliente não relê a
  config sozinho); sessão NOVA já nasce certa.

Uso:
    python3 fix_ide_mcp.py           # detecta, corrige, mostra o resultado
    python3 fix_ide_mcp.py --dry     # só mostra o que faria, não grava
    python3 fix_ide_mcp.py --quiet   # modo evento: só grava/loga quando muda algo

Só biblioteca padrão (stdlib). Escrita atômica, SEM backup .bak (doutrina do operador —
mantendo os 5 mais novos). Escrita atômica (grava num temporário e troca).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

HOME = Path.home()
GLOBAL_CFG = HOME / ".claude.json"  # zona canônica: jetbrains + jetbrains-index
PROJECT_CFG = HOME / "projetos" / ".mcp.json"  # zona de expurgo: sem MCP de IDE
JUNIE_CFG = HOME / ".junie" / "mcp" / "mcp.json"  # zona enxuta: só jetbrains
# Config do Junie POR PROJETO — SOMA com a global. Zona de expurgo: sem MCP de IDE.
JUNIE_PROJ_CFG = HOME / "projetos" / ".junie" / "mcp" / "mcp.json"
LOG = HOME / ".local" / "state" / "fix-ide-mcp.log"
MAX_BAK = 5  # backups .bak-<ts> mantidos por arquivo

CANON_FULL = "jetbrains"
CANON_INDEX = "jetbrains-index"
# MCP Steroid (plugin do jonnyzzz): porta FIXA 6315 por design — ao contrário dos dois
# acima, NÃO muda a cada reinício, então não entra na sonda de portas vivas.
CANON_STEROID = "jetbrains-steroid"
STEROID_URL = "http://127.0.0.1:6315/mcp"

INIT = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fix-ide-mcp", "version": "2"},
        },
    }
).encode()
PATHS = ["/stream", "/index-mcp/streamable-http", "/sse"]

# Nome de produto JetBrains: a IDE que atende a porta muda, o nome mente.
# (contém "jetbrains" de propósito — mas os canônicos são tratados por igualdade
# de nome ANTES desta regra, então nunca são confundidos com "variante a podar".)
PRODUCT_RE = re.compile(
    r"(pycharm|webstorm|intellij|idea|datagrip|goland|phpstorm|rubymine|clion|"
    r"rider|rustrover|aqua|fleet)",
    re.I,
)
# URL que denuncia um endpoint MCP de IDE JetBrains, independente do nome da entrada.
IDE_URL_RE = re.compile(r"127\.0\.0\.1:\d+/(?:stream|index-mcp/streamable-http|sse)")


# ----------------------------------------------------------------------------- #
# Descoberta das portas vivas
# ----------------------------------------------------------------------------- #
def listening_ports() -> list[int]:
    """Portas em LISTEN no localhost (inclui bind IPv6-mapeado [::ffff:127.0.0.1])."""
    try:
        out = subprocess.run(
            ["ss", "-tln"], capture_output=True, text=True, timeout=10
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    ports = set()
    for m in re.finditer(r"127\.0\.0\.1\]?:(\d+)", out):
        ports.add(int(m.group(1)))
    return sorted(ports)


def probe(port: int, path: str) -> dict | None:
    """Dá o 'alô' de MCP; retorna {url, name} se for um servidor MCP de verdade."""
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(
        url,
        data=INIT,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            body = r.read().decode("utf-8", "ignore")
    except Exception:
        return None
    for chunk in body.splitlines():
        chunk = chunk[5:].strip() if chunk.startswith("data:") else chunk.strip()
        if not chunk.startswith("{"):
            continue
        try:
            info = json.loads(chunk).get("result", {}).get("serverInfo")
            if info:
                return {"url": url, "name": info.get("name", "?")}
        except json.JSONDecodeError:
            continue
    return None


def discover() -> dict[str, str]:
    """Acha o MCP full da IDE e o index MCP entre as portas vivas. {full,index}->url."""
    found: dict[str, str] = {}
    for port in listening_ports():
        for path in PATHS:
            info = probe(port, path)
            if not info:
                continue
            name = info["name"].lower()
            url = info["url"]
            if "index" in name or "index-mcp" in url:
                found.setdefault("index", url)
            elif PRODUCT_RE.search(name) or url.endswith("/stream"):
                found.setdefault("full", url)
            break  # essa porta já respondeu; próxima porta
    return found


# ----------------------------------------------------------------------------- #
# Classificação de entradas de config
# ----------------------------------------------------------------------------- #
def is_ide_entry(name: str, entry) -> bool:
    """True se a entrada é um MCP de IDE JetBrains (canônico OU variante de produto)."""
    # O steroid tem porta fixa e vida própria: nunca é podado nem repontado por aqui.
    if name == CANON_STEROID:
        return False
    if name in (CANON_FULL, CANON_INDEX):
        return True
    if PRODUCT_RE.search(name):
        return True
    if isinstance(entry, dict):
        url = entry.get("url", "")
        if isinstance(url, str) and IDE_URL_RE.search(url):
            return True
    return False


def entry_role(name: str, entry) -> str:
    """'index' ou 'full' para uma entrada de IDE (pela URL, cai pro nome)."""
    url = entry.get("url", "") if isinstance(entry, dict) else ""
    if "index-mcp" in url or "index" in name.lower():
        return "index"
    return "full"


# ----------------------------------------------------------------------------- #
# Transformações (mutam o dict em memória; devolvem se mudou algo)
# ----------------------------------------------------------------------------- #
def _canonize_zone(
    servers: dict, full: str | None, index: str | None, actions: list[str], where: str
) -> bool:
    """Zona canônica (global): deixa jetbrains + jetbrains-index + jetbrains-steroid."""
    changed = False

    # Steroid: porta fixa, entra sempre com a mesma URL (idempotente).
    desired_steroid = {"type": "http", "url": STEROID_URL}
    if servers.get(CANON_STEROID) != desired_steroid:
        verb = "atualizado" if CANON_STEROID in servers else "criado"
        servers[CANON_STEROID] = desired_steroid
        actions.append(f"{where}: {verb} '{CANON_STEROID}' -> {STEROID_URL} (porta fixa)")
        changed = True
    ide_names = [n for n, e in servers.items() if is_ide_entry(n, e)]

    # Se a sonda falhou, recupera a porta da própria entrada existente.
    full_url = full
    index_url = index
    if not full_url:
        for n in ide_names:
            if entry_role(n, servers[n]) == "full":
                full_url = (
                    servers[n].get("url") if isinstance(servers[n], dict) else None
                )
                if full_url:
                    break
    if not index_url:
        for n in ide_names:
            if entry_role(n, servers[n]) == "index":
                index_url = (
                    servers[n].get("url") if isinstance(servers[n], dict) else None
                )
                if index_url:
                    break

    # Poda toda entrada de IDE com nome NÃO-canônico (aqui morre o "pycharm").
    for n in ide_names:
        if n not in (CANON_FULL, CANON_INDEX):
            del servers[n]
            actions.append(f"{where}: podada entrada de IDE '{n}' (nome de produto)")
            changed = True

    # Garante jetbrains apontando pra porta viva.
    if full_url:
        desired = {
            "type": "http",
            "url": full_url,
            "headers": {"IJ_MCP_SERVER_PROJECT_PATH": str(HOME / "projetos")},
        }
        if servers.get(CANON_FULL) != desired:
            verb = "atualizado" if CANON_FULL in servers else "criado"
            servers[CANON_FULL] = desired
            actions.append(f"{where}: {verb} '{CANON_FULL}' -> {full_url}")
            changed = True

    # Garante jetbrains-index apontando pra porta viva.
    if index_url:
        desired = {"type": "http", "url": index_url}
        if servers.get(CANON_INDEX) != desired:
            verb = "atualizado" if CANON_INDEX in servers else "criado"
            servers[CANON_INDEX] = desired
            actions.append(f"{where}: {verb} '{CANON_INDEX}' -> {index_url}")
            changed = True

    return changed


def _junie_zone(
    servers: dict, full: str | None, actions: list[str], where: str
) -> bool:
    """Zona do Junie: SÓ 'jetbrains' na porta viva; todo o resto de IDE é podado.

    Formato do Junie difere do Claude Code: sem a chave "type", só url + headers.
    Poda jetbrains-index de propósito — ver "orçamento de ferramentas" no topo.
    """
    changed = False
    ide_names = [n for n, e in servers.items() if is_ide_entry(n, e)]

    # Se a sonda falhou, recupera a porta da entrada 'full' que já existe.
    full_url = full
    if not full_url:
        for n in ide_names:
            if entry_role(n, servers[n]) == "full" and isinstance(servers[n], dict):
                full_url = servers[n].get("url")
                if full_url:
                    break

    for n in ide_names:
        if n != CANON_FULL:
            del servers[n]
            actions.append(f"{where}: podada '{n}' (Junie só carrega '{CANON_FULL}')")
            changed = True

    if full_url:
        desired = {
            "url": full_url,
            "headers": {"IJ_MCP_SERVER_PROJECT_PATH": str(HOME / "projetos")},
        }
        if servers.get(CANON_FULL) != desired:
            verb = "atualizado" if CANON_FULL in servers else "criado"
            servers[CANON_FULL] = desired
            actions.append(f"{where}: {verb} '{CANON_FULL}' -> {full_url}")
            changed = True

    return changed


def _strip_zone(servers: dict, actions: list[str], where: str) -> bool:
    """Zona de expurgo (projeto): remove QUALQUER MCP de IDE (não pertence aqui)."""
    changed = False
    for n in [n for n, e in servers.items() if is_ide_entry(n, e)]:
        del servers[n]
        actions.append(
            f"{where}: removida entrada de IDE '{n}' (não vai no config de projeto)"
        )
        changed = True
    return changed


# ----------------------------------------------------------------------------- #
# Gravação segura
# ----------------------------------------------------------------------------- #
def _rotate_backups(path: Path) -> None:
    baks = sorted(path.parent.glob(f"{path.name}.bak-*"))
    for old in baks:   # doutrina SEM BACKUP: remove TODOS, não rotaciona
        try:
            old.unlink()
        except OSError:
            pass


def _write_atomic(path: Path, text: str) -> None:
    """Escrita atômica (temp + os.replace). SEM backup — doutrina SEM BACKUP
    (ordem do operador, 10-jul-2026): nada de .bak acumulando no workspace.
    A rede de segurança real é o git, não cópia local."""
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)


def process_file(
    path: Path,
    zone: str,
    full: str | None,
    index: str | None,
    dry: bool,
    actions: list[str],
    label: str | None = None,
) -> bool:
    """zone: 'global' (canoniza) | 'project' (expurga) | 'junie' (só jetbrains).

    label: rótulo mostrado no relatório. Necessário quando dois arquivos têm o mesmo
    nome (os dois mcp.json do Junie: o global e o do projeto).
    """
    if not path.exists():
        return False
    label = label or path.name
    try:
        original = path.read_text()
        cfg = json.loads(original)
    except (OSError, json.JSONDecodeError) as e:
        actions.append(f"{path.name}: ERRO lendo JSON ({e}) — pulado")
        return False

    changed = False
    servers = cfg.setdefault("mcpServers", {})
    if zone == "global":
        changed |= _canonize_zone(servers, full, index, actions, f"{label}[global]")
        projects = cfg.get("projects")
        if isinstance(projects, dict):
            for pname, pcfg in projects.items():
                psrv = pcfg.get("mcpServers") if isinstance(pcfg, dict) else None
                if isinstance(psrv, dict):
                    changed |= _strip_zone(psrv, actions, f"{label}[proj {pname}]")
    elif zone == "junie":
        changed |= _junie_zone(servers, full, actions, label)
    else:
        changed |= _strip_zone(servers, actions, label)

    if changed and not dry:
        _write_atomic(path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return changed


# ----------------------------------------------------------------------------- #
# Log (modo --quiet)
# ----------------------------------------------------------------------------- #
def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        # cap simples: se passar de ~200 linhas, mantém as últimas 150
        if LOG.exists():
            lines = LOG.read_text().splitlines()
            if len(lines) > 200:
                LOG.write_text("\n".join(lines[-150:]) + "\n")
        with LOG.open("a") as f:
            f.write(f"{dt.datetime.now().isoformat(timespec='seconds')}  {msg}\n")
    except OSError:
        pass


# ----------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Religa/mantém o MCP da IDE JetBrains (nome neutro)."
    )
    ap.add_argument(
        "--dry", action="store_true", help="só mostra o que faria, não grava"
    )
    ap.add_argument(
        "--quiet", action="store_true", help="modo evento: só grava/loga quando muda"
    )
    args = ap.parse_args()

    found = discover()
    full = found.get("full")
    index = found.get("index")

    if not full and not index:
        # IDE fechada é o normal — não é erro (não polui o journal do systemd).
        if not args.quiet:
            print("Nenhum MCP de IDE JetBrains vivo. Abra a IDE e rode de novo.")
        return 0

    actions: list[str] = []
    changed = process_file(
        GLOBAL_CFG, "global", full, index, args.dry, actions, label=".claude.json"
    )
    changed = (
        process_file(
            PROJECT_CFG,
            "project",
            full,
            index,
            args.dry,
            actions,
            label="projetos/.mcp.json",
        )
        or changed
    )
    changed = (
        process_file(
            JUNIE_CFG, "junie", full, index, args.dry, actions, label="junie/mcp.json"
        )
        or changed
    )
    # A config do Junie por projeto SOMA com a global — expurgo de MCP de IDE aqui
    # evita duplicata (o 'webstorm' que o plugin escreve = o 'jetbrains' da global).
    changed = (
        process_file(
            JUNIE_PROJ_CFG,
            "project",
            full,
            index,
            args.dry,
            actions,
            label="projetos/.junie/mcp.json",
        )
        or changed
    )

    if args.quiet:
        if changed and not args.dry:
            for a in actions:
                _log(a)
            _log("-> se houver sessão do Claude Code aberta, rode /mcp pra reconectar")
        return 0

    print("MCP de IDE detectado nas portas vivas:")
    print(f"  full  (jetbrains):       {full or '— não achado'}")
    print(f"  index (jetbrains-index): {index or '— não achado'}\n")
    if not actions:
        print("Configs já estavam canônicas e nas portas certas. Nada a fazer.")
    else:
        for a in actions:
            print(f"  {'(dry) ' if args.dry else ''}{a}")
        print(
            f"\n{'Seria aplicado.' if args.dry else 'Aplicado.'} "
            "Se houver sessão aberta do Claude Code, rode  /mcp  pra reconectar."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
