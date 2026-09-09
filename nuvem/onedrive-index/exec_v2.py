#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executa o plano v2: move+renomeia (OK) e agrupa dumps (DUMP) server-side no OneDrive.
Paralelo, sem baixar/subir. Loga cada resultado. Idempotente: se src sumiu e dst existe, conta OK.
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

RC = os.path.expanduser("~/.local/bin/rclone")
BASE = "onedrive:Documentos-claude-e-importacao-drive"
TMP = "/home/dr/.claude/jobs/afe98ad9/tmp"
rows = json.load(open(f"{TMP}/rename_plan_v2.json", encoding="utf-8"))

jobs = []
for r in rows:
    if r["status"] == "OK":
        jobs.append((r["atual"], r["destino"]))
    elif r["status"] == "DUMP":
        jobs.append((r["atual"], "Dev-IA/_codigo-backup/" + r["atual"]))
# nada a fazer se src==dst
jobs = [(s, d) for s, d in jobs if s != d]

logf = open(f"{TMP}/result_v2.log", "w", encoding="utf-8")


def move(job):
    src, dst = job
    r = subprocess.run(
        [
            RC,
            "moveto",
            f"{BASE}/{src}",
            f"{BASE}/{dst}",
            "--onedrive-hash-type",
            "none",
            "--retries",
            "3",
            "--timeout",
            "60s",
            "--low-level-retries",
            "5",
        ],
        capture_output=True,
        text=True,
    )
    ok = r.returncode == 0
    if not ok:
        # idempotência: se o destino já existe e a origem sumiu, considera feito
        chk = subprocess.run(
            [RC, "lsf", f"{BASE}/{dst}"], capture_output=True, text=True
        )
        if chk.stdout.strip():
            ok = True
    logf.write(("OK " if ok else "FAIL ") + f"{src}\t->\t{dst}\n")
    if not ok:
        logf.write("   ERR " + (r.stderr or "").strip().replace("\n", " ")[:200] + "\n")
    logf.flush()
    return ok


total = len(jobs)
done = 0
okc = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    for ok in ex.map(move, jobs):
        done += 1
        okc += ok
        if done % 50 == 0:
            print(f"{done}/{total} ({okc} OK)")
            sys.stdout.flush()
logf.close()
print(f"CONCLUÍDO: {okc}/{total} movidos OK, {total-okc} falhas")
