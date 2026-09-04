"""Legende Instagram : accroche, sommaire, credits photo, hashtags."""
from __future__ import annotations

from .images import credit_court
from .texte import date_longue

MAX = 2200


def construire(jour, evenements, cfg) -> str:
    lignes = [f"{cfg['page']['baseline'].upper()} — {date_longue(jour)}", ""]
    for e in evenements:
        lignes.append(f"{e.annee} · {e.titre}")
    lignes += ["", "Lequel de ces événements connaissais-tu ? Réponds en commentaire.",
               "Enregistre le carrousel pour le relire.", ""]

    credits = [f"{e.annee} : {credit_court(e.photo)}" for e in evenements if e.photo]
    if credits:
        lignes.append("Crédits photo (libres de droit) :")
        lignes += credits
        lignes.append("")
    lignes.append("Source des faits : Wikipédia FR.")
    lignes.append("")
    lignes.append(" ".join("#" + h for h in cfg["publication"]["hashtags"]))

    texte = "\n".join(lignes)
    if len(texte) > MAX:                      # on sacrifie les credits detailles avant les hashtags
        sans_credits = [l for l in lignes if not l.startswith(tuple(str(e.annee) + " :" for e in evenements))]
        texte = "\n".join(sans_credits)[:MAX]
    return texte
