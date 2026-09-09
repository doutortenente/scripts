#!/usr/bin/env python3
"""Indexa toda a arvore do SASI e materializa em SQLite (memory/sasi_index.db).

Doutrina ZERO ALUCINACAO: so registra fato lido do disco. Nada inferido sem regra explicita.
Ao final, regenera MAPA-SASI.md a partir da base (evita drift manual).

Uso (da raiz do repo): python3 ~/projetos/scripts/indices/build_sasi_index.py
"""

import datetime
import hashlib
import os
import re
import sqlite3

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = os.path.join(DEV, "SASI-V3")
DB = os.path.join(ROOT, "memory", "sasi_index.db")
MAPA = os.path.join(ROOT, "memory", "MAPA-SASI.md")
SKIP_DIRS = {".git", "node_modules"}
SKIP_FILES = {"sasi_index.db", "sasi_index.db.bak"}
TEXT_EXT = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".sql",
    ".css",
    ".scss",
    ".html",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".py",
    ".env",
    ".example",
    ".mjs",
    ".cjs",
    ".svg",
    ".gitignore",
    ".editorconfig",
    ".lock",
    ".map",
}

CAT_LABELS = {
    "frontend_src": "App React+Vite+TS — `frontend/src/`",
    "design_system": "Tokens, componentes, guidelines — `design-system/`",
    "frontend_config": "Configs do front (package-lock, vite, tsconfig)",
    "mcp_config": "Config do MCP server",
    "build_artifact": "**Ruído gerado** — `dist/` de front e mcp",
    "docs": "Documentação — `docs/`",
    "mcp_src": "Código-fonte MCP — `mcp-server/src/`",
    "doctrine": "Doutrina clínica/arquitetura — `doctrine/`",
    "supabase_config": "Config Supabase (config.toml, seed)",
    "root_config": "CLAUDE.md, README, .env.example, .mcp.json",
    "edge_function": "Edge Functions Deno — `supabase/functions/`",
    "db_migration": "Migrations SQL — `supabase/migrations/`",
    "ide_config": "`.idea/` (WebStorm)",
    "ci": "GitHub Actions — `.github/workflows/`",
    "project_memory": "Esta pasta `memory/`",
    "claude_config": "`.claude/` (rules)",
    "frontend_public": "`frontend/public/`",
    "other": "Sem categoria (revisar regras)",
}


def categorize(rel):
    p = rel.replace("\\", "/")
    rules = [
        (r"^frontend/src/", "frontend_src"),
        (r"^frontend/dist/", "build_artifact"),
        (r"^frontend/public/", "frontend_public"),
        (r"^frontend/", "frontend_config"),
        (r"^mcp-server/src/", "mcp_src"),
        (r"^mcp-server/dist/", "build_artifact"),
        (r"^mcp-server/", "mcp_config"),
        (r"^supabase/migrations/", "db_migration"),
        (r"^supabase/functions/", "edge_function"),
        (r"^supabase/", "supabase_config"),
        (r"^doctrine/", "doctrine"),
        (r"^docs/", "docs"),
        (r"^design-system/", "design_system"),
        (r"^\.design-sync/", "design_system"),
        (r"^\.claude/", "claude_config"),
        (r"^memory/", "project_memory"),
        (r"^\.github/", "ci"),
        (r"^\.idea/", "ide_config"),
    ]
    for rx, cat in rules:
        if re.search(rx, p):
            return cat
    if "/" not in p:
        return "root_config"
    return "other"


