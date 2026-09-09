#!/usr/bin/env python3
"""Indexa o repo Claude → memory/claude_index.db + MAPA-CLAUDE.md + SKILLS-CATALOGO.md.

Uso (raiz do repo): python3 ~/projetos/scripts/indices/build_claude_index.py
"""

import datetime
import hashlib
import os
import re
import sqlite3

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = os.path.join(DEV, "claude")
DB = os.path.join(ROOT, "memory", "claude_index.db")
MAPA = os.path.join(ROOT, "memory", "MAPA-CLAUDE.md")
CATALOGO = os.path.join(ROOT, "memory", "SKILLS-CATALOGO.md")

# `ide/` e `.agentbridge/` NUNCA entram: os .lock da IDE carregam authToken em
# texto puro e cairiam no FTS do índice. `.idea/` e worktrees são ruído local.
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "ide",
    ".agentbridge",
    ".idea",
    "worktrees",
}
SKIP_FILES = {"claude_index.db", "claude_index.db.bak"}
BLOB_EXT = {
    ".csv",
    ".xsd",
    ".ttf",
    ".woff",
    ".woff2",
    ".png",
    ".jpg",
    ".gif",
    ".webp",
    ".pdf",
}
SCRIPT_EXT = {".py", ".sh", ".js", ".cjs", ".mjs"}
TEXT_EXT = {
    ".md",
    ".json",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".html",
    ".css",
    ".xml",
    ".py",
    ".sh",
    ".js",
    ".cjs",
    ".mjs",
    ".dot",
    ".ts",
    ".tsx",
}

CAT_LABELS = {
    "skill_ide": "Pacote 00 — IDE e documentação",
    "skill_clinical": "Pacote 01 — skills médicas (UTI)",
    "skill_workspace": "Pacote 02 — workspace (docx, pdf, xlsx…)",
    "skill_dev": "Pacote 03 — nativas do Claude (skill-creator, TDD…)",
    "skill_backend": "Pacote 04 — Supabase e Vercel",
    "script": "Scripts que são o corpo de uma skill",
    "agent": "Subagentes — `agents/<nome>/`",
    "governance": "`.claude/` — rules, skills, agents, hooks, settings",
    "docs": "`docs/` — manual, inventário, decisões, runbook",
    "memory": "`memory/` — este índice",
    "extracao": "`EXTRACAO-CLINICA-SASI/` — briefing + atalhos",
    "vendor_blob": "Binários/pesados (só path, sem FTS)",
    "root": "CLAUDE.md, README, .gitignore, .env.example",
    "other": "Revisar",
}

# Pacote temático → categoria do índice.
PACOTES = {
    "00-pacote-ide-e-documentacao": "skill_ide",
    "01-pacote-skills-medicas": "skill_clinical",
    "02-pacote-skills-workspace": "skill_workspace",
    "03-pacote-skills-claude-nativas": "skill_dev",
    "04-pacote-skills-supabase-e-vercel": "skill_backend",
}


def categorize(rel, name):
    p = rel.replace("\\", "/")
    ext = os.path.splitext(name)[1].lower()
    if ext in BLOB_EXT or "/data/" in p and ext == ".csv":
        return "vendor_blob"
    if p.startswith(".claude/"):
        return "governance"
    if p.startswith("agents/"):
        return "agent"
    if p.startswith("docs/"):
        return "docs"
    if p.startswith("memory/"):
        return "memory"
    if p.startswith("EXTRACAO-CLINICA-SASI/"):
        return "extracao"
    if p.startswith("skills-que-prestam/"):
        # Script que É o corpo de uma skill tem categoria própria — é o que
        # `query_claude_index.py scripts` lista.
        if ext in SCRIPT_EXT:
            return "script"
        partes = p.split("/")
        if len(partes) > 1:
            return PACOTES.get(partes[1], "other")
        return "other"
    if "/" not in p:
        return "root"
    return "other"


