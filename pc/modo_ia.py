#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modo IA do Tijolão — prepara a máquina para rodar um modelo de linguagem local.

O problema que este script resolve: o Tijolão tem 8 GB de RAM em CANAL ÚNICO e um
modelo de 4B em Q4 ocupa ~2,5 GB. Se o Chrome e o Claude Desktop estiverem abertos,
não sobra espaço e o modelo agoniza no disco em vez de rodar na memória.

O que ele faz:
  - mede se DÁ para rodar agora (orçamento de RAM contra o tamanho do modelo);
  - sobe o governador da CPU e o perfil de energia enquanto o modelo trabalha;
  - aponta quem está comendo a RAM e quanto cada um liberaria;
  - devolve a máquina ao estado normal quando você terminar.

O que ele NÃO faz sem você mandar: fechar programa. Fechar exige `--fechar`
e confirmação digitada. E ele NUNCA fecha o terminal onde ele mesmo está rodando.

Uso:
    python3 modo_ia.py                 # boletim: dá para rodar IA local agora?
    python3 modo_ia.py on              # liga o modo IA (energia no máximo)
    python3 modo_ia.py off             # devolve a máquina ao normal
    python3 modo_ia.py on --fechar     # liga E fecha os comedores de RAM (pede confirmação)
    python3 modo_ia.py on --fechar --sim   # sem perguntar (para script)
    python3 modo_ia.py --modelo 4.7    # calcula o orçamento para um modelo de 4,7 GB

Saída: exit 0 se a máquina está pronta, exit 1 se falta RAM para o modelo alvo.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ENV_FILE = Path.home() / "projetos" / ".env"
GOV_PATH = "/sys/devices/system/cpu/cpu{}/cpufreq/scaling_governor"
EPP_PATH = "/sys/devices/system/cpu/cpu{}/cpufreq/energy_performance_preference"

# Tamanho padrão do alvo: qwen3:4b em Q4 = 2,5 GB de pesos.
# Somamos folga para o cache de contexto e o processo do Ollama.
MODELO_GB_PADRAO = 2.5
FOLGA_GB = 0.8

# Programas que valem a pena fechar antes de rodar o modelo, por nome de processo.
# `claude-desktop` é o aplicativo Electron; o `claude` puro é a linha de comando
# (possivelmente ESTA sessão) e por isso está fora da lista de propósito.
COMEDORES = {
    "chrome": "Google Chrome",
    "chromium": "Chromium",
    "claude-desktop": "Claude Desktop",
    "webstorm": "WebStorm",
    "datagrip": "DataGrip",
    "idea": "IDE JetBrains",
    "code": "VS Code",
    "electron": "app Electron",
}

VERDE, AMARELO, VERMELHO = "\033[92m", "\033[93m", "\033[91m"
NEGRITO, FIM = "\033[1m", "\033[0m"


