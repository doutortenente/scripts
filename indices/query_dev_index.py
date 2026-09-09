#!/usr/bin/env python3
"""Consulta memory/dev_index.db (~/projetos inteiro).

python3 ~/projetos/scripts/indices/query_dev_index.py repos
python3 ~/projetos/scripts/indices/query_dev_index.py find <termo>
python3 ~/projetos/scripts/indices/query_dev_index.py search <termo>
python3 ~/projetos/scripts/indices/query_dev_index.py repo <nome>
python3 ~/projetos/scripts/indices/query_dev_index.py top [--n 15]
"""

import argparse
import os
import sqlite3
import sys

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = DEV
DB = os.path.join(ROOT, "memory", "dev_index.db")


def connect():
    if not os.path.exists(DB):
        sys.exit(
            f"Índice ausente: {DB}\nRode: python3 ~/projetos/scripts/indices/build_dev_index.py"
        )
    return sqlite3.connect(DB)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("repos")
    f = sub.add_parser("find")
    f.add_argument("term")
    s = sub.add_parser("search")
    s.add_argument("term")
    r = sub.add_parser("repo")
    r.add_argument("name")
    t = sub.add_parser("top")
    t.add_argument("--n", type=int, default=15)
    args = p.parse_args()
    c = connect().cursor()

    if args.cmd == "repos":
        print(f"{'repo':<16}{'arq':>5}{'linhas':>9}{'tokens':>10}")
        for rep, n, _b, l, tok in c.execute("select * from repos"):
            print(f"{rep:<16}{n:>5}{l or 0:>9}{tok or 0:>10}")
    elif args.cmd == "find":
        like = f"%{args.term}%"
        for row in c.execute(
            "select path, repo, lines, tokens from files where path like ? order by tokens desc",
            (like,),
        ):
            print(f"{row[3] or 0:>7} tok  [{row[1]}]  {row[0]}")
    elif args.cmd == "search":
        for path, snip in c.execute(
            "select path, snippet(files_fts, 1, '>>', '<<', '…', 48) "
            "from files_fts where files_fts match ? limit 25",
            (args.term,),
        ):
            print(f"{path}\n  {snip}\n")
    elif args.cmd == "repo":
        print(f"=== {args.name} ===")
        for path, lines, tokens in c.execute(
            "select path, lines, tokens from files where repo=? order by coalesce(tokens,0) desc limit 40",
            (args.name,),
        ):
            print(f"{tokens or 0:>7} tok  {path}")
    elif args.cmd == "top":
        for path, rep, lines, tokens in c.execute(
            "select path, repo, lines, tokens from files where tokens is not null "
            "order by tokens desc limit ?",
            (args.n,),
        ):
            print(f"{tokens:>7} tok  [{rep}]  {path}")


if __name__ == "__main__":
    main()
