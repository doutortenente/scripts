#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor v2: reorganiza por FEATURE (assunto-first), mata ~aprox.
Lê od_now.txt (snapshot atual). Gera rename_plan_v2.json + resumo.
Determinístico: heurística de keyword no nome/path decide a feature.
NÃO move nada. Marca REVISAR (genéricos a ler) e DUMP (código a preservar)."""

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

TMP = "/home/dr/.claude/jobs/afe98ad9/tmp"


def slug(s, n=60):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n].strip("-")


# ---- pacientes conhecidos (pra separar paciente de assunto) ----
known = set()
try:
    plan = json.load(open(f"{TMP}/rename_plan.json", encoding="utf-8"))
    known |= set(r["paciente"] for r in plan if r.get("paciente"))
except Exception:
    pass
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
    "JOAO BOSCO DE CASTRO NOGUEIRA",
    "LUIS ANTONIO BENEDITO",
    "SAULO CASTRO ALMEIDA",
    "IAN SERGIO DE SOUZA",
    "MATEUS ELIAS DE JESUS MELLO",
    "NEY AUGUSTO MELLO JUNIOR",
    "SERGIO BONSANGUE",
}
known_slugs = sorted(
    ((slug(k), k) for k in known if len(k) > 4), key=lambda x: -len(x[0])
)

# ---- 7 FEATURES → pasta destino ----
FEATURE_DIR = {
    "clinico": "Clinico",
    "militar": "Militar-FAB",
    "estudo": "Estudo",
    "dev": "Dev-IA",
    "financeiro": "Financeiro",
    "tese": "Tese-Mae",
    "pessoal": "Pessoal",
}
# tipos clínicos (categoria v1) que caem em Clínico
CLIN_CATS = {
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

# ---- heurística de RECLASSIFICAÇÃO por keyword (corrige mal-postos) ----
# ordem importa: primeira regra que casa vence
# KW rodam SÓ no nome do arquivo. NÃO incluir termos-categoria (cadastro/estudo/dev/pessoal)
# — categoria já é tratada no passo 5; senão captura cedo demais e atropela o path-context.
KW = [
    (
        "militar",
        r"eear|guarnae|funsa|aeronautic|avot|ssij|\bteme\b|salvamento|operacional-1\d{5}|caceres|efpu|guarni|comando-da-aeronautica|situacao-ausente",
    ),
    (
        "estudo",
        r"nejm|socesp|revista|lupus|psicose|guia-plantao|guia-de-plantao|terapia-intensiva|medicina-intensiva|residencia|diretriz|caderno|ecocardiog|arritmia|gasometria|ventilacao|sedacao|\bchoque\b|\bcoma\b|rebaixamento|paciente-grave|livro-professor|modulo|perfusao|dissec|aorta|hemodinamic|neurointens|distarbio|disturbio|bloqueio|\becg\b|coronar|anatomia|dor-toracic|hematolog|vasoativ|manejo|amib|sbpt|artigo|\baula\b|\bavc\b|protocolo|nejmra",
    ),
    ("tese", r"plac|doutorado|dissertacao|capitulo-livro"),
    (
        "dev",
        r"sasi|jarvis|grok|prompt|workflow|\bschema\b|pipeline|payload|\bskill\b|applet|ai-studio|dossie|refatorad|useclinical|readme|template-base|catalogo-sasi|manual-de-montagem|agentic",
    ),
    (
        "financeiro",
        r"ultragaz|\bccf\b|boleto|nota-fiscal|imposto|\bdarf\b|r-int-conv|pagamento|hostinger|fatura|recibo|comprovante|contrato|\bpix\b|extrato",
    ),
]
KW = [(f, re.compile(p)) for f, p in KW]
# PATH-context: sinal forte da PASTA (só pra genéricos/séries de foto). ordem importa.
PATH_CTX = [
    ("tese", r"projeto-mamae|projeto-mam"),
    (
        "estudo",
        r"gemini-gems|cadernos-e-estudos|ecocardiograma|projeto-educa-osa|ccp-1|trilha-8|curso-fgv|educa-osa|respostas|teste-0",
    ),
    (
        "militar",
        r"funsa|cepog|credenciado|visitas-credenciados|christovam|junta-saude|\bscl\b|educa-osa",
    ),
]
PATH_CTX = [(f, re.compile(p)) for f, p in PATH_CTX]
# genéricos = precisam leitura (não classificar às cegas)
GENERIC = re.compile(
    r"^(anexo-?[a-z]?|documento|doc\d+|scan-?\d*|\d{6,}|img-?\d+|image|paste|camera|whatsapp-image|processed|c[0-9a-f]{8}|[0-9a-f]{8}-[0-9a-f]{4}|arquivo-\d+|untitled|sem-titulo|copia-de)$"
)


def is_dump(path):
    """dump de código/projeto a preservar sem renomear item-a-item"""
    p = path.lower()
    return any(
        k in p
        for k in [
            "sasi_codigo_fonte",
            "sasi — arquivo de operação",
            "fase delta",
            "skills e docs claude",
            "google ai studio",
            "correcões sasi",
            "desing sasi",
            "prompts_e_workflows",
            "relatorios_e_resumos",
        ]
    )


def feature_of(cat, base_slug, path, tem_paciente):
    """decide feature. Precedência: paciente/keyword-do-NOME > path-context > cat-v1.
    cat=categoria v1 (pode ser None). retorna (feature, reclass_bool)."""
    top = path.split("/")[0]
    pslug = slug(path)
    # 1) Projeto Mamãe = tese, sempre
    if top.lower().startswith("projeto mamae") or top.lower().startswith("projeto mam"):
        return "tese", cat not in (None, "tese")
    # 2) nome de paciente no arquivo => clínico (a menos que já-clínico)
    if tem_paciente and cat not in CLIN_CATS:
        return "clinico", cat is not None
    # 3) keyword forte no NOME do arquivo (não no path — path-velho contamina)
    for f, rx in KW:
        if rx.search(base_slug):
            if cat in CLIN_CATS:
                break  # clínico com nome-paciente fica clínico
            return f, (cat is not None and _cat_feature(cat) != f)
    # 4) contexto forte da PASTA (pra genéricos e séries de foto)
    for f, rx in PATH_CTX:
        if rx.search(pslug):
            return f, (cat is not None and _cat_feature(cat) != f)
    # 5) categoria v1 embutida
    if cat:
        return _cat_feature(cat), False
    # 6) sem sinal
    return None, False


def _cat_feature(cat):
    if cat in CLIN_CATS:
        return "clinico"
    if cat in ("cadastro", "financ"):
        return "financeiro"
    if cat == "estudo":
        return "estudo"
    if cat in ("dev", "ia", "codigo", "src", "schema", "access", "refatorada"):
        return "dev"
    if cat == "pessoal":
        return "pessoal"
    return None


# ---- parse v1 + monta v2 ----
# assunto opcional: cobre tanto data_cat_assunto.ext quanto data_cat.ext (sem assunto)
V1 = re.compile(
    r"^(\d{4}-\d{2}-\d{2})(~aprox)?_([a-z]+)(?:_(.+?))?(\.[a-z0-9]+)?$", re.I
)

rows = []
for line in open(f"{TMP}/od_now.txt", encoding="utf-8"):
    line = line.rstrip("\n")
    if not line or "|" not in line:
        continue
    path, mt = line.rsplit("|", 1)
    mt = mt[:10]
    base = os.path.basename(path)
    if base in ("_INDEX.md", "_index.json"):
        continue
    ext = os.path.splitext(base)[1].lower()
    dump = is_dump(path)

    m = V1.match(base)
    if m:
        data_raw = m.group(1)
        aprox = bool(m.group(2))
        cat = m.group(3).lower()
        rest = m.group(4) or "documento"  # paciente-slug + assunto-slug juntos
        data = None if aprox else data_raw  # mata ~aprox: data estimada = descartada
    else:
        data = None
        cat = None
        rest = slug(os.path.splitext(base)[0])

    # separa paciente de assunto
    paciente = None
    assunto = rest
    for ks, kn in known_slugs:
        if rest.startswith(ks):
            paciente = kn
            assunto = rest[len(ks) :].strip("-_") or "documento"
            break
        if ("_" + ks) in ("_" + rest) and ks in rest:
            paciente = kn
            assunto = rest.replace(ks, "").strip("-_") or "documento"
            break
    assunto = slug(assunto, 50) or "documento"

    feature, reclass = feature_of(cat, slug(base), path, paciente is not None)
    generic = bool(GENERIC.match(assunto)) or assunto in ("documento", "")

    # genérico (img-XXXX) mas feature definida e pasta informativa → usa a PASTA como assunto
    BLACKLIST_DIRS = {"salvo-do-chrome", "google-drive"}
    if generic and feature not in (None, "?") and not dump:
        pp = [slug(x) for x in path.split("/")[1:-1]]
        pp = [x for x in pp if x and x not in BLACKLIST_DIRS]
        if pp:
            assunto = slug("-".join(pp), 55)
            generic = False

    if dump:
        feature = "dev"
        status = "DUMP"
    elif feature is None or feature == "?" or (generic and not paciente):
        status = "REVISAR"
        feature = feature or "?"
    else:
        status = "OK"

    # nome v2: <categoria>_<assunto>_<paciente?>_<data?>.ext  (assunto-first)
    cat_out = cat if cat else (feature if feature != "?" else "outros")
    parts = [cat_out, assunto]
    if paciente:
        parts.append(slug(paciente, 45))
    if data:
        parts.append(data)
    novo = "_".join(p for p in parts if p) + ext
    destino = (
        f"{FEATURE_DIR.get(feature,'_REVISAR')}/{novo}" if status != "DUMP" else None
    )

    rows.append(
        {
            "atual": path,
            "base": base,
            "feature": feature,
            "status": status,
            "cat": cat,
            "assunto": assunto,
            "paciente": paciente,
            "data": data,
            "reclass": reclass,
            "novo": novo,
            "destino": destino,
            "ext": ext,
            "mt": mt,
        }
    )

json.dump(
    rows,
    open(f"{TMP}/rename_plan_v2.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)

# ---- resumo ----
st = Counter(r["status"] for r in rows)
ft = Counter(r["feature"] for r in rows if r["status"] != "DUMP")
rc = sum(1 for r in rows if r["reclass"])
print(f"TOTAL {len(rows)} | status {dict(st)}")
print(f"reclassificados (mudaram de feature): {rc}")
print("por feature:", dict(ft.most_common()))
print(f"\n=== REVISAR (precisam leitura de conteúdo): {st['REVISAR']} ===")
for r in rows:
    if r["status"] == "REVISAR":
        print(f"  [{r['feature']:9s}] {r['atual']}")
