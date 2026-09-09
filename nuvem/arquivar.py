#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arquiva um documento no OneDrive (camada "banco de documentos"), convenção v2.

Guarda um arquivo do PC na nuvem OneDrive seguindo a convenção travada 03-jul-2026:
nome = `categoria_assunto[_paciente][_AAAA-MM-DD].ext`, dentro de 1 das 7 pastas-feature
em `onedrive:Documentos-claude-e-importacao-drive/` (Clinico · Militar-FAB · Estudo · Dev-IA · Financeiro ·
Tese-Mae · Pessoal). A data NUNCA é estimada — sem --data, o nome não leva data
(zero alucinação; o ~aprox foi abolido).

Padrão da casa: default é DRY-RUN (só mostra "DE -> PARA"); --apply é que copia.
No --apply confere a integridade por hash (QuickXor) local × remoto; só remove o
local (--rm-local) se o hash bater. stdlib pura — chama o rclone via subprocess.

Uso:
    python3 arquivar.py <arquivo> --feature Clinico --categoria laudo --assunto tc-cranio \\
        [--paciente "NOME COMPLETO"] [--data AAAA-MM-DD] [--rm-local] [--apply]

    # dry-run (padrão): mostra o destino e sai, nada é copiado
    python3 arquivar.py laudo.pdf --feature Clinico --categoria laudo --assunto tc-cranio
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

RCLONE = Path.home() / ".local/bin/rclone"
BASE = "onedrive:Documentos-claude-e-importacao-drive"

# 7 features -> nome canônico da pasta (entrada é case-insensitive / sem acento)
FEATURES = {
    "clinico": "Clinico",
    "militar-fab": "Militar-FAB",
    "estudo": "Estudo",
    "dev-ia": "Dev-IA",
    "financeiro": "Financeiro",
    "tese-mae": "Tese-Mae",
    "pessoal": "Pessoal",
}

# categorias válidas (1º campo do nome)
CATEGORIAS = {
    "evolucao",
    "admissao",
    "prontuario",
    "passagem",
    "censo",
    "exame",
    "laudo",
    "auditoria",
    "altocusto",
    "solicitacao",
    "receita",
    "estudo",
    "dev",
    "ia",
    "codigo",
    "financ",
    "cadastro",
    "modelo",
    "pessoal",
}

# chars que quebram o sync do OneDrive/rclone
PROIBIDOS = re.compile(r'[/\\:?*"<>|]')


def slug(s: str, limite: int = 60) -> str:
    """minúsculo, sem acento, espaços->'-', tira chars que quebram sync."""
    s = PROIBIDOS.sub(" ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:limite].strip("-")


def norm_feature(v: str) -> str:
    """normaliza a entrada da feature (sem acento, minúsculo) pra bater na chave."""
    v = unicodedata.normalize("NFKD", v)
    v = "".join(c for c in v if not unicodedata.combining(c))
    return v.lower().strip()


def valida_data(v: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError(f"data '{v}' fora do formato AAAA-MM-DD")
    try:
        dt.date.fromisoformat(v)
    except ValueError:
        raise ValueError(f"data '{v}' não é uma data válida")
    return v


def rclone(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(RCLONE), *args], capture_output=True, text=True, timeout=timeout
    )


def hash_quickxor(alvo: str, timeout: int = 180) -> str | None:
    """Retorna o QuickXorHash do alvo (local ou remoto), ou None se falhar."""
    r = rclone(["hashsum", "quickxor", alvo], timeout=timeout)
    if r.returncode != 0:
        return None
    linha = r.stdout.strip().splitlines()
    if not linha:
        return None
    return linha[0].split()[0]  # "HASH  nome" -> HASH


def erro(msg: str) -> int:
    print(f"🔴 ERRO: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Arquiva um documento no OneDrive (convenção v2, dry-run por padrão)",
    )
    ap.add_argument("arquivo", help="arquivo local a arquivar")
    ap.add_argument(
        "--feature",
        required=True,
        help="pasta-feature: " + " · ".join(FEATURES.values()),
    )
    ap.add_argument("--categoria", required=True, help="categoria (1º campo do nome)")
    ap.add_argument("--assunto", required=True, help="assunto curto (será slugificado)")
    ap.add_argument("--paciente", help="nome completo do paciente (opcional)")
    ap.add_argument("--data", help="data real AAAA-MM-DD (opcional; NUNCA estimada)")
    ap.add_argument(
        "--rm-local", action="store_true", help="remove o local após hash conferir"
    )
    ap.add_argument(
        "--apply", action="store_true", help="executa a cópia (sem isso, só mostra)"
    )
    args = ap.parse_args()

    # --- validações ---
    src = Path(args.arquivo).expanduser()
    if not src.is_file():
        return erro(f"arquivo não encontrado: {src}")

    feat_key = norm_feature(args.feature)
    if feat_key not in FEATURES:
        return erro(
            f"feature inválida: '{args.feature}'. Válidas: {', '.join(FEATURES.values())}"
        )
    feature = FEATURES[feat_key]

    categoria = args.categoria.lower().strip()
    if categoria not in CATEGORIAS:
        return erro(
            f"categoria inválida: '{args.categoria}'. Válidas: {', '.join(sorted(CATEGORIAS))}"
        )

    data = None
    if args.data:
        try:
            data = valida_data(args.data)
        except ValueError as e:
            return erro(str(e))

    assunto = slug(args.assunto, 50)
    if not assunto:
        return erro("assunto vazio após slugificar")

    # --- monta o nome final: categoria_assunto[_paciente][_data].ext ---
    ext = src.suffix.lower()
    partes = [categoria, assunto]
    if args.paciente:
        pac = slug(args.paciente, 45)
        if pac:
            partes.append(pac)
    if data:
        partes.append(data)
    nome = "_".join(partes) + ext
    destino = f"{BASE}/{feature}/{nome}"

    # --- dry-run (padrão) ---
    print("ARQUIVAR — OneDrive (convenção v2)")
    print(f"  DE:   {src}")
    print(f"  PARA: {destino}")
    if not args.apply:
        print("\n(dry-run — nada foi copiado. Adicione --apply para executar.)")
        return 0

    # --- apply: copia + confere hash ---
    if not RCLONE.exists():
        return erro(f"rclone não encontrado em {RCLONE}")
    print("\n  copiando...")
    cp = rclone(["copyto", str(src), destino])
    if cp.returncode != 0:
        return erro(f"rclone copyto falhou: {(cp.stderr or cp.stdout).strip()}")

    print("  conferindo integridade (QuickXor local × remoto)...")
    h_local = hash_quickxor(str(src))
    h_remoto = hash_quickxor(destino)
    if not h_local or not h_remoto:
        print("🔴 não consegui calcular o hash dos dois lados — local PRESERVADO.")
        return 1
    if h_local != h_remoto:
        print(
            f"🔴 HASH DIVERGE (local {h_local[:12]}… ≠ remoto {h_remoto[:12]}…) — local PRESERVADO, confira."
        )
        return 1

    print(f"  ✅ hash confere ({h_local[:12]}…) — cópia íntegra.")
    if args.rm_local:
        try:
            src.unlink()
            print(f"  ✅ local removido: {src}")
        except OSError as e:
            print(f"  ⚠️ não removi o local ({e}) — remova à mão se quiser.")

    print(f"\nArquivado em  {feature}/{nome}")
    print(
        "Lembrete: catálogo desatualizado — rode  regen_index_v2.py  quando fechar o lote."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
