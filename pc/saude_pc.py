#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boletim de saúde do PC "Tijolão" — leitura pura, nada é gravado.

Passa o estetoscópio no Tijolão e imprime um boletim em pt-BR com um sinal
✅/⚠️/🔴 por seção (disco, memória, IDEs, conectores da IDE, Node, repos, cache).
É só diagnóstico: NÃO apaga, NÃO grava, NÃO conecta em lugar nenhum além de
testar se as portas locais da IDE respondem.

Bibliotecas: usa `psutil` (5.9.x, já instalado) pra memória/processos; se faltar,
degrada pra /proc e segue com aviso. O resto é stdlib pura.

Uso:
    python3 saude_pc.py        # roda sem argumento, imprime o boletim e sai (exit 0 sempre)
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

HOME = Path.home()

try:
    import psutil  # type: ignore

    HAS_PSUTIL = True
except ImportError:  # degrada com aviso, não quebra
    psutil = None  # type: ignore
    HAS_PSUTIL = False

OK, WARN, CRIT = "✅", "⚠️", "🔴"


def human(n: float) -> str:
    f = float(n)
    for u in ("B", "K", "M", "G", "T"):
        if f < 1024 or u == "T":
            return f"{f:.1f}{u}"
        f /= 1024
    return f"{f:.1f}T"


class Secao:
    """Uma seção do boletim: título, sinal, linhas e (opcional) 1 linha de conduta."""

    def __init__(self, titulo: str):
        self.titulo = titulo
        self.icon = OK
        self.linhas: list[str] = []
        self.conduta: str | None = None

    def grade(self, icon: str) -> None:
        # mantém sempre o pior sinal já visto (✅ < ⚠️ < 🔴)
        ordem = {OK: 0, WARN: 1, CRIT: 2}
        if ordem[icon] > ordem[self.icon]:
            self.icon = icon


# --------------------------------------------------------------------------- #
# 1. Disco
# --------------------------------------------------------------------------- #
def sec_disco() -> Secao:
    s = Secao("Disco (raiz /)")
    import shutil

    total, usado, livre = shutil.disk_usage("/")
    pct = usado / total * 100
    if pct > 85:
        s.grade(CRIT)
        s.conduta = (
            "Disco > 85% — rode  python3 ~/projetos/scripts/pc/pc_higiene.py --apply"
        )
    elif pct > 75:
        s.grade(WARN)
        s.conduta = "Disco > 75% — considere  python3 ~/projetos/scripts/pc/pc_higiene.py  (dry-run primeiro)"
    s.linhas.append(
        f"usado {human(usado)} / total {human(total)} ({pct:.0f}%) · livre {human(livre)}"
    )
    return s


# --------------------------------------------------------------------------- #
# 2. RAM + swap + zram
# --------------------------------------------------------------------------- #
def meminfo_fallback() -> dict[str, int]:
    d: dict[str, int] = {}
    try:
        for line in (Path("/proc/meminfo")).read_text().splitlines():
            k, _, v = line.partition(":")
            d[k.strip()] = int(v.strip().split()[0]) * 1024  # kB -> B
    except OSError:
        pass
    return d


def sec_ram() -> Secao:
    s = Secao("RAM + swap")
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        total, usado, pct = vm.total, vm.used, vm.percent
        sw_total, sw_usado = sw.total, sw.used
    else:
        s.linhas.append("(psutil ausente — lendo /proc/meminfo)")
        mi = meminfo_fallback()
        total = mi.get("MemTotal", 0)
        disp = mi.get("MemAvailable", 0)
        usado = total - disp
        pct = (usado / total * 100) if total else 0.0
        sw_total = mi.get("SwapTotal", 0)
        sw_usado = sw_total - mi.get("SwapFree", 0)

    if pct > 90:
        s.grade(CRIT)
        s.conduta = "RAM > 90% — feche uma IDE ou app pesado (teto físico 8GB)"
    elif pct > 80:
        s.grade(WARN)
        s.conduta = "RAM > 80% — atenção; nunca 2 IDEs abertas juntas"
    s.linhas.append(f"RAM usada {human(usado)} / {human(total)} ({pct:.0f}%)")
    s.linhas.append(f"swap usada {human(sw_usado)} / {human(sw_total)}")

    # zram ativo?
    zram = None
    try:
        for line in Path("/proc/swaps").read_text().splitlines()[1:]:
            campos = line.split()
            if campos and "zram" in campos[0]:
                zram = int(campos[2]) * 1024  # tamanho em kB -> B
    except OSError:
        pass
    s.linhas.append(f"zram: {'ATIVO — ' + human(zram) if zram else 'inativo'}")
    return s