def is_text(path, ext):
    if ext in TEXT_EXT:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        if b"\x00" in chunk:
            return False
        chunk.decode("utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        # UnicodeDecodeError = o arquivo não é texto UTF-8, logo é binário.
        # Sem ele aqui, um único byte inválido derrubava a varredura inteira.
        return False


def read_text_metrics(path, max_bytes=5_000_000):
    """Lê arquivo texto inteiro: linhas, chars, tokens (split whitespace), sha256."""
    try:
        with open(path, "rb") as f:
            raw = f.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None, None, None, None, None
        digest = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        chars = len(text)
        tokens = len(text.split())
        return lines, chars, tokens, digest, text
    except OSError:
        return None, None, None, None, None


def scan_files():
    rows = []
    fts_rows = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
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
            rel = os.path.relpath(full, ROOT)
            ext = os.path.splitext(fn)[1].lower() or (
                fn.lower() if fn.startswith(".") else ""
            )
            cat = categorize(rel)
            txt = is_text(full, ext)
            lines = chars = tokens = digest = None
            content = None
            if txt and st.st_size < 5_000_000:
                lines, chars, tokens, digest, content = read_text_metrics(full)
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
                    int(txt),
                    datetime.datetime.fromtimestamp(st.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    cat,
                )
            )
            if content is not None:
                fts_rows.append((rel, content))
    return rows, fts_rows


