"""Verification rapide, sans reseau : mise en page, decoupe du texte, legende.

    python tests/test_hors_ligne.py
Genere docs/2026-09-04/ a partir du jeu d'essai et controle le resultat.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import run  # noqa: E402
from src import texte  # noqa: E402

echecs = []


def verifier(condition, message):
    print(("  ok   " if condition else "  ECHEC ") + message)
    if not condition:
        echecs.append(message)


def main() -> int:
    cfg = run.config()
    jour = dt.date(2026, 9, 4)
    manifeste = run.generer(jour, cfg, RACINE / "tests" / "fixtures" / "jour_test.json")

    print("\nControles :")
    dossier = run.DOCS / jour.isoformat()
    verifier(len(manifeste["slides"]) == cfg["contenu"]["nb_evenements"] + 2,
             "8 slides (couverture + evenements + appel a l'action)")
    verifier(2 <= len(manifeste["slides"]) <= 10, "carrousel dans les limites Instagram")

    from PIL import Image
    for nom in manifeste["slides"]:
        img = Image.open(dossier / nom)
        if img.size != (cfg["design"]["largeur"], cfg["design"]["hauteur"]):
            verifier(False, f"{nom} au mauvais format : {img.size}")
            break
    else:
        verifier(True, "toutes les slides en 1080x1350 (4:5)")

    verifier(len(manifeste["legende"]) <= 2200, "legende sous la limite Instagram")
    verifier(all(len(e["titre"]) <= cfg["contenu"]["titre_max_caracteres"]
                 for e in manifeste["evenements"]), "titres a la bonne longueur")
    verifier(all(len(e["resume"]) <= cfg["contenu"]["resume_max_caracteres"]
                 for e in manifeste["evenements"]), "resumes a la bonne longueur")
    verifier(all(e["resume"] for e in manifeste["evenements"]), "aucun resume vide")
    verifier(len({e["annee"] for e in manifeste["evenements"]})
             == len(manifeste["evenements"]), "pas de doublon d'annee")
    verifier((run.DOCS / "index.html").exists(), "page d'archive regeneree")

    p = texte.phrases("Ne en 500 av. J.-C. a Athenes. Il meurt en 428. Fin.")
    verifier(len(p) == 3, f"decoupe des phrases francaises (obtenu {len(p)})")

    print(json.dumps(manifeste["evenements"][0], ensure_ascii=False, indent=1)[:400])
    print("\n" + ("TOUT EST BON" if not echecs else f"{len(echecs)} probleme(s)"))
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