# --------------------------------------------------------------------------- #
# 3. Top 5 processos por RAM   +   4. Doutrina IDEs (mesma varredura)
# --------------------------------------------------------------------------- #
def varredura_processos() -> tuple[list[tuple[float, str, float]], set[str]]:
    """Retorna (top_procs, ides). top_procs=[(rss, nome, mem_pct)]; ides={produto...}.

    O launcher novo do JetBrains é um binário nativo (`.../Toolbox/apps/<prod>/bin/<prod>`)
    que NÃO expõe `idea.paths.selector` no cmdline — então detectamos pelo nome do
    executável sob um caminho JetBrains. Dedupe por produto = nº de IDEs abertas.
    """
    procs: list[tuple[float, str, float]] = []
    ides: set[str] = set()
    # binários-launcher das IDEs (o processo-mãe tem esse nome exato)
    ide_bins = {
        "pycharm",
        "webstorm",
        "idea",
        "datagrip",
        "goland",
        "phpstorm",
        "clion",
        "rubymine",
        "rider",
        "intellij",
    }
    if not HAS_PSUTIL:
        return procs, ides
    for p in psutil.process_iter(
        ["name", "memory_percent", "memory_info", "cmdline", "exe"]
    ):
        try:
            info = p.info
            rss = info["memory_info"].rss if info.get("memory_info") else 0
            nome = info.get("name") or "?"
            procs.append((rss, nome, info.get("memory_percent") or 0.0))
            exe = info.get("exe") or ""
            base = os.path.basename(exe).lower() if exe else ""
            cand = base or nome.lower()
            # IDE = nome do binário bate E o executável mora numa pasta JetBrains
            if cand in ide_bins and (
                "/JetBrains/" in exe or "jetbrains" in exe.lower()
            ):
                ides.add(cand)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            AttributeError,
        ):
            continue
    procs.sort(key=lambda x: x[0], reverse=True)
    return procs[:5], ides


def sec_top(procs: list[tuple[float, str, float]]) -> Secao:
    s = Secao("Top 5 processos por RAM")
    if not HAS_PSUTIL:
        s.grade(WARN)
        s.conduta = "psutil ausente — instale:  pip install --user --break-system-packages psutil"
        s.linhas.append("(indisponível sem psutil)")
        return s
    for rss, nome, pct in procs:
        s.linhas.append(f"{nome[:24]:<24} {pct:5.1f}%  {human(rss):>8}")
    return s


def sec_ides(ides: set[str]) -> Secao:
    s = Secao("Doutrina IDEs (nunca 2 juntas — RAM 8GB)")
    if not HAS_PSUTIL:
        s.linhas.append("(indisponível sem psutil)")
        return s
    if not ides:
        s.linhas.append("nenhuma IDE JetBrains aberta")
    else:
        for prod in sorted(ides):
            s.linhas.append(f"aberta: {prod}")
    if len(ides) >= 2:
        s.grade(CRIT)
        s.conduta = f"{len(ides)} IDEs abertas ao mesmo tempo — feche uma (doutrina: nunca 2 juntas)"
    return s


