#!/usr/bin/env python3
"""Higiene do PC "Tijolão" — limpa lixo recuperável com segurança.

Só toca em alvos conhecidos (caches, backups, lixo regenerável). NUNCA faz
rm genérico. Mostra tudo antes (dry-run é o padrão); só apaga com --apply.

Uso:
    python3 pc_higiene.py                    # dry-run: só mostra o que faria
    python3 pc_higiene.py --apply            # executa a limpeza
    python3 pc_higiene.py --apply --grok     # também remove ~/.grok inteiro (Grok CLI)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()


def human(n: int) -> str:
    f = float(n)
    for u in ("B", "K", "M", "G", "T"):
        if f < 1024 or u == "T":
            return f"{f:.1f}{u}"
        f /= 1024
    return f"{f:.1f}T"


def size_of(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file() or p.is_symlink():
        try:
            return p.stat(follow_symlinks=False).st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda e: None):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    return total


def remove(p: Path, apply: bool) -> None:
    if p.is_dir() and not p.is_symlink():
        if apply:
            shutil.rmtree(p, ignore_errors=True)
    else:
        if apply:
            try:
                p.unlink()
            except OSError:
                pass


def glob_targets(base: Path, patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(base.glob(pat))
    return out


def run_cmd(cmd: list[str], apply: bool) -> str:
    """Roda comando externo (apt/flatpak). Em dry-run, só descreve."""
    if not apply:
        return f"(dry-run) rodaria: {' '.join(cmd)}"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        tail = (r.stdout or r.stderr or "").strip().splitlines()
        return tail[-1] if tail else "ok"
    except (subprocess.SubprocessError, OSError) as e:
        return f"falhou: {e}"


def sudo_ok() -> bool:
    """sudo sem senha disponível?"""
    try:
        return (
            subprocess.run(
                ["sudo", "-n", "true"], capture_output=True, timeout=5
            ).returncode
            == 0
        )
    except (subprocess.SubprocessError, OSError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Higiene do PC Tijolão")
    ap.add_argument(
        "--apply", action="store_true", help="executa (sem isso, só mostra)"
    )
    ap.add_argument(
        "--grok",
        action="store_true",
        help="remove ~/.grok inteiro (Grok CLI não usado)",
    )
    args = ap.parse_args()
    apply = args.apply

    print(
        f"{'APLICANDO' if apply else 'DRY-RUN (nada será apagado)'} — higiene do Tijolão\n"
    )

    # --- alvos de arquivo/dir (path, descrição) ---
    targets: list[tuple[Path, str]] = []

    # 1. Backups do JetBrains Toolbox (acumulam ao atualizar IDEs)
    tb = HOME / ".cache/JetBrains/Toolbox/backup"
    if tb.exists():
        targets.append((tb, "JetBrains Toolbox backups"))

    # 2. Caches do Grok (sempre lixo) ou Grok inteiro com --grok
    grok = HOME / ".grok"
    if grok.exists():
        if args.grok:
            targets.append((grok, "Grok CLI inteiro (~/.grok)"))
        else:
            for sub in ("downloads", "sessions", "marketplace-cache", "logs"):
                p = grok / sub
                if p.exists():
                    targets.append((p, f"Grok cache: {sub}"))

    # 3. Backups .bak soltos em ~/projetos e ~/.config (regeneráveis)
    for p in glob_targets(HOME / "dev", [".mcp.json.bak*", "**/*.bak-2026*"]):
        targets.append((p, f"backup órfão: {p.relative_to(HOME)}"))

    # 4. Caches de gerenciadores (pip / npm)
    for p in [HOME / ".cache/pip", HOME / ".npm/_cacache"]:
        if p.exists():
            targets.append((p, f"cache: {p.relative_to(HOME)}"))

    # dedup por caminho resolvido (globs podem sobrepor)
    seen: set[Path] = set()
    deduped: list[tuple[Path, str]] = []
    for p, desc in targets:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        deduped.append((p, desc))
    targets = deduped

    # --- executa alvos de arquivo ---
    freed = 0
    for p, desc in targets:
        s = size_of(p)
        freed += s
        print(f"  [{human(s):>8}]  {desc}")
        remove(p, apply)
    if not targets:
        print("  (nenhum alvo de arquivo encontrado)")

    print(f"\n  >> espaço {'liberado' if apply else 'a liberar'}: {human(freed)}\n")

    # --- comandos de sistema ---
    print("Pacotes do sistema:")
    if sudo_ok():
        print(
            "  apt autoremove:",
            run_cmd(["sudo", "-n", "apt-get", "autoremove", "-y"], apply),
        )
        print("  apt clean:     ", run_cmd(["sudo", "-n", "apt-get", "clean"], apply))
    else:
        print(
            "  apt: pulado (sudo exige senha — rode manual: sudo apt autoremove && sudo apt clean)"
        )
    if shutil.which("flatpak"):
        print(
            "  flatpak unused:",
            run_cmd(["flatpak", "uninstall", "--unused", "-y"], apply),
        )

    if not apply:
        print("\nNada foi apagado. Releia a lista e rode com --apply para executar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