def build_db(rows, fts_rows):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    bak = DB + ".bak"
    if os.path.exists(DB):
        os.rename(DB, bak)
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.execute("""create table files(
      id integer primary key, path text unique, dir text, name text, ext text,
      size_bytes integer, lines integer, chars integer, tokens integer,
      sha256 text, is_text integer, mtime text, category text)""")
    c.executemany(
        "insert into files(path,dir,name,ext,size_bytes,lines,chars,tokens,sha256,is_text,mtime,category) "
        "values(?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    c.execute("""create table dirs as
      select dir, count(*) file_count, sum(size_bytes) total_bytes,
             sum(coalesce(lines,0)) total_lines, sum(coalesce(tokens,0)) total_tokens
      from files group by dir""")
    c.execute(
        "create view categorias as select category, count(*) arquivos, sum(size_bytes) bytes, "
        "sum(coalesce(lines,0)) linhas, sum(coalesce(tokens,0)) tokens "
        "from files group by category order by sum(coalesce(tokens,0)) desc"
    )
    c.execute("create index idx_files_cat on files(category)")
    c.execute("create index idx_files_ext on files(ext)")
    c.execute("create index idx_files_path on files(path)")
    c.execute("create index idx_files_tokens on files(tokens)")
    c.execute(
        "create virtual table files_fts using fts5(path, content, tokenize='unicode61')"
    )
    c.executemany("insert into files_fts(path, content) values(?,?)", fts_rows)
    if os.path.exists(bak):
        os.remove(bak)
    con.commit()
    return con, c


def write_mapa(c, today):
    tot_files, tot_bytes, tot_lines, tot_tokens = c.execute(
        "select count(*), sum(size_bytes), sum(coalesce(lines,0)), sum(coalesce(tokens,0)) from files"
    ).fetchone()
    cats = c.execute("select * from categorias").fetchall()
    top_code = c.execute(
        "select path, lines, category from files where is_text=1 and lines is not null "
        "and category not in ('build_artifact','frontend_config','mcp_config') "
        "order by lines desc limit 8"
    ).fetchall()
    frontend_dirs = c.execute(
        "select dir, count(*), sum(lines) from files where category='frontend_src' "
        "group by dir order by sum(lines) desc"
    ).fetchall()
    memory_docs = c.execute(
        "select path, lines from files where category='project_memory' and ext='.md' order by path"
    ).fetchall()
    other = c.execute("select path from files where category='other'").fetchall()

    lines = [
        "# MAPA DO SASI — inventário do repositório",
        "",
        f"> Gerado automaticamente em {today} por `~/projetos/scripts/indices/build_sasi_index.py`.",
        "> Fonte de verdade: `sasi_index.db` (SQLite). Doutrina ZERO ALUCINAÇÃO: só fato lido do disco.",
        "> Regenerar: `python3 ~/projetos/scripts/indices/build_sasi_index.py` (a partir da raiz do repo).",
        "",
        f"**Total:** {tot_files} arquivos · {tot_bytes / 1024 / 1024:.1f} MB · {tot_lines:,} linhas · "
        f"{tot_tokens:,} tokens (excluídos `.git`, `node_modules`, `sasi_index.db`).",
        "",
        "## Por categoria",
        "",
        "| Categoria | Arq | Linhas | Tokens | O que é |",
        "|---|---:|---:|---:|---|",
    ]
    for cat, n, _b, l, t in cats:
        label = CAT_LABELS.get(cat, cat)
        lines.append(f"| `{cat}` | {n} | {l or 0:,} | {t or 0:,} | {label} |")

    lines += [
        "",
        "## Núcleo (sem build_artifact nem lock files)",
        "",
        "### `frontend/src/` — por diretório",
        "",
        "| Diretório | Arq | Linhas |",
        "|---|---:|---:|",
    ]
    for d, n, l in frontend_dirs:
        lines.append(f"| `{d}` | {n} | {l or 0:,} |")

    lines += ["", "### Maiores arquivos de código/texto", ""]
    for path, l, cat in top_code:
        lines.append(f"- `{path}` — {l:,} linhas (`{cat}`)")

    lines += [
        "",
        "### Outros núcleos",
        "",
        "- **MCP** → `mcp-server/src/` — ponte skills→MCP→Supabase",
        "- **Backend** → `supabase/migrations/` + `supabase/functions/`",
        "- **Motor clínico v2** → `docs/motor-clinico-v2/`",
        "- **Design system** → `design-system/` (inclui fonts .woff/.woff2 sem contagem de linhas)",
        "",
        "## Memória do projeto (`memory/`)",
        "",
    ]
    for path, l in memory_docs:
        lines.append(f"- `{path}` — {l or 0} linhas")

    lines += [
        "",
        "## Consultas úteis",
        "",
        "```bash",
        "# Resumo por categoria",
        "python3 ~/projetos/scripts/indices/query_sasi_index.py categorias",
        "",
        "# Top arquivos por linhas",
        "python3 ~/projetos/scripts/indices/query_sasi_index.py top --n 15",
        "",
        "# Buscar path",
        "python3 ~/projetos/scripts/indices/query_sasi_index.py find FichaCompleta",
        "",
        "# Busca full-text (FTS5, token a token indexado)",
        "python3 ~/projetos/scripts/indices/query_sasi_index.py search eventos_clinicos",
        "```",
        "",
        "Tabelas SQLite: `files` (sha256, tokens), `dirs`, `files_fts` (FTS5), view `categorias`.",
        "Sync remoto (opcional): `python3 scripts/push_repo_index_to_postgres.py` → schema `repo_index` no Supabase.",
    ]
    if other:
        lines += ["", "## ⚠️ Categoria `other` (revisar regras)", ""]
        for (path,) in other:
            lines.append(f"- `{path}`")

    with open(MAPA, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    today = datetime.date.today().strftime("%d-%b-%Y").lower()
    rows, fts_rows = scan_files()
    con, c = build_db(rows, fts_rows)

    tot_files, tot_bytes, tot_lines, tot_tokens = c.execute(
        "select count(*), sum(size_bytes), sum(coalesce(lines,0)), sum(coalesce(tokens,0)) from files"
    ).fetchone()
    fts_count = c.execute("select count(*) from files_fts").fetchone()[0]
    print(f"DB: {DB}")
    print(
        f"TOTAL: {tot_files} arquivos | {tot_bytes / 1024:.0f} KB | {tot_lines} linhas | {tot_tokens} tokens"
    )
    print(f"FTS: {fts_count} documentos indexados token a token\n")
    print("=== POR CATEGORIA ===")
    print(f"{'categoria':<18}{'arq':>5}{'KB':>8}{'linhas':>9}{'tokens':>10}")
    for cat, n, b, l, t in c.execute("select * from categorias"):
        print(f"{cat:<18}{n:>5}{(b or 0) / 1024:>8.0f}{l or 0:>9}{t or 0:>10}")

    write_mapa(c, today)
    print(f"\nMAPA: {MAPA}")
    con.close()
    print("OK")


if __name__ == "__main__":
    main()
