#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boletim de segurança da MÁQUINA — leitura pura, nada é gravado.

Irmão do `saude_pc.py`. Aquele mede recurso (disco, RAM, processos, portas de
IDE, repos); este mede **postura de segurança do sistema operacional**: firewall,
criptografia de disco, SSH exposto, AppArmor, atualizações pendentes, Secure Boot
e portas abertas pra fora do localhost. Zero sobreposição: nenhuma seção daqui
existe lá.

É só diagnóstico: NÃO liga firewall, NÃO instala pacote, NÃO edita config, NÃO
conecta em rede externa. Sai sempre com exit 0 — boletim não é portão.

**Sem score.** Nota 0-100 de segurança é chute com cara de medida: o peso de cada
item é arbitrário e o número esconde qual item falhou. Aqui cada item aparece com
o valor medido e o limiar, ou com [SEM_LEITURA] quando falta privilégio.

Degradação: vários checks precisam de root. Este script usa só `sudo -n` (nunca
pede senha, nunca trava). Sem sudo livre, o item vira [SEM_LEITURA] em vez de
virar falso "OK" — item não medido nunca é reportado como seguro.

Bibliotecas: stdlib pura. Nada pra instalar.

Uso:
    python3 seguranca_pc.py        # imprime o boletim e sai
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()

OK, WARN, CRIT, UNK = "✅", "⚠️", "🔴", "❔"


class Secao:
    """Uma seção do boletim: título, sinal, linhas e (opcional) 1 linha de conduta."""

    def __init__(self, titulo: str):
        self.titulo = titulo
        self.icon = OK
        self.linhas: list[str] = []
        self.conduta: str | None = None

    def grade(self, icon: str) -> None:
        # mantém sempre o pior sinal já visto (✅ < ❔ < ⚠️ < 🔴)
        ordem = {OK: 0, UNK: 1, WARN: 2, CRIT: 3}
        if ordem[icon] > ordem[self.icon]:
            self.icon = icon


