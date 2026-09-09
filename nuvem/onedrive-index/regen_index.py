#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera _index.json + _INDEX.md a partir do ESTADO ATUAL do OneDrive (fonte da verdade).
Categoria/data são lidas do próprio nome (auto-descritivo); paciente por casamento com nomes conhecidos.
"""

import datetime
import json
import os
import re
import subprocess
import unicodedata

RC = os.path.expanduser("~/.local/bin/rclone")
BASE = "onedrive:Documentos-claude-e-importacao-drive"
HOJE = datetime.date.today().isoformat()
TMP = os.path.dirname(os.path.abspath(__file__))


def slug(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# lista atual
out = subprocess.run(
    [RC, "lsf", BASE, "-R", "--files-only", "--format", "pt", "--separator", "|"],
    capture_output=True,
    text=True,
    timeout=180,
).stdout
files = []
for l in out.splitlines():
    if not l.strip() or l.startswith("_INDEX") or l.startswith("_index"):
        continue
    p = l.rsplit("|", 1)
    path = p[0]
    mt = p[1][:10] if len(p) > 1 else ""
    files.append((path, mt))

# pacientes conhecidos (do plano + os identificados manualmente no Revisar)
plan = json.load(open(f"{TMP}/rename_plan.json", encoding="utf-8"))
known = set(r["paciente"] for r in plan if r["paciente"])
known |= {
    "RENATA CRISTINA DE SIQUEIRA BARBOSA DO NASCIMENTO",
    "WALTER OLIVEIRA DA SILVA",
    "PAULO VITOR DIAS",
    "VANESSA VEGA DA SILVA ROSA",
    "BENEDITO AUGUSTO MARCONDES",
    "IVAN LUIZ DE CASTRO NOBRE",
    "LAERTE GONCALVES PEREIRA",
    "MARIA ROSARIA URBANO GOMES",
    "MARLON RONALDO DE CAMPOS",
    "MINERVINA MARIA DA SILVA CRUZ",
    "NEUZA COUTO DE MOURA",
    "TEREZA FERRAZ DE CAMPOS SILVA",
    "ANNITO CHEQUER NOVAES NETO",
    "ELENICE",
    "JOAO BOSCO DE CASTRO NOGUEIRA",
    "LUIS ANTONIO BENEDITO",
    "SAULO CASTRO ALMEIDA",
    "IAN SERGIO DE SOUZA",
    "MATEUS ELIAS DE JESUS MELLO",
    "NEY AUGUSTO MELLO JUNIOR",
    "MARCELO",
    "ROBERTA",
    "SERGIO BONSANGUE",
}
known_slugs = {slug(k): k for k in known if len(k) > 4}

PHI = {
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
CATLBL = {
    "prontuario": "Prontuário",
    "evolucao": "Evolução",
    "admissao": "Admissão",
    "exame": "Exame",
    "laudo": "Laudo/Relatório",
    "altocusto": "Alto custo",
    "passagem": "Passagem/Censo",
    "censo": "Censo",
    "solicitacao": "Solicitação",
    "receita": "Receita",
    "auditoria": "Auditoria",
    "cadastro": "Cadastro/Documento",
    "financ": "Financeiro",
    "estudo": "Estudo",
    "dev": "Dev/Código",
    "ia": "IA/Prompts",
    "pessoal": "Pessoal",
    "outros": "Outros (não indexado)",
}
FOLDER_CAT = {
    "Clinico": "prontuario",
    "Cadastro e Financeiro": "cadastro",
    "Estudo": "estudo",
    "Dev e IA": "dev",
    "Pessoal": "pessoal",
}

from collections import Counter, defaultdict

arquivos = []
pac = defaultdict(list)
cat_c = Counter()
folder_c = Counter()
for path, mt in files:
    base = os.path.basename(path)
    top = path.split("/")[0]
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(~aprox)?_([a-z]+)_", base)
    if m:
        data = m.group(1)
        aprox = bool(m.group(2))
        cat = m.group(3)
    else:
        data = mt or "?"
        aprox = True
        cat = FOLDER_CAT.get(top, "outros")
    if cat not in CATLBL:
        cat = "outros"
    # paciente por casamento
    bslug = slug(base)
    paciente = None
    for ks, kn in known_slugs.items():
        if ks in bslug:
            paciente = kn
            break
    rec = {
        "path": path,
        "categoria": cat,
        "data": data,
        "aprox": aprox,
        "paciente": paciente,
        "phi": cat in PHI,
    }
    arquivos.append(rec)
    cat_c[cat] += 1
    folder_c[top] += 1
    if paciente:
        pac[paciente].append(base)

arquivos.sort(key=lambda x: (x["categoria"], x["data"]))
datas = [a["data"] for a in arquivos if re.match(r"20\d{2}-\d{2}-\d{2}", a["data"])]
faixa = (min(datas), max(datas)) if datas else ("?", "?")

ij = {
    "gerado": HOJE,
    "raiz_onedrive": "Documentos-claude-e-importacao-drive",
    "total_arquivos": len(arquivos),
    "faixa_datas": {"de": faixa[0], "ate": faixa[1]},
    "categorias": dict(cat_c.most_common()),
    "convencao_nome": "AAAA-MM-DD_categoria_[paciente_]assunto.ext ; ~aprox = data estimada (modtime)",
    "phi": "phi=true contém nome de paciente. Pastas clínicas = PHI.",
    "nota": "Originais no Google Drive (backup). appsheet apagada. 00_Revisar tem só vazios+lixo Adobe.",
    "arquivos": arquivos,
}
json.dump(
    ij, open(f"{TMP}/_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)

L = [
    f"# Arquivo de documentos — Dr. Nicolas Nagaita",
    f"> Catálogo agente-first · organizado {HOJE} (migração Google Drive → OneDrive).",
    f"> **{len(arquivos)} arquivos** · período {faixa[0]}–{faixa[1]} · raiz `OneDrive:/Documentos-claude-e-importacao-drive/`.\n",
    "## Como usar (IA e humano)",
    "- O nome já é o índice: `AAAA-MM-DD_categoria_[paciente_]assunto.ext`. Data na frente ordena sozinho.",
    "- `~aprox` = data estimada pela data de modificação (nunca inventada).",
    "- `_index.json` = índice-máquina: todo arquivo com categoria/data/paciente/phi.",
    "- 🔴 PHI: pastas clínicas têm nome completo de paciente.",
    "- Originais no Google Drive (backup). `00_Revisar/` = só vazios + 1 lixo do Adobe.\n",
    "## Categorias",
    "| Categoria | Arquivos | PHI |",
    "|---|---|---|",
]
for c, n in cat_c.most_common():
    L.append(f"| {CATLBL.get(c,c)} (`{c}`) | {n} | {'🔴' if c in PHI else ''} |")
L += [f"\n## Pastas (nível 1)", "| Pasta | Arquivos |", "|---|---|"]
for f, n in sorted(folder_c.items(), key=lambda x: -x[1])[:20]:
    L.append(f"| `{f}/` | {n} |")
L += [
    f"\n## Índice de pacientes ({len(pac)})",
    "> Nome → arquivos. Só os que o conteúdo/nome revelou (zero alucinação).\n",
]
for nome in sorted(pac):
    fs = pac[nome]
    L.append(
        f"- **{nome}** ({len(fs)}): "
        + " · ".join(f"`{x}`" for x in fs[:5])
        + (" …" if len(fs) > 5 else "")
    )
open(f"{TMP}/_INDEX.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print(
    f"total {len(arquivos)} | categorias {len(cat_c)} | pacientes {len(pac)} | período {faixa}"
)
print("por categoria:", dict(cat_c.most_common()))