# --------------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------------
def ler(caminho: str) -> str:
    try:
        return Path(caminho).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def senha_sudo() -> str | None:
    """Lê SUDO_TIJOLAO_PASSWORD do cofre ~/projetos/.env. Nunca imprime o valor."""
    if not ENV_FILE.exists():
        return None
    for linha in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r'^\s*(?:export\s+)?SUDO_TIJOLAO_PASSWORD\s*=\s*(.*)$', linha)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def sudo(comando: list[str]) -> tuple[int, str]:
    """Roda um comando com sudo.

    Regra de ouro aprendida na marra: o comando alvo NÃO pode ler a entrada
    padrão, senão ele engole a senha e a grava no lugar do conteúdo. Por isso
    escrita em arquivo é sempre via `sh -c 'echo ... > ...'`, nunca via `tee`.
    """
    pw = senha_sudo()
    if pw is None:
        return 1, "SUDO_TIJOLAO_PASSWORD não encontrada em ~/projetos/.env"
    try:
        p = subprocess.run(
            ["sudo", "-S", "-p", ""] + comando,
            input=pw + "\n", capture_output=True, text=True, timeout=60,
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def rodar(comando: list[str]) -> str:
    try:
        p = subprocess.run(comando, capture_output=True, text=True, timeout=20)
        return (p.stdout or p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def gb(bytes_: float) -> float:
    return round(bytes_ / 1024 ** 3, 2)


# --------------------------------------------------------------------------
# coleta
# --------------------------------------------------------------------------
def nucleos() -> list[int]:
    return sorted(
        int(m.group(1))
        for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*")
        if (m := re.match(r"cpu(\d+)$", p.name)) and (p / "cpufreq").exists()
    )


def energia() -> dict:
    ns = nucleos()
    ac = ler("/sys/class/power_supply/AC/online") or ler("/sys/class/power_supply/ACAD/online")
    if not ac:
        for p in Path("/sys/class/power_supply").glob("A*"):
            if (p / "online").exists():
                ac = ler(str(p / "online"))
                break
    perfil = rodar(["powerprofilesctl", "get"]) if os.path.exists("/usr/bin/powerprofilesctl") else ""
    return {
        "na_tomada": ac == "1",
        "governadores": {c: ler(GOV_PATH.format(c)) for c in ns},
        "epp": {c: ler(EPP_PATH.format(c)) for c in ns},
        "perfil_daemon": perfil,
        "turbo_desligado": ler("/sys/devices/system/cpu/intel_pstate/no_turbo") == "1",
    }


def memoria() -> dict:
    info = {}
    for linha in ler("/proc/meminfo").splitlines():
        chave, _, resto = linha.partition(":")
        info[chave] = int(resto.strip().split()[0]) * 1024
    psi = ler("/proc/pressure/memory").splitlines()
    return {
        "total": info.get("MemTotal", 0),
        "disponivel": info.get("MemAvailable", 0),
        "cache": info.get("Cached", 0),
        "swap_total": info.get("SwapTotal", 0),
        "swap_livre": info.get("SwapFree", 0),
        "psi_full": psi[1] if len(psi) > 1 else "",
    }


def processos() -> list[tuple[int, str, int]]:
    """(pid, nome, rss) de todo processo do usuário, do mais pesado ao mais leve."""
    saida = rodar(["ps", "-eo", "pid=,rss=,comm=", "--sort=-rss"])
    out = []
    for linha in saida.splitlines():
        partes = linha.split(None, 2)
        if len(partes) == 3 and partes[1].isdigit():
            out.append((int(partes[0]), partes[2].strip(), int(partes[1]) * 1024))
    return out


def linhagem_propria() -> set[int]:
    """PIDs desta sessão e de todos os seus pais — intocáveis."""
    protegidos, pid = set(), os.getpid()
    while pid and pid > 1 and len(protegidos) < 40:
        protegidos.add(pid)
        stat = ler(f"/proc/{pid}/stat")
        if not stat:
            break
        try:
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (IndexError, ValueError):
            break
    return protegidos


def comedores() -> dict[str, tuple[list[int], int]]:
    """Agrupa por aplicativo: nome -> (pids, RAM somada). Exclui a própria linhagem."""
    protegidos = linhagem_propria()
    grupos: dict[str, tuple[list[int], int]] = {}
    for pid, nome, rss in processos():
        if pid in protegidos:
            continue
        chave = next((k for k in COMEDORES if k in nome.lower()), None)
        if not chave:
            continue
        pids, total = grupos.get(COMEDORES[chave], ([], 0))
        grupos[COMEDORES[chave]] = (pids + [pid], total + rss)
    return dict(sorted(grupos.items(), key=lambda kv: -kv[1][1]))


def termico() -> dict:
    saida = rodar(["sensors"])
    cpu = re.search(r"^CPU:\s+\+?([\d.]+)", saida, re.M)
    fan = re.search(r"Fan:\s+(\d+) RPM", saida)
    pkg = re.search(r"Package id 0:\s+\+?([\d.]+)", saida, re.M)
    return {
        "cpu_c": float(cpu.group(1)) if cpu else (float(pkg.group(1)) if pkg else None),
        "ventilador_rpm": int(fan.group(1)) if fan else None,
    }


def ollama() -> dict:
    ativo = rodar(["systemctl", "is-active", "ollama"]) == "active"
    lista = rodar(["ollama", "list"])
    carregado = rodar(["ollama", "ps"])
    modelos = [l.split()[0] for l in lista.splitlines()[1:] if l.strip()]
    return {
        "ativo": ativo,
        "modelos": modelos,
        "carregado": [l.split()[0] for l in carregado.splitlines()[1:] if l.strip()],
    }


# --------------------------------------------------------------------------
# ações
# --------------------------------------------------------------------------
def aplicar_energia(ligar: bool) -> list[str]:
    """Sobe (ou devolve) governador, EPP e perfil de energia. Devolve o log."""
    log = []
    gov = "performance" if ligar else "powersave"
    epp = "performance" if ligar else "balance_performance"
    perfil = "performance" if ligar else "balanced"

    if os.path.exists("/usr/bin/powerprofilesctl"):
        # o daemon manda no EPP; mexer no sysfs sem ele é desfeito em seguida
        rc, msg = 0, rodar(["powerprofilesctl", "set", perfil])
        atual = rodar(["powerprofilesctl", "get"])
        log.append(f"perfil de energia -> {atual or 'falhou'}" + (f" ({msg})" if msg else ""))

    # o cpupower do Mint depende do pacote linux-tools da versão EXATA do kernel;
    # num kernel recém-atualizado ele existe mas falha. Por isso o plano B roda
    # sempre que o governador não tiver mudado — não só quando o binário falta.
    if os.path.exists("/usr/bin/cpupower"):
        sudo(["cpupower", "frequency-set", "-g", gov])
    if ler(GOV_PATH.format(nucleos()[0])) != gov:
        for c in nucleos():
            sudo(["sh", "-c", f"echo {gov} > {GOV_PATH.format(c)}"])
    obtido = ler(GOV_PATH.format(nucleos()[0]))
    log.append(f"governador -> {obtido}" if obtido == gov
               else f"governador NAO MUDOU (continua {obtido})")

    # o EPP às vezes não acompanha o perfil do daemon; forçamos por núcleo
    for c in nucleos():
        if ler(EPP_PATH.format(c)) != epp:
            sudo(["sh", "-c", f"echo {epp} > {EPP_PATH.format(c)}"])
    log.append(f"EPP -> {ler(EPP_PATH.format(nucleos()[0])) or 'n/d'}")
    return log


def fechar(grupos: dict[str, tuple[list[int], int]], sem_perguntar: bool) -> list[str]:
    if not grupos:
        return ["nada para fechar"]
    print(f"\n{NEGRITO}Vou pedir para estes programas fecharem (SIGTERM, salvam antes de sair):{FIM}")
    for nome, (pids, rss) in grupos.items():
        print(f"  {nome:20} {len(pids):>3} processos   libera {gb(rss):>5} GB")
    print(f"  {'TOTAL':20} {'':>3}             libera {gb(sum(r for _, r in grupos.values())):>5} GB")
    if not sem_perguntar:
        try:
            if input(f"\n{AMARELO}Digite FECHAR para confirmar: {FIM}").strip() != "FECHAR":
                return ["cancelado por você — nada foi fechado"]
        except (EOFError, KeyboardInterrupt):
            return ["cancelado — nada foi fechado"]
    log = []
    for nome, (pids, rss) in grupos.items():
        ok = 0
        for pid in pids:
            try:
                os.kill(pid, 15)
                ok += 1
            except OSError:
                pass
        log.append(f"{nome}: pedido de saída enviado a {ok}/{len(pids)} processos (~{gb(rss)} GB)")
    return log


# --------------------------------------------------------------------------
# boletim
# --------------------------------------------------------------------------
def boletim(modelo_gb: float) -> int:
    e, m, t, o = energia(), memoria(), termico(), ollama()
    grupos = comedores()
    preciso = modelo_gb + FOLGA_GB
    disp = gb(m["disponivel"])
    libera = gb(sum(r for _, r in grupos.values()))

    print(f"\n{NEGRITO}== MODO IA — Tijolão =={FIM}")

    print(f"\n{NEGRITO}Energia{FIM}")
    govs = set(e["governadores"].values())
    print(f"  tomada          {'sim' if e['na_tomada'] else 'NÃO — na bateria'}")
    print(f"  governador      {'/'.join(sorted(govs))}")
    print(f"  EPP             {'/'.join(sorted(set(e['epp'].values())))}")
    if e["perfil_daemon"]:
        print(f"  perfil daemon   {e['perfil_daemon']}")
    print(f"  turbo           {'DESLIGADO' if e['turbo_desligado'] else 'ligado'}")

    print(f"\n{NEGRITO}Memória{FIM}")
    print(f"  total           {gb(m['total'])} GB")
    print(f"  disponível      {disp} GB")
    print(f"  swap em uso     {gb(m['swap_total'] - m['swap_livre'])} GB de {gb(m['swap_total'])} GB")
    if m["psi_full"]:
        print(f"  pressão (PSI)   {m['psi_full']}")

    if t["cpu_c"] is not None:
        estrangula = t["cpu_c"] >= 85
        cor = VERMELHO if estrangula else VERDE
        print(f"\n{NEGRITO}Térmico{FIM}")
        print(f"  CPU             {cor}{t['cpu_c']} °C{FIM}"
              + ("  <- estrangulando" if estrangula else ""))
        if t["ventilador_rpm"] is not None:
            print(f"  ventilador      {t['ventilador_rpm']} RPM")

    print(f"\n{NEGRITO}Ollama{FIM}")
    print(f"  serviço         {'ativo' if o['ativo'] else 'PARADO'}")
    print(f"  modelos         {', '.join(o['modelos']) if o['modelos'] else 'nenhum baixado'}")
    print(f"  carregado agora {', '.join(o['carregado']) if o['carregado'] else '-'}")

    if grupos:
        print(f"\n{NEGRITO}Comendo a sua RAM{FIM}")
        for nome, (pids, rss) in grupos.items():
            print(f"  {nome:20} {gb(rss):>5} GB  ({len(pids)} processos)")

    print(f"\n{NEGRITO}Veredito{FIM} — modelo de {modelo_gb} GB precisa de ~{round(preciso, 2)} GB livres")
    if disp >= preciso:
        print(f"  {VERDE}PRONTO{FIM}: {disp} GB disponíveis. Pode rodar.")
        return 0
    if disp + libera >= preciso:
        falta = round(preciso - disp, 2)
        print(f"  {AMARELO}FALTAM {falta} GB{FIM}: fechando os programas acima você libera "
              f"{libera} GB e sobra folga.")
        print(f"  Comando: python3 {Path(__file__).name} on --fechar")
        return 1
    print(f"  {VERMELHO}NÃO CABE{FIM}: {disp} GB livres + {libera} GB fechando tudo "
          f"= {round(disp + libera, 2)} GB, contra {round(preciso, 2)} GB necessários.")
    print("  Escolha um modelo menor, ou instale o 2º pente de RAM (o slot ChannelB está vazio).")
    return 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Prepara o Tijolão para rodar IA local.")
    ap.add_argument("acao", nargs="?", default="status", choices=["status", "on", "off"],
                    help="status (padrão) = só o boletim; on = liga o modo IA; off = devolve ao normal")
    ap.add_argument("--fechar", action="store_true", help="fecha os programas que comem RAM")
    ap.add_argument("--sim", action="store_true", help="não pergunta antes de fechar")
    ap.add_argument("--modelo", type=float, default=MODELO_GB_PADRAO,
                    help=f"tamanho do modelo em GB (padrão {MODELO_GB_PADRAO})")
    ap.add_argument("--forcar", action="store_true", help="liga o modo IA mesmo na bateria")
    args = ap.parse_args()

    if args.acao == "off":
        print(f"{NEGRITO}Devolvendo o Tijolão ao normal{FIM}")
        for l in aplicar_energia(False):
            print(f"  {l}")
        return 0

    if args.acao == "on":
        if not energia()["na_tomada"] and not args.forcar:
            print(f"{VERMELHO}Na bateria.{FIM} Governador em performance na bateria esquenta e "
                  f"dura pouco. Ligue na tomada, ou use --forcar se souber o que está fazendo.")
            return 1
        print(f"{NEGRITO}Ligando o modo IA{FIM}")
        for l in aplicar_energia(True):
            print(f"  {l}")
        if args.fechar:
            for l in fechar(comedores(), args.sim):
                print(f"  {l}")

    return boletim(args.modelo)


if __name__ == "__main__":
    sys.exit(main())
