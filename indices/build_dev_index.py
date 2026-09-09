#!/usr/bin/env python3
"""Indexa ~/projetos/ inteiro → memory/dev_index.db + MAPA-DEV.md.

Doutrina ZERO ALUCINACAO: so fato lido do disco.
Uso: python3 ~/projetos/scripts/indices/build_dev_index.py  (de ~/projetos)
"""

import datetime
import hashlib
import os
import sqlite3
import sys

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = DEV
DB = os.path.join(ROOT, "memory", "dev_index.db")
MAPA = os.path.join(ROOT, "memory", "MAPA-DEV.md")

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".turbo",
    ".next",
    "dist",
    "build",
    ".cache",
}
SKIP_FILES = {
    "dev_index.db",
    "dev_index.db.bak",
    "sasi_index.db",
    "sasi_index.db.bak",
}
SKIP_PREFIXES = ("dist/", "frontend/dist/", "mcp-server/dist/")

# Diretorios de ESTADO DE FERRAMENTA: ainda sao indexados, mas mudancas neles
# NAO contam como "codigo novo" para o gatilho --if-stale (a IDE reescreve
# .idea/workspace.xml e o harness reescreve .claude/settings.local.json o tempo
# todo; sem isso o indice ficaria "sempre stale" e reindexaria a cada turno).
STALE_IGNORE = {".idea", ".claude"}
# Arquivos de OUTPUT do proprio build: sao indexados, mas write_mapa() os escreve
# DEPOIS do .db, entao seriam vistos como "mais novos que o indice" e deixariam
# --if-stale sempre verdadeiro. Ignorados so na checagem de stale.
STALE_IGNORE_FILES = {"MAPA-DEV.md"}

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
    ".mdc",
}


def repo_of(rel):
    parts = rel.replace("\\", "/").split("/")
    if len(parts) == 1:
        return "(root)"
    top = parts[0]
    if top.startswith("."):
        return top
    return top


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
        return False


def read_text_metrics(path, max_bytes=5_000_000):
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
        return lines, len(text), len(text.split()), digest, text
    except OSError:
        return None, None, None, None, None


def scan():
    rows, fts = [], []
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
            if any(rel.startswith(p) for p in SKIP_PREFIXES):
                continue
            if "/dist/" in rel or rel.endswith("/dist"):
                continue
            ext = os.path.splitext(fn)[1].lower() or (
                fn.lower() if fn.startswith(".") else ""
            )
            rep = repo_of(rel)
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
                    rep,
                    st.st_size,
                    lines,
                    chars,
                    tokens,
                    digest,
                    int(txt),
                    datetime.datetime.fromtimestamp(st.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                )
            )
            if content is not None:
                fts.append((rel, content))
    return rows, fts


