"""Page d'archive (docs/index.html) : tous les carrousels deja produits.

Utile pour se relire, retrouver une source, ou activer GitHub Pages sur /docs.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

GABARIT = """<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titre} — archives</title>
<style>
 :root{{color-scheme:dark}}
 body{{margin:0;background:#0B0B0F;color:#F5F1E8;
   font:16px/1.6 Inter,system-ui,-apple-system,Segoe UI,sans-serif}}
 header{{padding:56px 24px 24px;max-width:1000px;margin:auto}}
 h1{{font-family:Georgia,serif;font-size:40px;margin:0 0 6px}}
 .sous{{color:#A9A29A;margin:0}}
 main{{max-width:1000px;margin:auto;padding:0 24px 80px}}
 section{{border-top:1px solid #262630;padding:28px 0}}
 h2{{font-family:Georgia,serif;font-size:24px;margin:0 0 12px;color:#C9A227}}
 .pellicule{{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}}
 .pellicule img{{height:210px;border-radius:8px;flex:0 0 auto}}
 ul{{margin:12px 0 0;padding-left:18px;color:#A9A29A}}
 a{{color:#C9A227}}
</style>
<header><h1>{titre}</h1><p class="sous">{baseline} — archives des carrousels publies</p></header>
<main>{corps}</main></html>
"""


def construire(docs: Path, cfg: dict) -> None:
    sections = []
    for dossier in sorted((d for d in docs.iterdir() if d.is_dir()), reverse=True):
        m = dossier / "manifest.json"
        if not m.exists():
            continue
        data = json.loads(m.read_text("utf-8"))
        vignettes = "".join(
            f'<img loading="lazy" src="{dossier.name}/{s}" alt="">' for s in data["slides"])
        faits = "".join(
            f'<li>{e["annee"]} — <a href="{html.escape(e.get("url", ""))}">'
            f'{html.escape(e["titre"])}</a></li>' for e in data["evenements"])
        sections.append(
            f'<section><h2>{data["date"]}</h2>'
            f'<div class="pellicule">{vignettes}</div><ul>{faits}</ul></section>')
    (docs / "index.html").write_text(
        GABARIT.format(titre=cfg["page"]["nom"], baseline=cfg["page"]["baseline"],
                       corps="".join(sections)), "utf-8")
