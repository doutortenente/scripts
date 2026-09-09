#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faxina_dev.py — Boletim de faxina do workspace ~/projetos (LEITURA PURA)

O QUE FAZ
    Imprime um relatório de higiene do workspace do PC "Tijolão". Confere 5
    frentes que costumam bagunçar: raiz ~/projetos poluída, Downloads acumulando,
    repositórios git sujos/dessincronizados, worktrees órfãos e lixo comum
    (.bak, __pycache__, .zip soltos). NÃO apaga, NÃO move, NÃO altera NADA em
    lugar nenhum — só lê o estado e imprime na tela.

POR QUE EXISTE
    Aprovado pelo operador em 06-jul-2026. Depois de cada sessão de trabalho o
    workspace tende a juntar sobras. Este boletim é o "raio-X" que diz o que
    limpar, sem tocar em nada. Quem decide/apaga é o operador (ou outra rotina
    com --apply próprio); este script é só o diagnóstico.

COMO USAR
    python3 /home/dr/projetos/scripts/faxina_dev.py
    (sem flags — é boletim, sempre sai com código 0)

LIBS
    Só stdlib (os, subprocess, pathlib, datetime, time). Nada a instalar.

MANUTENÇÃO
    - RAIZ_ESPERADA: allowlist do estado limpo da raiz ~/projetos. Se você adicionar
      de propósito um item novo na raiz, inclua o nome aqui pra parar de acusar.
    - DOWNLOADS_PINNED: arquivos do Downloads que podem ficar velhos sem virar
      alerta (ex.: zips do catálogo de skills, presos a uma tarefa em curso).
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ─── Configuração editável ────────────────────────────────────────────────────

HOME = Path("/home/dr")
DEV = HOME / "projetos"
DOWNLOADS = HOME / "Downloads"

# Snapshot do estado LIMPO da raiz ~/projetos (atualizado 23-jul-2026,
# pós-migração ~/dev→~/projetos e _lab→rascunhos).
# Qualquer item na raiz fora desta lista é sinalizado como intruso.
RAIZ_ESPERADA = {
    ".claude",
    "central-do-trampo",  # app Central do Trampo — movido pra cá pelo operador (28-jul-2026)
    "claude",
    "CLAUDE.md",
    ".env",
    ".gitignore",
    ".idea",
    ".mcp.json",
    "mapa-claude-e-catalogo-skills",
    "rascunhos",
    "sasi",
    "scripts",
    "templates",
}

# Arquivos do Downloads que NÃO devem virar alerta mesmo velhos (presos a tarefa).
# Estado 06-jul-2026: os 12 zips do catálogo de skills (tarefa das 359 skills).
DOWNLOADS_PINNED = {
    "book-to-skill-master.zip",
    "buildwithclaude-main.zip",
    "chrome-devtools-mcp-main.zip",
    "context7-master.zip",
    "educational-plugin-master.zip",
    "firecrawl-main.zip",
    "mcp-steroid-main.zip",
    "ring-ui-master.zip",
    "supabase-js-master.zip",
    "supabase-py-main.zip",
    "ui-main.zip",
    "vercel-main.zip",
}

# Repos git vigiados: (rótulo, caminho, branch local)
REPOS = [
    ("sasi", DEV / "sasi", "main"),
    ("claude", DEV / "claude", "main"),
    ("celebro", HOME / "vaults" / "celebro", "main"),
]

# Pastas ignoradas na varredura de lixo (seção 5).
LIXO_EXCLUIR = {"rascunhos", "node_modules", ".git"}

DIAS_VELHO = 7

OK, WARN, CRIT = "✅", "⚠️", "🔴"


# ─── Utilidades ───────────────────────────────────────────────────────────────


