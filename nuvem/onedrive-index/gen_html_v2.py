#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o painel de revisão v2 (HTML self-contained) do plano de reorganização por feature."""

import html
import json
from collections import Counter

TMP = "/home/dr/.claude/jobs/afe98ad9/tmp"
rows = json.load(open(f"{TMP}/rename_plan_v2.json", encoding="utf-8"))
PHI_CATS = {
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
FEAT_LABEL = {
    "clinico": "Clínico",
    "militar": "Militar-FAB",
    "estudo": "Estudo",
    "dev": "Dev-IA",
    "financeiro": "Financeiro",
    "tese": "Tese-Mãe",
    "pessoal": "Pessoal",
}

data = []
for r in rows:
    phi = r.get("phi_manual", (r.get("cat") in PHI_CATS))
    dump = r["status"] == "DUMP"
    data.append(
        {
            "a": r["atual"],
            "n": ("(preservado como está)" if dump else r["destino"]),
            "f": r["feature"],
            "phi": bool(phi),
            "rc": bool(r.get("reclass")) and not dump,
            "dump": dump,
        }
    )

# stats
feat_c = Counter(d["f"] for d in data if not d["dump"])
n_total = len(data)
n_dump = sum(d["dump"] for d in data)
n_reclass = sum(d["rc"] for d in data)
n_phi = sum(d["phi"] for d in data)
n_ren = n_total - n_dump

JSON = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
FEATS = json.dumps({k: v for k, v in FEAT_LABEL.items()}, ensure_ascii=False)

stat_cards = "".join(
    f'<div class="card"><span class="big">{v}</span><span class="lbl">{FEAT_LABEL[k]}</span></div>'
    for k, v in sorted(feat_c.items(), key=lambda x: -x[1])
)

HTML = f"""<title>Revisão — Reorganização OneDrive por feature</title>
<style>
:root{{
  --bg:#eef1f5; --panel:#ffffff; --ink:#141821; --ink2:#4a5568; --line:#d9dfe8;
  --accent:#2b6cb0; --shadow:0 1px 2px rgba(20,24,33,.06),0 4px 14px rgba(20,24,33,.05);
  --clinico:#c0395b; --militar:#5f7a3e; --estudo:#2b6cb0; --dev:#7048c4;
  --financeiro:#b5811f; --tese:#0f8b8d; --pessoal:#6b7280; --phi:#c05621;
}}
@media (prefers-color-scheme:dark){{:root{{
  --bg:#0e1117; --panel:#161b23; --ink:#e6ebf2; --ink2:#9aa6b6; --line:#262e3a;
  --accent:#63a4e0; --shadow:0 1px 2px rgba(0,0,0,.4),0 6px 20px rgba(0,0,0,.35);
  --clinico:#e8698a; --militar:#9dc06a; --estudo:#63a4e0; --dev:#a988f0;
  --financeiro:#e0b24d; --tese:#3fc2c4; --pessoal:#9aa6b6; --phi:#ed8936;
}}}}
:root[data-theme="light"]{{--bg:#eef1f5;--panel:#fff;--ink:#141821;--ink2:#4a5568;--line:#d9dfe8;--accent:#2b6cb0;--clinico:#c0395b;--militar:#5f7a3e;--estudo:#2b6cb0;--dev:#7048c4;--financeiro:#b5811f;--tese:#0f8b8d;--pessoal:#6b7280;--phi:#c05621;}}
:root[data-theme="dark"]{{--bg:#0e1117;--panel:#161b23;--ink:#e6ebf2;--ink2:#9aa6b6;--line:#262e3a;--accent:#63a4e0;--clinico:#e8698a;--militar:#9dc06a;--estudo:#63a4e0;--dev:#a988f0;--financeiro:#e0b24d;--tese:#3fc2c4;--pessoal:#9aa6b6;--phi:#ed8936;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5;
  padding:clamp(16px,3vw,40px)}}
.wrap{{max-width:1180px;margin:0 auto}}
header h1{{font-size:clamp(1.3rem,2.6vw,1.9rem);margin:0 0 .2em;letter-spacing:-.01em;text-wrap:balance}}
header p{{color:var(--ink2);margin:0 0 1.4em;max-width:62ch}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:22px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
  display:flex;flex-direction:column;gap:2px;box-shadow:var(--shadow)}}
.card .big{{font-size:1.7rem;font-weight:680;font-variant-numeric:tabular-nums}}
.card .lbl{{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink2)}}
.card.k .big{{color:var(--accent)}}
.bar{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:16px}}
.chip{{border:1px solid var(--line);background:var(--panel);color:var(--ink2);
  padding:6px 12px;border-radius:999px;font-size:.82rem;cursor:pointer;user-select:none;
  display:inline-flex;gap:7px;align-items:center;transition:.12s}}
.chip .dot{{width:9px;height:9px;border-radius:50%}}
.chip[aria-pressed="true"]{{color:var(--ink);border-color:currentColor;font-weight:600}}
.chip:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
#q{{flex:1;min-width:180px;padding:8px 13px;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);font-size:.88rem}}
#q:focus-visible{{outline:2px solid var(--accent);outline-offset:1px}}
.tablewrap{{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel);box-shadow:var(--shadow)}}
table{{border-collapse:collapse;width:100%;font-size:.83rem}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{position:sticky;top:0;background:var(--panel);z-index:1;font-size:.72rem;text-transform:uppercase;
  letter-spacing:.05em;color:var(--ink2);font-weight:600}}
tr:last-child td{{border-bottom:none}}
.path{{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.78rem;word-break:break-word}}
.old{{color:var(--ink2)}}
.arrow{{color:var(--accent);padding:0 2px}}
.fbadge{{display:inline-block;padding:2px 9px;border-radius:6px;font-size:.72rem;font-weight:600;
  white-space:nowrap;color:#fff}}
.flags{{display:flex;gap:5px;flex-wrap:wrap}}
.tag{{font-size:.66rem;font-weight:700;letter-spacing:.03em;padding:2px 6px;border-radius:5px;white-space:nowrap}}
.tag.phi{{background:color-mix(in srgb,var(--phi) 18%,transparent);color:var(--phi);border:1px solid color-mix(in srgb,var(--phi) 40%,transparent)}}
.tag.rc{{background:color-mix(in srgb,var(--accent) 15%,transparent);color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 38%,transparent)}}
.tag.dump{{background:color-mix(in srgb,var(--pessoal) 18%,transparent);color:var(--pessoal);border:1px solid color-mix(in srgb,var(--pessoal) 40%,transparent)}}
.count{{color:var(--ink2);font-size:.8rem;margin:10px 2px}}
tr.dumprow .path.new{{font-style:italic;color:var(--ink2);font-family:system-ui}}
footer{{color:var(--ink2);font-size:.76rem;margin-top:22px;text-align:center}}
</style>
<div class="wrap">
<header>
<h1>Reorganização do OneDrive — por feature</h1>
<p>Plano proposto: cada arquivo agrupado por <b>o que ele é</b> (tipo/assunto), não por data. O <code>~aprox</code> foi removido — data só entra no nome quando é real. <b>Nada foi movido ainda.</b> Confira e aprove.</p>
</header>
<div class="cards">
<div class="card k"><span class="big">{n_ren}</span><span class="lbl">Renomeações</span></div>
<div class="card k"><span class="big">{n_reclass}</span><span class="lbl">Reclassificados</span></div>
<div class="card"><span class="big">{n_phi}</span><span class="lbl">Com dado de paciente</span></div>
<div class="card"><span class="big">{n_dump}</span><span class="lbl">Código (preservado)</span></div>
</div>
<div class="cards">{stat_cards}</div>
<div class="bar" id="chips"></div>
<div class="bar"><input id="q" type="search" placeholder="Buscar no nome do arquivo…" autocomplete="off"></div>
<div class="count" id="count"></div>
<div class="tablewrap"><table>
<thead><tr><th style="width:44%">Nome atual</th><th style="width:44%">Vira</th><th>Feature</th><th>Flags</th></tr></thead>
<tbody id="tb"></tbody>
</table></div>
<footer>Revisão gerada do estado atual do OneDrive · {n_total} arquivos · fluxo: você aprova → eu movo · originais no Google Drive como backup</footer>
</div>
<script>
const DATA={JSON}, FEATS={FEATS};
const FCOL={{clinico:'--clinico',militar:'--militar',estudo:'--estudo',dev:'--dev',financeiro:'--financeiro',tese:'--tese',pessoal:'--pessoal'}};
let active=new Set(Object.keys(FEATS)), q="";
const chips=document.getElementById('chips');
Object.entries(FEATS).forEach(([k,v])=>{{
  const b=document.createElement('button');b.className='chip';b.setAttribute('aria-pressed','true');
  b.innerHTML=`<span class="dot" style="background:var(${{FCOL[k]}})"></span>${{v}}`;
  b.onclick=()=>{{active.has(k)?active.delete(k):active.add(k);b.setAttribute('aria-pressed',active.has(k));render();}};
  chips.appendChild(b);
}});
const esc=s=>s.replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
const tb=document.getElementById('tb'), cnt=document.getElementById('count');
function render(){{
  const ql=q.toLowerCase();
  const rowsF=DATA.filter(d=>(d.dump?active.has('dev'):active.has(d.f))&&(!ql||d.a.toLowerCase().includes(ql)||d.n.toLowerCase().includes(ql)));
  cnt.textContent=`${{rowsF.length}} arquivo(s) exibido(s)`;
  tb.innerHTML=rowsF.map(d=>{{
    const col=`var(${{FCOL[d.f]||'--pessoal'}})`;
    const flags=[d.phi?'<span class="tag phi">PACIENTE</span>':'',d.rc?'<span class="tag rc">RECLASS</span>':'',d.dump?'<span class="tag dump">CÓDIGO</span>':''].join('');
    return `<tr class="${{d.dump?'dumprow':''}}">
      <td><span class="path old">${{esc(d.a)}}</span></td>
      <td><span class="arrow">▸</span><span class="path new">${{esc(d.n)}}</span></td>
      <td><span class="fbadge" style="background:${{col}}">${{FEATS[d.f]||d.f}}</span></td>
      <td><span class="flags">${{flags||'—'}}</span></td></tr>`;
  }}).join('');
}}
document.getElementById('q').addEventListener('input',e=>{{q=e.target.value;render();}});
render();
</script>"""
open(f"{TMP}/revisao_v2.html", "w", encoding="utf-8").write(HTML)
print(
    f"HTML gerado: {len(HTML)//1024} KB | {n_total} linhas | {n_ren} renomeações, {n_dump} dumps"
)
print("features:", dict(feat_c.most_common()))
