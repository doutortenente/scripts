#!/usr/bin/env python3
"""Consulta rápida ao índice Claude (evita varrer 900+ arquivos).

python3 ~/projetos/scripts/indices/query_claude_index.py skills [--clinical|--dev|--design]
python3 ~/projetos/scripts/indices/query_claude_index.py skill <nome>
python3 ~/projetos/scripts/indices/query_claude_index.py scripts
python3 ~/projetos/scripts/indices/query_claude_index.py agents
python3 ~/projetos/scripts/indices/query_claude_index.py categorias
python3 ~/projetos/scripts/indices/query_claude_index.py find <termo>
python3 ~/projetos/scripts/indices/query_claude_index.py search <termo>
python3 ~/projetos/scripts/indices/query_claude_index.py cat <categoria>
python3 ~/projetos/scripts/indices/query_claude_index.py top [--n 15]
"""

import argparse
import os
import sqlite3
import sys

DEV = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # ~/projetos
ROOT = os.path.join(DEV, "claude")
DB = os.path.join(ROOT, "memory", "claude_index.db")


def connect():
    if not os.path.exists(DB):
        sys.exit(
            f"Índice ausente: {DB}\nRode: python3 ~/projetos/scripts/indices/build_claude_index.py"
        )
    return sqlite3.connect(DB)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sk = sub.add_parser("skills", help="lista skills (name + path)")
    sk.add_argument("--clinical", action="store_true")
    sk.add_argument("--dev", action="store_true")
    sk.add_argument("--design", action="store_true")
    sk.add_argument("--anthropic", action="store_true")

    s1 = sub.add_parser("skill", help="detalhe de uma skill")
    s1.add_argument("name")

    sub.add_parser("scripts", help="scripts executáveis")
    sub.add_parser("agents", help="subagentes")
    sub.add_parser("categorias", help="resumo por categoria")

    f = sub.add_parser("find", help="busca path (substring)")
    f.add_argument("term")

    s = sub.add_parser("search", help="FTS5 full-text")
    s.add_argument("term")

    c2 = sub.add_parser("cat", help="arquivos por categoria")
    c2.add_argument("name")

    t = sub.add_parser("top", help="maiores por tokens")
    t.add_argument("--n", type=int, default=15)

    args = p.parse_args()
    cur = connect().cursor()

    if args.cmd == "skills":
        q = "select name, path, category, description from skills"
        filt = []
        if args.clinical:
            filt.append("skill_clinical")
        if args.dev:
            filt.append("skill_dev")
        if args.design:
            filt.append("skill_design")
        if args.anthropic:
            filt.append("skill_anthropic")
        if filt:
            q += " where category in (" + ",".join("?" * len(filt)) + ") order by name"
            rows = cur.execute(q, filt).fetchall()
        else:
            rows = cur.execute(q + " order by category, name").fetchall()
        for name, path, cat, desc in rows:
            print(f"[{cat}] {name}")
            print(f"  {path}")
            if desc:
                print(f"  {desc[:120]}{'…' if len(desc) > 120 else ''}")
            print()

    elif args.cmd == "skill":
        row = cur.execute(
            "select name, path, category, description, tokens from skills where name=?",
            (args.name,),
        ).fetchone()
        if not row:
            row = cur.execute(
                "select name, path, category, description, tokens from skills where name like ?",
                (f"%{args.name}%",),
            ).fetchone()
        if not row:
            sys.exit(f"Skill não encontrada: {args.name}")
        name, path, cat, desc, tok = row
        print(f"name: {name}")
        print(f"path: {path}")
        print(f"category: {cat}")
        print(f"tokens: {tok}")
        print(f"description: {desc}")

    elif args.cmd == "scripts":
        for path, lines in cur.execute(
            "select path, lines from files where category='script' order by path"
        ):
            print(f"{(lines or 0):>5} lin  {path}")

    elif args.cmd == "agents":
        for path, lines in cur.execute(
            "select path, lines from files where category='agent' order by path"
        ):
            print(f"{(lines or 0):>5} lin  {path}")

    elif args.cmd == "categorias":
        print(f"{'categoria':<18}{'arq':>5}{'tokens':>10}")
        for cat, n, _b, _l, t in cur.execute("select * from categorias"):
            print(f"{cat:<18}{n:>5}{t or 0:>10}")

    elif args.cmd == "find":
        like = f"%{args.term}%"
        for path, cat, tokens in cur.execute(
            "select path, category, tokens from files where path like ? "
            "order by coalesce(tokens,0) desc limit 40",
            (like,),
        ):
            print(f"{(tokens or 0):>7} tok  [{cat}]  {path}")

    elif args.cmd == "search":
        for path, snip in cur.execute(
            "select path, snippet(files_fts, 1, '>>', '<<', '…', 48) "
            "from files_fts where files_fts match ? limit 20",
            (args.term,),
        ):
            print(f"{path}\n  {snip}\n")

    elif args.cmd == "cat":
        for path, tokens in cur.execute(
            "select path, tokens from files where category=? order by coalesce(tokens,0) desc",
            (args.name,),
        ):
            print(f"{(tokens or 0):>7} tok  {path}")

    elif args.cmd == "top":
        for path, cat, tokens in cur.execute(
            "select path, category, tokens from files where tokens is not null "
            "and category != 'vendor_blob' order by tokens desc limit ?",
            (args.n,),
        ):
            print(f"{tokens:>7} tok  [{cat}]  {path}")


if __name__ == "__main__":
    main()
