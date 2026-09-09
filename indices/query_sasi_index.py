#!/usr/bin/env python3
"""Consultas rápidas ao índice local do SASI (memory/sasi_index.db).

Uso (da raiz do repo):
  python3 scripts/query_sasi_index.py categorias
  python3 scripts/query_sasi_index.py top [--n 15]
  python3 scripts/query_sasi_index.py find <termo>
  python3 scripts/query_sasi_index.py cat <categoria>
  python3 scripts/query_sasi_index.py dir <caminho-parcial>
  python3 scripts/query_sasi_index.py search <termo>   # FTS5 full-text
"""

import argparse
import os
import sqlite3
import sys

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = os.path.join(DEV, "SASI-V3")
DB = os.path.join(ROOT, "memory", "sasi_index.db")


def connect():
    if not os.path.exists(DB):
        sys.exit(f"Índice ausente: {DB}\nRode: python3 scripts/build_sasi_index.py")
    return sqlite3.connect(DB)


def cmd_categorias(c):
    print(f"{'categoria':<18}{'arq':>5}{'linhas':>9}{'tokens':>10}")
    for cat, n, _b, l, t in c.execute("select * from categorias"):
        print(f"{cat:<18}{n:>5}{l or 0:>9}{t or 0:>10}")


def cmd_top(c, n):
    for path, lines, cat in c.execute(
        "select path, lines, category from files where is_text=1 and lines is not null "
        "order by lines desc limit ?",
        (n,),
    ):
        print(f"{lines:>6}  [{cat}]  {path}")


def cmd_find(c, term):
    like = f"%{term}%"
    rows = c.execute(
        "select path, lines, category from files where path like ? order by path",
        (like,),
    ).fetchall()
    if not rows:
        print(f"(nenhum match para '{term}')")
        return
    for path, lines, cat in rows:
        print(f"{(lines or 0):>6}  [{cat}]  {path}")


def cmd_cat(c, category):
    rows = c.execute(
        "select path, lines from files where category=? order by coalesce(lines,0) desc",
        (category,),
    ).fetchall()
    if not rows:
        print(f"(categoria vazia ou inexistente: {category})")
        return
    for path, lines in rows:
        print(f"{(lines or 0):>6}  {path}")


def cmd_search(c, term):
    rows = c.execute(
        "select path, snippet(files_fts, 1, '>>', '<<', '…', 48) "
        "from files_fts where files_fts match ? limit 25",
        (term,),
    ).fetchall()
    if not rows:
        print(f"(FTS: nenhum match para '{term}')")
        return
    for path, snip in rows:
        print(f"{path}\n  {snip}\n")


def cmd_dir(c, term):
    like = f"%{term}%"
    rows = c.execute(
        "select dir, file_count, total_lines from dirs where dir like ? order by total_lines desc",
        (like,),
    ).fetchall()
    if not rows:
        print(f"(nenhum dir para '{term}')")
        return
    for d, n, l in rows:
        print(f"{l or 0:>7} lin  {n:>3} arq  {d}")


def main():
    p = argparse.ArgumentParser(description="Consulta sasi_index.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("categorias", help="resumo por categoria")

    top = sub.add_parser("top", help="maiores arquivos por linhas")
    top.add_argument("--n", type=int, default=15)

    find = sub.add_parser("find", help="busca path (substring)")
    find.add_argument("term")

    cat = sub.add_parser("cat", help="lista arquivos de uma categoria")
    cat.add_argument("category")

    d = sub.add_parser("dir", help="agregado por diretório")
    d.add_argument("term")

    sr = sub.add_parser("search", help="busca full-text FTS5 no conteúdo")
    sr.add_argument("term")

    args = p.parse_args()
    con = connect()
    c = con.cursor()

    if args.cmd == "categorias":
        cmd_categorias(c)
    elif args.cmd == "top":
        cmd_top(c, args.n)
    elif args.cmd == "find":
        cmd_find(c, args.term)
    elif args.cmd == "cat":
        cmd_cat(c, args.category)
    elif args.cmd == "dir":
        cmd_dir(c, args.term)
    elif args.cmd == "search":
        cmd_search(c, args.term)

    con.close()


if __name__ == "__main__":
    main()