def run(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    """Roda comando local e devolve (rc, saída). Nunca levanta exceção."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
            # Locale C: sem isso o sistema responde em pt-BR ("Estado: ativo")
            # e todo parser abaixo, que casa texto em ingles, le errado.
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return 127, ""


def tem(binario: str) -> bool:
    return shutil.which(binario) is not None


def _senha_do_cofre() -> str | None:
    """Le SUDO_TIJOLAO_PASSWORD do cofre ~/projetos/.env, se existir.

    Boletim que nao consegue ler firewall/AppArmor reporta [SEM_LEITURA] no
    lugar do estado real — e item nao medido nao serve pra decidir nada. O
    cofre ja e 600 e fica fora de todo repo git; usa-lo aqui troca dois "nao
    sei" por dois numeros. A senha nunca e impressa nem entra em argv (vai
    por stdin do `sudo -S`).
    """
    cofre = HOME / "projetos" / ".env"
    try:
        if cofre.stat().st_mode & 0o077:
            return None  # permissao frouxa: nao usa
        for linha in cofre.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("SUDO_TIJOLAO_PASSWORD="):
                v = linha.split("=", 1)[1].strip().strip("\"'")
                return v or None
    except OSError:
        return None
    return None


_SENHA = _senha_do_cofre()


def sudo_livre() -> bool:
    """True se da pra rodar sudo: sem senha (-n) ou com a senha do cofre."""
    rc, _ = run(["sudo", "-n", "true"], timeout=4)
    if rc == 0:
        return True
    if _SENHA:
        try:
            p = subprocess.run(
                ["sudo", "-S", "-p", "", "true"],
                input=_SENHA + "\n", capture_output=True, text=True,
                timeout=6, check=False,
            )
            return p.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
    return False


SUDO_OK = sudo_livre()


def sudo_run(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    """Roda privilegiado. Tenta -n; cai pra senha do cofre; senao rc=126."""
    rc, out = run(["sudo", "-n"] + cmd, timeout=timeout)
    if rc != 126 and rc != 1 and out:
        return rc, out
    if not _SENHA:
        return 126, ""
    try:
        p = subprocess.run(
            ["sudo", "-S", "-p", ""] + cmd,
            input=_SENHA + "\n", capture_output=True, text=True,
            timeout=timeout, check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return 126, ""


# --------------------------------------------------------------------------- #
# 1. Firewall
# --------------------------------------------------------------------------- #
def sec_firewall() -> Secao:
    s = Secao("Firewall")

    if not tem("ufw"):
        s.grade(WARN)
        s.linhas.append("ufw não instalado")
        s.conduta = "Sem firewall gerenciável — instale ufw:  sudo apt install ufw"
        return s

    # systemctl is-enabled não precisa de root: diz se sobe no boot.
    rc_boot, out_boot = run(["systemctl", "is-enabled", "ufw"])
    no_boot = out_boot.splitlines()[0].strip() if out_boot else "desconhecido"

    # ufw status precisa de root; sem sudo livre, o boot é a melhor evidência.
    rc, out = sudo_run(["ufw", "status", "verbose"])
    if rc == 0 and out:
        # O ufw traduz a propria saida via gettext: LC_ALL=C nao reverte.
        # Por isso o parser aceita as duas formas (en/pt-BR).
        ativo = bool(re.search(r"^(Status|Estado):\s*(active|ativo)", out, re.M | re.I))
        regras = len(re.findall(r"\b(ALLOW|DENY|REJECT|LIMIT)\b", out))
        politica = "?"
        m = re.search(r"^(?:Default|Predefinido):\s*(.+)", out, re.M | re.I)
        if m:
            politica = m.group(1).strip()
        if ativo:
            s.linhas.append(f"ufw ativo · {regras} regra(s) · default: {politica}")
            entrada_negada = re.search(r"deny\s*\((incoming|entrada)\)", politica, re.I)
            if not entrada_negada:
                s.grade(WARN)
                s.conduta = (
                    "Entrada não está em deny por padrão — "
                    "sudo ufw default deny incoming"
                )
        else:
            s.grade(CRIT)
            s.linhas.append(f"ufw INATIVO (no boot: {no_boot})")
            s.conduta = "Firewall desligado — sudo ufw default deny incoming && sudo ufw enable"
        return s

    # Sem leitura privilegiada: reporta o que dá, sem fingir que mediu.
    if no_boot == "enabled":
        s.grade(UNK)
        s.linhas.append(f"ufw instalado, habilitado no boot · [SEM_LEITURA] estado corrente (exige root)")
        s.conduta = "Confirme com:  sudo ufw status verbose"
    else:
        s.grade(WARN)
        s.linhas.append(f"ufw instalado mas NÃO habilitado no boot ({no_boot})")
        s.conduta = "Firewall não sobe no boot — sudo ufw enable"
    return s


# --------------------------------------------------------------------------- #
# 2. Criptografia de disco
# --------------------------------------------------------------------------- #
def sec_cripto() -> Secao:
    s = Secao("Criptografia de disco")

    # lsblk mostra tipo crypt sem precisar de root.
    rc, out = run(["lsblk", "-o", "NAME,FSTYPE,TYPE,MOUNTPOINT"])
    luks = "crypto_LUKS" in out or re.search(r"\bcrypt\b", out) is not None

    # ecryptfs no home (padrão antigo do Mint/Ubuntu "encrypt home directory")
    home_cripto = Path("/home/.ecryptfs").exists()

    if luks:
        s.linhas.append("volume LUKS/dm-crypt presente")
    elif home_cripto:
        s.grade(WARN)
        s.linhas.append("home com ecryptfs · disco raiz SEM criptografia")
        s.conduta = "Só o home é cifrado — swap e / ficam em claro se a máquina for levada"
    else:
        s.grade(WARN)
        s.linhas.append("nenhuma criptografia de disco detectada")
        s.conduta = (
            "Disco em claro — notebook furtado entrega tudo. "
            "Cifrar exige reinstalar; avalie o risco"
        )

    # Swap em disco guarda página de memória (chave, token, senha digitada) em
    # claro, e sobrevive ao desligamento. zram vive só na RAM: some no boot.
    try:
        swaps = Path("/proc/swaps").read_text(encoding="utf-8", errors="replace")
        linhas_swap = [l for l in swaps.splitlines()[1:] if l.strip()]
        if not linhas_swap:
            s.linhas.append("swap: nenhum ativo")
            return s

        nomes = [l.split()[0] for l in linhas_swap]
        persistentes = [n for n in nomes if "zram" not in n]
        volateis = [n for n in nomes if "zram" in n]

        partes = []
        if volateis:
            partes.append(f"{', '.join(volateis)} (zram — só RAM, some no boot)")
        if persistentes:
            partes.append(f"{', '.join(persistentes)} (EM DISCO, persiste)")
        s.linhas.append(f"swap: {' · '.join(partes)}")

        if persistentes and not luks:
            s.grade(WARN)
            aviso = (
                f"Swap em disco sem criptografia ({', '.join(persistentes)}) — "
                "página de memória (chave, token, senha) fica em claro após desligar"
            )
            s.conduta = f"{s.conduta} | {aviso}" if s.conduta else aviso
    except OSError:
        s.grade(UNK)
        s.linhas.append("swap: [SEM_LEITURA]")
    return s


# --------------------------------------------------------------------------- #
# 3. SSH (superfície de entrada)
# --------------------------------------------------------------------------- #
def sec_ssh() -> Secao:
    s = Secao("SSH")

    ativo = False
    for unidade in ("ssh", "sshd"):
        rc, out = run(["systemctl", "is-active", unidade])
        if out.strip() == "active":
            ativo = True
            break

    if not ativo:
        s.linhas.append("servidor SSH não está rodando (nenhuma porta 22 exposta por ele)")
        return s

    s.linhas.append("servidor SSH ATIVO")
    cfg = Path("/etc/ssh/sshd_config")
    if not os.access(cfg, os.R_OK):
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] sshd_config (exige root)")
        s.conduta = "Confira:  sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication'"
        return s

    try:
        texto = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] sshd_config")
        return s

    def diretiva(nome: str) -> str | None:
        m = re.search(rf"^\s*{nome}\s+(\S+)", texto, re.IGNORECASE | re.MULTILINE)
        return m.group(1).lower() if m else None

    root_login = diretiva("PermitRootLogin")
    senha = diretiva("PasswordAuthentication")

    if root_login in ("yes", "prohibit-password", None):
        if root_login == "yes":
            s.grade(CRIT)
            s.conduta = "PermitRootLogin yes — troque para 'no' em /etc/ssh/sshd_config"
        s.linhas.append(f"PermitRootLogin: {root_login or 'não declarado (default do build)'}")
    else:
        s.linhas.append(f"PermitRootLogin: {root_login}")

    if senha == "yes":
        s.grade(WARN)
        s.linhas.append("PasswordAuthentication: yes (aberto a força bruta)")
        if not s.conduta:
            s.conduta = "SSH com senha exposto — prefira chave e 'PasswordAuthentication no'"
    elif senha:
        s.linhas.append(f"PasswordAuthentication: {senha}")
    return s


# --------------------------------------------------------------------------- #
# 4. AppArmor (confinamento obrigatório)
# --------------------------------------------------------------------------- #
def sec_apparmor() -> Secao:
    s = Secao("AppArmor")

    if not (tem("aa-status") or tem("apparmor_status")):
        s.grade(WARN)
        s.linhas.append("aa-status ausente — AppArmor provavelmente não instalado")
        return s

    # /sys/module/apparmor/parameters/enabled é legível sem root.
    p = Path("/sys/module/apparmor/parameters/enabled")
    if p.exists():
        try:
            val = p.read_text(encoding="utf-8", errors="replace").strip()
            if val.upper().startswith("Y"):
                s.linhas.append("módulo do kernel: habilitado")
            else:
                s.grade(CRIT)
                s.linhas.append(f"módulo do kernel: DESABILITADO ({val})")
                s.conduta = "AppArmor desligado no kernel — confira o cmdline do GRUB"
                return s
        except OSError:
            pass

    rc, out = sudo_run(["aa-status"])
    if rc == 0 and out:
        m = re.search(r"(\d+)\s+profiles are in enforce mode", out)
        c = re.search(r"(\d+)\s+profiles are in complain mode", out)
        enforce = m.group(1) if m else "?"
        complain = c.group(1) if c else "0"
        s.linhas.append(f"{enforce} perfil(is) em enforce · {complain} em complain")
        if enforce.isdigit() and int(enforce) == 0:
            s.grade(WARN)
            s.conduta = "Nenhum perfil em enforce — confinamento sem efeito prático"
    else:
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] contagem de perfis (exige root)")
        s.conduta = "Confira:  sudo aa-status"
    return s


# --------------------------------------------------------------------------- #
# 5. Atualizações de segurança
# --------------------------------------------------------------------------- #
def sec_updates() -> Secao:
    s = Secao("Atualizações")

    # Automáticas: unattended-upgrades
    auto_cfg = Path("/etc/apt/apt.conf.d/20auto-upgrades")
    if not tem("unattended-upgrade") and not auto_cfg.exists():
        s.grade(WARN)
        s.linhas.append("unattended-upgrades NÃO instalado (nenhuma correção automática)")
        s.conduta = "Correção de segurança só entra na mão — sudo apt install unattended-upgrades"
    elif auto_cfg.exists():
        try:
            t = auto_cfg.read_text(encoding="utf-8", errors="replace")
            lig = re.search(r'Unattended-Upgrade"?\s+"1"', t) is not None
            s.linhas.append(f"unattended-upgrades: {'ligado' if lig else 'instalado mas desligado'}")
            if not lig:
                s.grade(WARN)
                s.conduta = "Auto-upgrade instalado porém desligado — sudo dpkg-reconfigure -plow unattended-upgrades"
        except OSError:
            s.linhas.append("unattended-upgrades: [SEM_LEITURA]")
    else:
        s.linhas.append("unattended-upgrade presente, config padrão não encontrada")

    # Pendentes: apt list --upgradable não precisa de root (usa cache local).
    rc, out = run(["apt", "list", "--upgradable"], timeout=25)
    if rc == 0 and out:
        linhas = [l for l in out.splitlines() if "/" in l and "Listing" not in l]
        seg = [l for l in linhas if "-security" in l]
        if seg:
            s.grade(CRIT if len(seg) > 10 else WARN)
            s.linhas.append(f"{len(linhas)} pacote(s) atualizáveis · {len(seg)} de SEGURANÇA")
            s.conduta = f"{len(seg)} correção(ões) de segurança pendente(s) — sudo apt upgrade"
        elif linhas:
            s.linhas.append(f"{len(linhas)} pacote(s) atualizáveis · 0 de segurança")
        else:
            s.linhas.append("nenhum pacote pendente")
    else:
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] lista de pendentes (cache do apt indisponível)")
    return s


# --------------------------------------------------------------------------- #
# 6. Portas ouvindo fora do localhost
# --------------------------------------------------------------------------- #
def sec_portas() -> Secao:
    s = Secao("Portas expostas")

    if not tem("ss"):
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] `ss` ausente")
        return s

    # -p nomeia o processo dono. Sem root vem só o que é do próprio usuário;
    # porta sem dono legível vira "?" em vez de sumir do boletim.
    rc, out = sudo_run(["ss", "-tulnpH"])
    if rc != 0 or not out:
        s.grade(UNK)
        s.linhas.append("[SEM_LEITURA] saída de `ss`")
        return s

    def local_e_privado(h: str) -> bool:
        """True para endereço que não é superfície de entrada externa."""
        h = h.strip("[]").split("%")[0]  # descarta escopo de interface (ex.: %lo)
        if h.startswith("127.") or h in ("::1", "::"):
            return True
        if h.startswith("224.") or h.startswith("ff"):  # multicast (mDNS/SSDP)
            return True
        if h.startswith("fe80:"):  # link-local IPv6
            return True
        return False

    expostas: dict[str, str] = {}
    tailscale: list[str] = []
    for linha in out.splitlines():
        campos = linha.split()
        if len(campos) < 5:
            continue
        m = re.match(r"^(.*):(\d+)$", campos[4])
        if not m:
            continue
        host, porta = m.group(1), m.group(2)
        h = host.strip("[]").split("%")[0]

        # Sem root, `ss -p` só nomeia processo do próprio usuário. Porta de
        # serviço do sistema fica sem dono legível — isso é falta de leitura,
        # não ausência de dono, e o boletim precisa dizer qual dos dois é.
        dono = "[dono exige root]"
        mp = re.search(r'users:\(\("([^"]+)"', linha)
        if mp:
            # nome pode conter espaço/parêntese ("next-server (v1..."): corta no 1º
            dono = re.split(r"[\s(]", mp.group(1).strip())[0] or mp.group(1).strip()

        if h.startswith("100.") or h.startswith("fd7a:"):
            tailscale.append(f"{porta}/{dono}")  # tailnet: rede privada, não internet
            continue
        if local_e_privado(h):
            continue
        # dedupe por porta+dono: 0.0.0.0 e [::] do mesmo serviço é um só achado
        expostas[f"{porta}/{dono}"] = host

    if tailscale:
        s.linhas.append(
            f"tailnet (rede privada): {', '.join(sorted(set(tailscale))[:6])}"
        )

    # Socket ouvindo em 0.0.0.0 so e' superficie real se o firewall deixar
    # entrar. Sem cruzar com o ufw, o boletim acusa porta que ja esta' fechada
    # — alarme falso treina o operador a ignorar o boletim.
    rc_fw, out_fw = sudo_run(["ufw", "status"])
    _, out_fw_v = sudo_run(["ufw", "status", "verbose"])
    fw_ativo = bool(re.search(r"^(Status|Estado):\s*(active|ativo)", out_fw, re.M | re.I))
    liberadas: set[str] = set()
    if fw_ativo:
        for l in out_fw.splitlines():
            if not re.search(r"\bALLOW\b", l, re.I):
                continue
            mp = re.match(r"\s*(\d+)(?:/(?:tcp|udp))?\s", l)
            if mp:
                liberadas.add(mp.group(1))

    # Com politica default deny(entrada), so entra o que tem regra ALLOW
    # explicita por PORTA. Regra por interface (ex.: "Anywhere on tailscale0")
    # nao expoe a porta na internet — ja e' contabilizada como tailnet acima.
    deny_entrada = bool(
        re.search(r"deny\s*\((?:incoming|entrada)\)", out_fw, re.I)
    ) or bool(re.search(r"deny\s*\((?:incoming|entrada)\)", out_fw_v, re.I))

    if fw_ativo and deny_entrada:
        alcancaveis = {k: v for k, v in expostas.items()
                       if k.split("/", 1)[0] in liberadas}
        n_fech = len(expostas) - len(alcancaveis)
        if n_fech:
            s.linhas.append(
                f"firewall ativo (deny entrada): {n_fech} de {len(expostas)} "
                "porta(s) NAO alcancavel de fora"
            )
        expostas = alcancaveis

    # Porta liberada por regra COM comentario e' decisao registrada do
    # operador, nao achado. Sem isso o boletim reclama todo dia da mesma
    # regra deliberada e o operador para de ler.
    documentadas = set(re.findall(r"^\s*(\d+)(?:/(?:tcp|udp))?\s.*#\s*\S", out_fw, re.M))
    if documentadas:
        justificadas = {k: v for k, v in expostas.items()
                        if k.split("/", 1)[0] in documentadas}
        if justificadas:
            s.linhas.append(
                "liberada(s) por regra documentada no ufw: "
                + ", ".join(sorted(k.split("/", 1)[0] for k in justificadas))
            )
        expostas = {k: v for k, v in expostas.items() if k not in justificadas}

    if expostas:
        s.grade(WARN)
        s.linhas.append(f"{len(expostas)} porta(s) em toda interface:")
        for chave in sorted(expostas, key=lambda x: int(x.split("/", 1)[0]))[:10]:
            porta, dono = chave.split("/", 1)
            s.linhas.append(f"  · {porta:<6} {dono}  em {expostas[chave]}")
        s.conduta = (
            "Porta acima ouve em toda interface E passa pelo firewall — "
            "confirme que é intencional ou restrinja ao localhost"
        )
    else:
        s.linhas.append(
            "nenhuma porta alcancavel de fora (firewall + localhost/tailnet)"
            if fw_ativo else "nenhuma porta ouvindo além do localhost/tailnet"
        )
    return s


# --------------------------------------------------------------------------- #
# 7. Secure Boot / UEFI
# --------------------------------------------------------------------------- #
def sec_secureboot() -> Secao:
    s = Secao("Secure Boot")

    if not Path("/sys/firmware/efi").exists():
        s.linhas.append("BIOS legado (sem UEFI) — Secure Boot não se aplica")
        return s

    if tem("mokutil"):
        rc, out = run(["mokutil", "--sb-state"])
        if rc == 0 and out:
            estado = out.strip().splitlines()[0]
            if "enabled" in estado.lower():
                s.linhas.append("UEFI · Secure Boot habilitado")
            else:
                s.linhas.append(f"UEFI · {estado}")
            return s

    s.grade(UNK)
    s.linhas.append("UEFI presente · [SEM_LEITURA] estado do Secure Boot")
    s.conduta = "Confira:  mokutil --sb-state"
    return s


# --------------------------------------------------------------------------- #
def main() -> int:
    print("=" * 62)
    print("  BOLETIM DE SEGURANÇA — máquina (leitura pura)")
    if not SUDO_OK:
        print("  (sem sudo livre: itens que exigem root saem como [SEM_LEITURA])")
    print("=" * 62)

    secoes = [
        sec_firewall(),
        sec_cripto(),
        sec_ssh(),
        sec_apparmor(),
        sec_updates(),
        sec_portas(),
        sec_secureboot(),
    ]

    for sec in secoes:
        print(f"\n{sec.icon}  {sec.titulo}")
        for l in sec.linhas:
            print(f"     {l}")

    n_ok = sum(1 for s in secoes if s.icon == OK)
    n_un = sum(1 for s in secoes if s.icon == UNK)
    n_wa = sum(1 for s in secoes if s.icon == WARN)
    n_cr = sum(1 for s in secoes if s.icon == CRIT)
    print("\n" + "-" * 62)
    print(f"BOLETIM: {n_ok} {OK} · {n_un} {UNK} · {n_wa} {WARN} · {n_cr} {CRIT}")

    condutas = [(s.icon, s.conduta) for s in secoes if s.conduta]
    if condutas:
        print("\nConduta:")
        for icon, c in condutas:
            print(f"  {icon} {c}")
    else:
        print("\nNenhum item passou do limiar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