def parse_skill_frontmatter(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read(8000)
    except OSError:
        return None, None
    if not text.startswith("---"):
        return None, None
    end = text.find("\n---", 3)
    if end < 0:
        return None, None
    fm = text[3:end]
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    n = name.group(1).strip().strip("'\"") if name else None
    d = desc.group(1).strip().strip("'\"") if desc else None
    if d and d.startswith(">"):
        d = d[1:].strip()
    return n, d


def is_text(path, ext):
    if ext in TEXT_EXT:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
        return b"\x00" not in chunk
    except OSError:
        return False


def read_metrics(path, max_bytes=500_000):
    try:
        with open(path, "rb") as f:
            raw = f.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None, None, None, None, None
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        return lines, len(text), len(text.split()), digest, text
    except OSError:
        return None, None, None, None, None


def scan():
    rows, fts, skills = [], [], []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in sorted(dirnames) if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            ext = os.path.splitext(fn)[1].lower() or (
                fn.lower() if fn.startswith(".") else ""
            )
            cat = categorize(rel, fn)
            txt = is_text(full, ext) and cat != "vendor_blob"
            lines = chars = tokens = digest = content = None
            if txt and st.st_size < 500_000:
                lines, chars, tokens, digest, content = read_metrics(full)
            reldir = os.path.dirname(rel) or "."
            rows.append(
                (
                    rel,
                    reldir,
                    fn,
                    ext,
                    st.st_size,
                    lines,
                    chars,
                    tokens,
                    digest,
                    int(txt or cat == "vendor_blob"),
                    cat,
                    datetime.datetime.fromtimestamp(st.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                )
            )
            if content and cat not in ("vendor_blob",):
                fts.append((rel, content))
            if fn == "SKILL.md":
                name, desc = parse_skill_frontmatter(full)
                if name:
                    skills.append((name, desc or "", rel, cat, tokens or 0))
    return rows, fts, skills


def build_db(rows, fts_rows, skills):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    bak = DB + ".bak"
    if os.path.exists(DB):
        os.rename(DB, bak)
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.execute("""create table files(
      id integer primary key, path text unique, dir text, name text, ext text,
      size_bytes integer, lines integer, chars integer, tokens integer,
      sha256 text, is_text integer, category text, mtime text)""")
    c.executemany(
        "insert into files(path,dir,name,ext,size_bytes,lines,chars,tokens,sha256,is_text,category,mtime) "
        "values(?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    c.execute(
        """create table skills(
      name text primary key, description text, path text, category text, tokens integer)"""
    )
    c.executemany(
        "insert or replace into skills(name,description,path,category,tokens) values(?,?,?,?,?)",
        skills,
    )
    c.execute(
        "create view categorias as select category, count(*) arquivos, sum(size_bytes) bytes, "
        "sum(coalesce(lines,0)) linhas, sum(coalesce(tokens,0)) tokens "
        "from files group by category order by sum(coalesce(tokens,0)) desc"
    )
    c.execute("create index idx_files_cat on files(category)")
    c.execute("create index idx_files_path on files(path)")
    c.execute(
        "create virtual table files_fts using fts5(path, content, tokenize='unicode61')"
    )
    c.executemany("insert into files_fts(path, content) values(?,?)", fts_rows)
    if os.path.exists(bak):
        os.remove(bak)
    con.commit()
    return con, c


def write_catalogo(c, today):
    lines = [
        "# Catálogo de Skills — Claude",
        "",
        f"> Gerado {today} · **leia isto antes de varrer `skills/` com Read/Glob.**",
        "> Regenerar: `python3 ~/projetos/scripts/indices/build_claude_index.py`",
        "",
        "## Clínicas (UTI)",
        "",
    ]
    for name, desc, path, cat, _ in c.execute(
        "select name, description, path, category, tokens from skills where category='skill_clinical' order by name"
    ):
        lines.append(f"- **{name}** — `{path}`")
        if desc:
            lines.append(f"  {desc[:200]}{'…' if len(desc) > 200 else ''}")

    lines += ["", "## Desenvolvimento (superpowers)", ""]
    for name, desc, path, cat, _ in c.execute(
        "select name, description, path, category, tokens from skills where category='skill_dev' order by name"
    ):
        lines.append(f"- **{name}** — `{path}`")
        if desc:
            lines.append(f"  {desc[:160]}{'…' if len(desc) > 160 else ''}")

    lines += ["", "## Design (`_design/` — carregar sob demanda)", ""]
    for name, desc, path, cat, _ in c.execute(
        "select name, description, path, category, tokens from skills where category='skill_design' order by name"
    ):
        lines.append(f"- **{name}** — `{path}`")

    lines += ["", "## Anthropic (`_anthropic/` — sob demanda)", ""]
    for name, desc, path, cat, _ in c.execute(
        "select name, description, path, category, tokens from skills where category='skill_anthropic' order by name"
    ):
        lines.append(f"- **{name}** — `{path}`")

    lines += [
        "",
        "## Consulta rápida",
        "",
        "```bash",
        "python3 ~/projetos/scripts/indices/query_claude_index.py skills",
        "python3 ~/projetos/scripts/indices/query_claude_index.py skill sasi-ingest-export",
        "python3 ~/projetos/scripts/indices/query_claude_index.py scripts",
        "python3 ~/projetos/scripts/indices/query_claude_index.py search zero alucinação",
        "```",
    ]
    with open(CATALOGO, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_mapa(c, today):
    tot = c.execute(
        "select count(*), sum(size_bytes), sum(coalesce(lines,0)), sum(coalesce(tokens,0)) from files"
    ).fetchone()
    n_skills = c.execute("select count(*) from skills").fetchone()[0]
    cats = c.execute("select * from categorias").fetchall()
    top = c.execute(
        "select path, tokens, category from files where tokens is not null "
        "and category not in ('vendor_blob') order by tokens desc limit 12"
    ).fetchall()

    lines = [
        "# MAPA — repo Claude",
        "",
        f"> Gerado {today} por `~/projetos/scripts/indices/build_claude_index.py`",
        "",
        f"**Total:** {tot[0]} arquivos · {tot[1]/1024/1024:.1f} MB · {tot[2]:,} linhas · "
        f"{tot[3]:,} tokens indexados · **{n_skills} skills**",
        "",
        "## Por categoria",
        "",
        "| Categoria | Arq | Tokens | O que é |",
        "|---|---:|---:|---|",
    ]
    for cat, n, _b, _l, t in cats:
        lines.append(f"| `{cat}` | {n} | {t or 0:,} | {CAT_LABELS.get(cat, cat)} |")

    lines += ["", "## Maiores arquivos (exceto vendor_blob)", ""]
    for path, tok, cat in top:
        lines.append(f"- `{path}` — {tok:,} tok (`{cat}`)")

    lines += [
        "",
        "## Navegação rápida (obrigatório para agentes)",
        "",
        "1. **Skills** → `memory/SKILLS-CATALOGO.md` ou `query_claude_index.py skills`",
        "2. **Scripts** → `query_claude_index.py scripts`",
        "3. **Busca** → `query_claude_index.py search <termo>` (FTS5)",
        "4. **Só então** → `Read` no path exato retornado",
        "",
        "Não usar `Glob **/skills/**` nem ler `_design/`/`_anthropic/` sem necessidade.",
        "",
        "```bash",
        "python3 ~/projetos/scripts/indices/query_claude_index.py skills --clinical",
        "python3 ~/projetos/scripts/indices/query_claude_index.py find engine.py",
        "python3 ~/projetos/scripts/indices/query_claude_index.py agents",
        "```",
    ]
    with open(MAPA, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    today = datetime.date.today().strftime("%d-%b-%Y").lower()
    rows, fts, skills = scan()
    con, c = build_db(rows, fts, skills)
    write_mapa(c, today)
    write_catalogo(c, today)
    n = c.execute("select count(*) from files").fetchone()[0]
    ns = c.execute("select count(*) from skills").fetchone()[0]
    print(f"DB: {DB}")
    print(f"files: {n} | skills: {ns} | FTS: {len(fts)}")
    print(f"MAPA: {MAPA}")
    print(f"CATALOGO: {CATALOGO}")
    con.close()
    print("OK")


if __name__ == "__main__":
    main()
