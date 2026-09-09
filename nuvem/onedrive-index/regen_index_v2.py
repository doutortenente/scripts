#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera _INDEX.md + _index.json v2 (eixo por FEATURE/assunto, sem ~aprox).
Fonte da verdade = estado REAL do OneDrive (lsf). Enriquece paciente/phi cruzando com o plano.
"""

import json
import os
import re
import subprocess
from collections import Counter, defaultdict

RC = os.path.expanduser("~/.local/bin/rclone")
BASE = "onedrive:Documentos-claude-e-importacao-drive"
HOJE = "2026-07-05"
TMP = os.path.expanduser(
    "~/projetos/scripts/nuvem/onedrive-index"
)  # casa definitiva (job dir evapora)

# estado real
out = subprocess.run(
    [RC, "lsf", BASE, "-R", "--files-only", "--format", "pt", "--separator", "|"],
    capture_output=True,
    text=True,
    timeout=180,
).stdout
# plano: destino -> (paciente, phi, cat)
plan = json.load(open(f"{TMP}/rename_plan_v2.json", encoding="utf-8"))
PHI_CATS = {
    "prontuario",
    "exame",
    "laudo",
    "altocusto",
    "admissao",
    "evolucao",
    "passagem",
    "censo",
    "solicitacao",
    "receita",
    "auditoria",
}
byd = {}
for r in plan:
    if r["status"] == "OK":
        byd[r["destino"]] = (
            r.get("paciente"),
            r.get("phi_manual", r.get("cat") in PHI_CATS),
        )

FLABEL = {
    "Clinico": "Clínico",
    "Militar-FAB": "Militar-FAB",
    "Estudo": "Estudo",
    "Dev-IA": "Dev-IA",
    "Financeiro": "Financeiro",
    "Tese-Mae": "Tese-Mãe",
    "Pessoal": "Pessoal",
    "Passagem-de-turno": "Passagem de turno",
    "evolucoes-sasi-claude": "Evoluções SASI (Claude)",
}
CATLBL = {
    "prontuario": "Prontuário",
    "evolucao": "Evolução",
    "admissao": "Admissão",
    "exame": "Exame",
    "laudo": "Laudo/Relatório",
    "altocusto": "Alto custo",
    "passagem": "Passagem",
    "censo": "Censo",
    "solicitacao": "Solicitação",
    "receita": "Receita/Atestado",
    "auditoria": "Auditoria",
    "cadastro": "Cadastro/Doc",
    "financ": "Financeiro",
    "estudo": "Estudo",
    "dev": "Dev/Código",
    "ia": "IA/Prompts",
    "codigo": "Código",
    "modelo": "Modelo/Template",
    "pessoal": "Pessoal",
    "schema": "Schema",
    "src": "Código",
}

arquivos = []
pac = defaultdict(list)
featc = Counter()
catc = Counter()
DATE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.[a-z0-9]+$", re.I)
for l in out.splitlines():
    if not l.strip() or "|" not in l:
        continue
    path, mt = l.rsplit("|", 1)
    mt = mt[:10]
    base = os.path.basename(path)
    if base in ("_INDEX.md", "_index.json"):
        continue
    top = path.split("/")[0]
    feature = top if top in FLABEL else "Outros"
    # categoria = 1º token do nome; data = AAAA-MM-DD no fim (só real)
    cat = base.split("_", 1)[0].lower() if "_" in base else "outros"
    if cat not in CATLBL:
        cat = "dev" if feature == "Dev-IA" else "outros"
    dm = DATE.search(base)
    data = dm.group(1) if dm else None
    paciente, phi = byd.get(path, (None, cat in PHI_CATS))
    rec = {
        "path": path,
        "feature": feature,
        "categoria": cat,
        "assunto": None,
        "data": data,
        "paciente": paciente,
        "phi": bool(phi),
    }
    arquivos.append(rec)
    featc[feature] += 1
    catc[cat] += 1
    if paciente:
        pac[paciente].append(base)

arquivos.sort(key=lambda x: (x["feature"], x["categoria"], x["path"]))
datas = [a["data"] for a in arquivos if a["data"]]
faixa = (min(datas), max(datas)) if datas else ("?", "?")

ij = {
    "gerado": HOJE,
    "raiz": "OneDrive:/Documentos-claude-e-importacao-drive",
    "total": len(arquivos),
    "eixo": "feature (assunto), não data",
    "convencao_nome": "categoria_assunto[_paciente][_AAAA-MM-DD].ext — data só quando real (sem estimativa)",
    "features": dict(featc.most_common()),
    "categorias": dict(catc.most_common()),
    "phi": "phi=true contém nome de paciente (pastas clínicas).",
    "nota": "Reorganizado por feature em 2026-07-03. Originais no Google Drive (backup). 48 dumps de código em Dev-IA/_codigo-backup/.",
    "faixa_datas": {"de": faixa[0], "ate": faixa[1]},
    "arquivos": arquivos,
}
json.dump(
    ij, open(f"{TMP}/_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)

L = [
    f"# Arquivo de documentos — Dr. Nicolas Nagaita",
    f"> Catálogo agente-first · reorganizado {HOJE} **por feature** (o que o documento é, não a data).",
    f"> **{len(arquivos)} arquivos** em {len(featc)} features · datas reais {faixa[0]}–{faixa[1]} · raiz `OneDrive:/Documentos-claude-e-importacao-drive/`.\n",
    "## Como usar (IA e humano)",
    "- Cada arquivo é agrupado por **feature** (pasta) e nomeado `categoria_assunto[_paciente][_data].ext`.",
    "- A **data só aparece quando é real** — nada de estimativa. Ordenação natural = por assunto, não por tempo.",
    "- `_index.json` = índice-máquina: todo arquivo com feature/categoria/data/paciente/phi.",
    "- 🔴 PHI: arquivos clínicos têm nome completo de paciente.",
    "- Dumps de código em `Dev-IA/_codigo-backup/` (o código canônico vive no GitHub).",
    "- Originais no Google Drive como backup.\n",
    "## Features (pastas nível 1)",
    "| Feature | Arquivos |",
    "|---|---|",
]
for f, n in featc.most_common():
    L.append(f"| **{FLABEL.get(f,f)}** (`{f}/`) | {n} |")
L += [
    "\n## Categorias (tipo de documento)",
    "| Categoria | Arquivos | PHI |",
    "|---|---|---|",
]
for c, n in catc.most_common():
    L.append(f"| {CATLBL.get(c,c)} (`{c}`) | {n} | {'🔴' if c in PHI_CATS else ''} |")
L += [
    f"\n## Índice de pacientes ({len(pac)})",
    "> Nome → arquivos. Só os que o conteúdo/nome revelou (zero alucinação).\n",
]
for nome in sorted(pac):
    fs = pac[nome]
    L.append(
        f"- **{nome}** ({len(fs)}): "
        + " · ".join(f"`{x}`" for x in fs[:4])
        + (" …" if len(fs) > 4 else "")
    )
open(f"{TMP}/_INDEX.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"total {len(arquivos)} | features {dict(featc.most_common())}")
print(
    f"pacientes {len(pac)} | período {faixa} | PHI {sum(1 for a in arquivos if a['phi'])}"
)
