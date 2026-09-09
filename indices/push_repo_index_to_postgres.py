#!/usr/bin/env python3
"""Popula repo_index.files / repo_index.dirs no Postgres do Supabase a partir do
SQLite local (memory/sasi_index.db). Idempotente: recria schema se faltar e
da TRUNCATE antes de inserir. Rode da raiz do repo: python3 scripts/push_repo_index_to_postgres.py

Requer: psycopg (ja instalado em ~/.local via pip --user) e SUPABASE_DB_URL no .env.
ESCREVE direto na producao -> rode em sessao autorizada (ex: claude --dangerously-skip-permissions).
"""

import os
import sqlite3
import sys

try:
    import psycopg
except ImportError:
    sys.exit(
        "psycopg ausente. Instale: pip install --user --break-system-packages 'psycopg[binary]'"
    )

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = os.path.join(DEV, "SASI-V3")
DB = os.path.join(ROOT, "memory", "sasi_index.db")


def db_url():
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line.startswith("SUPABASE_DB_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("SUPABASE_DB_URL nao encontrada no .env")


DDL = """
create schema if not exists repo_index;
create table if not exists repo_index.files(
  id bigint generated always as identity primary key, path text unique not null,
  dir text, name text, ext text, size_bytes bigint, lines integer,
  is_text integer, mtime text, category text);
create table if not exists repo_index.dirs(
  dir text primary key, file_count integer, total_bytes bigint, total_lines integer);
create or replace view repo_index.categorias as
  select category, count(*) as arquivos, sum(size_bytes) as bytes, sum(coalesce(lines,0)) as linhas
  from repo_index.files group by category order by sum(coalesce(lines,0)) desc;
"""


def main():
    sq = sqlite3.connect(DB)
    files = sq.execute(
        "select path,dir,name,ext,size_bytes,lines,is_text,mtime,category from files"
    ).fetchall()
    dirs = sq.execute(
        "select dir,file_count,total_bytes,total_lines from dirs"
    ).fetchall()
    with psycopg.connect(db_url(), connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("truncate repo_index.files, repo_index.dirs;")
            cur.executemany(
                "insert into repo_index.files(path,dir,name,ext,size_bytes,lines,is_text,mtime,category)"
                " values(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                files,
            )
            cur.executemany(
                "insert into repo_index.dirs(dir,file_count,total_bytes,total_lines) values(%s,%s,%s,%s)",
                dirs,
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("select count(*) from repo_index.files")
            f = cur.fetchone()[0]
            cur.execute("select count(*) from repo_index.dirs")
            d = cur.fetchone()[0]
    print(f"OK -> repo_index.files={f}  repo_index.dirs={d}")


if __name__ == "__main__":
    main()