def build_db(rows, fts_rows):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    bak = DB + ".bak"
    if os.path.exists(DB):
        os.rename(DB, bak)
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.execute("""create table files(
      id integer primary key, path text unique, dir text, name text, ext text,
      repo text, size_bytes integer, lines integer, chars integer, tokens integer,
      sha256 text, is_text integer, mtime text)""")
    c.executemany(
        "insert into files(path,dir,name,ext,repo,size_bytes,lines,chars,tokens,sha256,is_text,mtime) "
        "values(?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    c.execute("""create table repos as
      select repo, count(*) arquivos, sum(size_bytes) bytes,
             sum(coalesce(lines,0)) linhas, sum(coalesce(tokens,0)) tokens
      from files group by repo order by sum(coalesce(tokens,0)) desc""")
    c.execute("""create table dirs as
      select dir, repo, count(*) file_count, sum(size_bytes) total_bytes,
             sum(coalesce(lines,0)) total_lines, sum(coalesce(tokens,0)) total_tokens
      from files group by dir, repo""")
    c.execute("""create view extensoes as
      select ext, count(*) arquivos, sum(coalesce(tokens,0)) tokens
      from files group by ext order by count(*) desc""")
    c.execute("create index idx_files_repo on files(repo)")
    c.execute("create index idx_files_ext on files(ext)")
    c.execute(
        "create virtual table files_fts using fts5(path, content, tokenize='unicode61')"
    )
    c.executemany("insert into files_fts(path, content) values(?,?)", fts_rows)
    if os.path.exists(bak):
        os.remove(bak)
    con.commit()
    return con, c


def write_mapa(c, today):
    tot = c.execute(
        "select count(*), sum(size_bytes), sum(coalesce(lines,0)), sum(coalesce(tokens,0)) from files"
    ).fetchone()
    repos = c.execute("select * from repos").fetchall()
    top = c.execute(
        "select path, repo, lines, tokens from files where is_text=1 and lines is not null "
        "order by tokens desc limit 12"
    ).fetchall()

    out = [
        "# MAPA — ~/projetos/",
        "",
        f"> Gerado {today} por `~/projetos/scripts/indices/build_dev_index.py`.",
        f"> DB: `memory/dev_index.db` · FTS5 token a token.",
        "",
        f"**Total:** {tot[0]} arquivos · {tot[1]/1024/1024:.1f} MB · {tot[2]:,} linhas · {tot[3]:,} tokens",
        "(excl. `.git`, `node_modules`, `dist/`, índices `.db`).",
        "",
        "## Por repo",
        "",
        "| Repo | Arq | Linhas | Tokens |",
        "|---|---:|---:|---:|",
    ]
    for rep, n, _b, l, t in repos:
        out.append(f"| `{rep}` | {n} | {l or 0:,} | {t or 0:,} |")

    out += ["", "## Maiores arquivos (tokens)", ""]
    for path, rep, l, t in top:
        out.append(f"- `{path}` — {t or 0:,} tok / {l or 0:,} lin (`{rep}`)")

    out += [
        "",
        "## Consultas",
        "",
        "```bash",
        "python3 ~/projetos/scripts/indices/query_dev_index.py repos",
        "python3 ~/projetos/scripts/indices/query_dev_index.py find CLAUDE",
        "python3 ~/projetos/scripts/indices/query_dev_index.py search supabase",
        "python3 ~/projetos/scripts/indices/query_dev_index.py repo sasi",
        "```",
    ]
    with open(MAPA, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def is_stale():
    """True se algum arquivo indexavel e mais novo que o .db. So stat (mtime),
    nao le conteudo; para no primeiro arquivo mais novo. Ignora STALE_IGNORE."""
    if not os.path.exists(DB):
        return True
    db_mtime = os.stat(DB).st_mtime
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and d not in STALE_IGNORE
        ]
        for fn in filenames:
            if fn in SKIP_FILES or fn in STALE_IGNORE_FILES:
                continue
            try:
                if os.lstat(os.path.join(dirpath, fn)).st_mtime > db_mtime:
                    return True
            except OSError:
                continue
    return False


def main():
    if "--if-stale" in sys.argv and not is_stale():
        print("fresh — indice atualizado, sem reindex")
        return
    today = datetime.date.today().strftime("%d-%b-%Y").lower()
    rows, fts = scan()
    con, c = build_db(rows, fts)
    tot = c.execute(
        "select count(*), sum(size_bytes), sum(coalesce(lines,0)), sum(coalesce(tokens,0)) from files"
    ).fetchone()
    fts_n = c.execute("select count(*) from files_fts").fetchone()[0]
    print(f"ROOT: {ROOT}")
    print(f"DB:   {DB}")
    print(
        f"TOTAL: {tot[0]} arquivos | {tot[1]/1024:.0f} KB | {tot[2]} linhas | {tot[3]} tokens"
    )
    print(f"FTS:   {fts_n} docs\n")
    print("=== POR REPO ===")
    print(f"{'repo':<16}{'arq':>5}{'linhas':>9}{'tokens':>10}")
    for rep, n, _b, l, t in c.execute("select * from repos"):
        print(f"{rep:<16}{n:>5}{l or 0:>9}{t or 0:>10}")
    write_mapa(c, today)
    print(f"\nMAPA: {MAPA}")
    con.close()
    print("OK")


if __name__ == "__main__":
    main()