def git(repo: Path, args, timeout=25):
    """Roda um comando git no repo. Devolve (rc, stdout, stderr). rc=-1 = timeout/erro."""
    try:
        p = subprocess.run(
            ["git", "-C", str(repo)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def pior(*symbols):
    """Retorna o símbolo de maior severidade entre os dados."""
    if CRIT in symbols:
        return CRIT
    if WARN in symbols:
        return WARN
    return OK


# ─── Seção 1 — RAIZ ~/projetos ─────────────────────────────────────────────────────


def sec_raiz():
    linhas, status = [], OK
    try:
        atual = set(os.listdir(DEV))
    except OSError as e:
        return CRIT, [f"  {CRIT} não consegui ler {DEV}: {e}"]
    intrusos = sorted(atual - RAIZ_ESPERADA)
    faltando = sorted(RAIZ_ESPERADA - atual)
    if intrusos:
        status = WARN
        for nome in intrusos:
            alvo = DEV / nome
            tipo = "pasta" if alvo.is_dir() else "arquivo"
            linhas.append(f"  {WARN} intruso: {nome} ({tipo})")
    for nome in faltando:
        linhas.append(f"  {OK} esperado ausente (ok se removido de propósito): {nome}")
    if not intrusos:
        linhas.append(f"  {OK} raiz limpa — {len(atual)} itens, todos na allowlist")
    return status, linhas


# ─── Seção 2 — DOWNLOADS ──────────────────────────────────────────────────────


def sec_downloads():
    linhas, status = [], OK
    if not DOWNLOADS.exists():
        return OK, [f"  {OK} {DOWNLOADS} não existe (nada a conferir)"]
    itens = sorted(os.listdir(DOWNLOADS))
    agora = time.time()
    corte = DIAS_VELHO * 86400
    velhos = []
    for nome in itens:
        if nome in DOWNLOADS_PINNED:
            continue
        alvo = DOWNLOADS / nome
        try:
            idade = agora - alvo.stat().st_mtime
        except OSError:
            continue
        if idade > corte:
            velhos.append((nome, int(idade // 86400)))
    linhas.append(
        f"  total de itens: {len(itens)}  |  fixados (pinned): {len(DOWNLOADS_PINNED & set(itens))}"
    )
    if velhos:
        status = WARN
        for nome, dias in velhos:
            linhas.append(
                f"  {WARN} velho ({dias}d, >{DIAS_VELHO}d, não-pinned): {nome}"
            )
    else:
        linhas.append(f"  {OK} nenhum item velho fora da lista de fixados")
    return status, linhas


# ─── Seção 3 — REPOS GIT ──────────────────────────────────────────────────────


def sec_repos():
    linhas, status = [], OK
    for rotulo, repo, branch in REPOS:
        if not (repo / ".git").exists():
            linhas.append(f"  {WARN} {rotulo}: não é repo git em {repo}")
            status = pior(status, WARN)
            continue

        s_repo = OK
        detalhe = []

        # (a) working tree sujo
        rc, out, _ = git(repo, ["status", "--porcelain"])
        if rc == 0 and out:
            n = len(out.splitlines())
            detalhe.append(f"{WARN} sujo ({n} arquivo(s) sem commit)")
            s_repo = pior(s_repo, WARN)
        elif rc == 0:
            detalhe.append(f"{OK} limpo")
        else:
            detalhe.append(f"{WARN} git status falhou")
            s_repo = pior(s_repo, WARN)

        # (b) à frente / atrás do GitHub — fetch primeiro
        frc, _, ferr = git(repo, ["fetch", "--quiet"], timeout=40)
        sem_rede = frc != 0
        rc2, out2, _ = git(
            repo, ["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"]
        )
        if rc2 == 0 and out2:
            partes = out2.split()
            frente = partes[0] if len(partes) > 0 else "?"
            atras = partes[1] if len(partes) > 1 else "?"
            sync = f"frente={frente} atras={atras}"
            if frente != "0" or atras != "0":
                detalhe.append(f"{WARN} dessincronizado ({sync})")
                s_repo = pior(s_repo, WARN)
            else:
                detalhe.append(f"{OK} sincronizado ({sync})")
        else:
            detalhe.append(f"{WARN} não comparei com origin (sem upstream ou erro)")
            s_repo = pior(s_repo, WARN)
        if sem_rede:
            detalhe.append("sem rede — comparação local pode estar defasada")

        # (c) merge/rebase travado
        gitdir = repo / ".git"
        travas = []
        if (gitdir / "MERGE_HEAD").exists():
            travas.append("MERGE_HEAD")
        if (gitdir / "rebase-merge").exists():
            travas.append("rebase-merge")
        if (gitdir / "rebase-apply").exists():
            travas.append("rebase-apply")
        if travas:
            detalhe.append(f"{CRIT} operação travada: {', '.join(travas)}")
            s_repo = pior(s_repo, CRIT)

        status = pior(status, s_repo)
        linhas.append(f"  {s_repo} {rotulo}:")
        for d in detalhe:
            linhas.append(f"       - {d}")
    return status, linhas


# ─── Seção 4 — WORKTREES ÓRFÃOS ───────────────────────────────────────────────


def sec_worktrees():
    linhas, status = [], OK
    for rotulo, repo, _ in REPOS:
        if not (repo / ".git").exists():
            continue
        rc, out, _ = git(repo, ["worktree", "list"])
        extras = []
        if rc == 0 and out:
            wlinhas = out.splitlines()
            extras = wlinhas[1:]  # 1ª linha = worktree principal
        if extras:
            status = pior(status, WARN)
            linhas.append(f"  {WARN} {rotulo}: {len(extras)} worktree(s) extra:")
            for w in extras:
                linhas.append(f"       - {w}")
        # pasta <repo>/.claude/worktrees/
        wt_dir = repo / ".claude" / "worktrees"
        if wt_dir.exists():
            conteudo = sorted(os.listdir(wt_dir))
            if conteudo:
                status = pior(status, WARN)
                linhas.append(
                    f"  {WARN} {rotulo}: .claude/worktrees/ com {len(conteudo)} item(ns):"
                )
                for c in conteudo:
                    linhas.append(f"       - {c}")
    if not linhas:
        linhas.append(f"  {OK} nenhum worktree órfão nos 4 repos")
    return status, linhas


# ─── Seção 5 — LIXO COMUM ─────────────────────────────────────────────────────


def sec_lixo():
    linhas, status = [], OK
    baks, pycaches, zips = [], [], []
    for raiz, dirs, arquivos in os.walk(DEV):
        # poda: não descer em pastas excluídas
        dirs[:] = [d for d in dirs if d not in LIXO_EXCLUIR]
        raiz_p = Path(raiz)
        for d in list(dirs):
            if d == "__pycache__":
                pycaches.append(str((raiz_p / d)))
        for a in arquivos:
            if ".bak-" in a:
                baks.append(str(raiz_p / a))
            elif a.endswith(".zip"):
                zips.append(str(raiz_p / a))

    def bloco(titulo, itens):
        nonlocal status
        if itens:
            status = pior(status, WARN)
            linhas.append(f"  {WARN} {titulo}: {len(itens)}")
            for it in sorted(itens):
                linhas.append(f"       - {it}")

    bloco("backups .bak-*", baks)
    bloco("pastas __pycache__", pycaches)
    bloco("arquivos .zip", zips)
    if not (baks or pycaches or zips):
        linhas.append(
            f"  {OK} sem lixo comum (.bak / __pycache__ / .zip) fora de _arquivo,_lab,node_modules"
        )
    return status, linhas


# ─── Orquestração ─────────────────────────────────────────────────────────────


def main():
    secoes = [
        ("1. RAIZ ~/projetos", sec_raiz),
        ("2. DOWNLOADS", sec_downloads),
        ("3. REPOS GIT", sec_repos),
        ("4. WORKTREES ÓRFÃOS", sec_worktrees),
        ("5. LIXO COMUM", sec_lixo),
    ]
    resultados = []
    for titulo, fn in secoes:
        try:
            st, linhas = fn()
        except Exception as e:  # noqa: BLE001 — boletim nunca quebra
            st, linhas = WARN, [f"  {WARN} erro ao rodar seção: {e}"]
        resultados.append((titulo, st, linhas))

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    geral = pior(*[st for _, st, _ in resultados])

    print("=" * 60)
    print(f"BOLETIM DE FAXINA — ~/projetos   ({agora})")
    print("=" * 60)
    print("RESUMO:")
    for titulo, st, _ in resultados:
        print(f"  {st}  {titulo}")
    print(f"  ── veredito geral: {geral}")
    print("=" * 60)

    for titulo, st, linhas in resultados:
        print(f"\n{st} {titulo}")
        print("-" * 60)
        for l in linhas:
            print(l)

    print()
    print("Leitura pura — este boletim não apagou nem moveu nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