# --------------------------------------------------------------------------- #
# 5. Conectores MCP da IDE
# --------------------------------------------------------------------------- #
def porta_viva(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def sec_mcp() -> Secao:
    s = Secao("Conectores MCP da IDE")
    cfg_path = HOME / ".claude.json"
    if not cfg_path.exists():
        s.grade(WARN)
        s.linhas.append("~/.claude.json não encontrado")
        s.conduta = "config global do Claude Code ausente"
        return s
    try:
        srv = json.loads(cfg_path.read_text()).get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        s.grade(WARN)
        s.linhas.append("~/.claude.json ilegível")
        return s
    algum_morto = False
    for nome in ("jetbrains", "jetbrains-index"):
        url = srv.get(nome, {}).get("url")
        if not url:
            s.grade(WARN)
            s.linhas.append(f"{nome}: entrada ausente")
            algum_morto = True
            continue
        u = urlparse(url)
        vivo = porta_viva(u.hostname or "127.0.0.1", u.port or 0)
        s.linhas.append(f"{nome}: porta {u.port} {'responde' if vivo else 'MORTA'}")
        if not vivo:
            s.grade(WARN)
            algum_morto = True
    if algum_morto:
        s.conduta = "porta MCP da IDE morta — rode  python3 ~/projetos/scripts/pc/fix_ide_mcp.py  e depois  /mcp"
    return s


# --------------------------------------------------------------------------- #
# 6. Node (default do nvm)
# --------------------------------------------------------------------------- #
def sec_node() -> Secao:
    s = Secao("Node (default do nvm)")
    default = None
    ativo = None
    try:
        r = subprocess.run(
            [
                "bash",
                "-lc",
                'source ~/.nvm/nvm.sh >/dev/null 2>&1 && echo "$(nvm version default) $(node -v 2>/dev/null)"',
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        parts = r.stdout.split()
        if parts:
            default = parts[0]
        if len(parts) > 1:
            ativo = parts[1]
    except (subprocess.SubprocessError, OSError):
        pass
    # fallback: lê o alias e resolve contra as versões instaladas
    if not default or not default.startswith("v"):
        alias = HOME / ".nvm/alias/default"
        vdir = HOME / ".nvm/versions/node"
        if alias.exists() and vdir.exists():
            want = alias.read_text().strip()
            cands = sorted(
                p.name for p in vdir.iterdir() if p.name.startswith(f"v{want}")
            )
            default = cands[-1] if cands else want

    if default and re.match(r"v?24\.", default):
        s.linhas.append(f"default do nvm: {default}")
    else:
        s.grade(WARN)
        s.linhas.append(f"default do nvm: {default or 'não resolvido'}")
        s.conduta = "padrão da casa é Node 24.x — rode  nvm alias default 24"
    if ativo and default and ativo != default:
        s.linhas.append(f"(nota: node ativo no shell = {ativo}, difere do default)")
    return s


# --------------------------------------------------------------------------- #
# 7. Repos git (offline, sem fetch)
# --------------------------------------------------------------------------- #
def sec_git() -> Secao:
    s = Secao("Repos git (offline)")
    repos = [HOME / "projetos/SASI-V3", HOME / "projetos/claude", HOME / "vaults/celebro"]
    sujo_ou_frente = False
    for repo in repos:
        if not (repo / ".git").exists():
            s.linhas.append(f"{repo.name}: (sem repo git)")
            continue
        try:
            porcelain = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
            sb = subprocess.run(
                ["git", "-C", str(repo), "status", "-sb"],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.splitlines()
        except (subprocess.SubprocessError, OSError):
            s.linhas.append(f"{repo.name}: git indisponível")
            continue
        n_mod = len([l for l in porcelain.splitlines() if l.strip()])
        head = sb[0] if sb else ""
        am = re.search(r"ahead (\d+)", head)
        bm = re.search(r"behind (\d+)", head)
        ahead = int(am.group(1)) if am else 0
        behind = int(bm.group(1)) if bm else 0
        marca = ""
        if n_mod or ahead:
            marca = " ⚠️"
            sujo_ou_frente = True
        estado = []
        if n_mod:
            estado.append(f"{n_mod} mod")
        if ahead:
            estado.append(f"{ahead} à frente")
        if behind:
            estado.append(f"{behind} atrás")
        s.linhas.append(
            f"{repo.name}: {', '.join(estado) if estado else 'limpo'}{marca}"
        )
    if sujo_ou_frente:
        s.grade(WARN)
        s.conduta = "repo sujo ou à frente — commitar/pushar o que estiver pronto"
    return s


# --------------------------------------------------------------------------- #
# 8. Camada cache (~/Downloads)
# --------------------------------------------------------------------------- #
def sec_downloads() -> Secao:
    s = Secao("Cache (~/Downloads)")
    dl = HOME / "Downloads"
    n = len(list(dl.iterdir())) if dl.exists() else 0
    s.linhas.append(f"{n} itens (doutrina: Downloads é cache temporário)")
    if n > 30:
        s.grade(WARN)
        s.conduta = "> 30 itens em Downloads — triar/limpar (é cache, não depósito)"
    return s


# --------------------------------------------------------------------------- #
def main() -> int:
    print("=" * 60)
    print("  BOLETIM DE SAÚDE — PC Tijolão")
    if not HAS_PSUTIL:
        print("  (aviso: psutil ausente — seções de memória/processos degradadas)")
    print("=" * 60)

    top, ides = varredura_processos()
    secoes = [
        sec_disco(),
        sec_ram(),
        sec_top(top),
        sec_ides(ides),
        sec_mcp(),
        sec_node(),
        sec_git(),
        sec_downloads(),
    ]

    for sec in secoes:
        print(f"\n{sec.icon}  {sec.titulo}")
        for l in sec.linhas:
            print(f"     {l}")

    n_ok = sum(1 for s in secoes if s.icon == OK)
    n_wa = sum(1 for s in secoes if s.icon == WARN)
    n_cr = sum(1 for s in secoes if s.icon == CRIT)
    print("\n" + "-" * 60)
    print(f"BOLETIM: {n_ok} {OK} · {n_wa} {WARN} · {n_cr} {CRIT}")

    condutas = [(s.icon, s.conduta) for s in secoes if s.conduta]
    if condutas:
        print("\nConduta:")
        for icon, c in condutas:
            print(f"  {icon} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
