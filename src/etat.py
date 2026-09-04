"""Memoire des publications : evite de reproposer les memes evenements l'annee suivante."""
from __future__ import annotations

import json
from pathlib import Path

FICHIER = Path(__file__).resolve().parent.parent / "state" / "publie.json"


def charger() -> dict:
    if FICHIER.exists():
        try:
            return json.loads(FICHIER.read_text("utf-8"))
        except json.JSONDecodeError:
            pass
    return {"jours": {}}


def deja_publies(jour) -> set[str]:
    etat = charger()
    cles: set[str] = set()
    for j in etat["jours"].values():
        if j.get("mmdd") == jour.strftime("%m-%d"):
            cles.update(j.get("evenements", []))
    return cles


def enregistrer(jour, evenements, post_id: str | None) -> None:
    etat = charger()
    etat["jours"][jour.isoformat()] = {
        "mmdd": jour.strftime("%m-%d"),
        "evenements": [e.cle for e in evenements],
        "post_id": post_id,
    }
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(etat, ensure_ascii=False, indent=1), "utf-8")
