#!/usr/bin/env python3
"""Auditoria rápida de eventos_clinicos — fila requires_review e baixa confidence."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

URL = os.environ.get("VITE_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
    "VITE_SUPABASE_ANON_KEY"
)


def fetch(path: str) -> list[dict]:
    if not URL or not KEY:
        print("Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        sys.exit(1)
    req = urllib.request.Request(
        f"{URL}/rest/v1/{path}",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    review = fetch(
        "eventos_clinicos?select=id,tipo,confidence,requires_review,ts,paciente_id"
        "&or=(requires_review.eq.true,confidence.lt.0.7)"
        "&order=ts.desc&limit=50"
    )
    total = fetch("eventos_clinicos?select=id&limit=1")
    print(f"Fila auditoria (top 50): {len(review)} itens")
    for row in review:
        print(
            f"  {row.get('ts','?')[:16]} | {row.get('tipo')} | conf={row.get('confidence')} "
            f"| review={row.get('requires_review')} | {row.get('id')}"
        )
    print("Total eventos (amostra API):", "ok" if total is not None else "erro")


if __name__ == "__main__":
    main()
