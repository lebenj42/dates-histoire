#!/usr/bin/env python3
"""Page "Ce jour dans l'histoire" — generation et publication automatiques.

  python run.py generer                 # fabrique le carrousel du jour dans docs/AAAA-MM-JJ/
  python run.py generer --date 1969-07-20
  python run.py publier --base-url https://raw.githubusercontent.com/moi/depot/main/docs
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import archive, etat, images, legende, rendu, texte, wiki  # noqa: E402

RACINE = Path(__file__).resolve().parent
DOCS = RACINE / "docs"
CACHE = RACINE / "out" / "cache"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-9s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("run")


def config() -> dict:
    return yaml.safe_load((RACINE / "config.yaml").read_text("utf-8"))


def aujourdhui_paris() -> dt.date:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    except Exception:  # noqa: BLE001
        return dt.datetime.utcnow().date()


def heure_paris() -> int:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Paris")).hour
    except Exception:  # noqa: BLE001
        return dt.datetime.utcnow().hour


# ── generation ──────────────────────────────────────────────────────────────

def generer(jour: dt.date, cfg: dict, fixture: Path | None = None,
            sans_photos: bool = False) -> dict:
    if fixture:
        evenements = _depuis_fixture(fixture)
    else:
        evenements = wiki.collecter(jour)
        if not evenements:
            raise SystemExit("Aucun evenement recupere : Wikipedia injoignable ?")
        wiki.mesurer_notoriete(evenements)
        evenements = wiki.classer(evenements, cfg["contenu"]["nb_evenements"],
                                  cfg["contenu"]["max_par_decennie"],
                                  etat.deja_publies(jour))
    texte.habiller(evenements, cfg)
    if not sans_photos:
        images.illustrer(evenements, cfg, CACHE)

    dossier = DOCS / jour.isoformat()
    chemins = rendu.carrousel(jour, evenements, cfg, dossier)
    manifeste = {
        "date": jour.isoformat(),
        "genere_le": dt.datetime.now().isoformat(timespec="seconds"),
        "slides": [p.name for p in chemins],
        "legende": legende.construire(jour, evenements, cfg),
        "evenements": [{"annee": e.annee, "titre": e.titre, "resume": e.resume,
                        "cle": e.cle, "vues_wikipedia": e.vues, "score": e.score,
                        "url": e.url_page, "photo": {k: v for k, v in e.photo.items()
                                                     if k != "fichier"}}
                       for e in evenements],
    }
    (dossier / "manifest.json").write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=1), "utf-8")
    archive.construire(DOCS, cfg)
    log.info("Carrousel du %s pret (%s slides)", jour, len(chemins))
    return manifeste


def _depuis_fixture(chemin: Path) -> list:
    data = json.loads(chemin.read_text("utf-8"))
    out = []
    for e in data:
        ev = wiki.Evenement(
            annee=e["annee"], texte=e["texte"], titre_page=e["titre_page"],
            extrait=e.get("extrait", ""), description=e.get("description", ""),
            url_page=e.get("url_page", ""), image_source=None, selectionne=True,
            vues=e.get("vues", 0))
        photo = dict(e.get("photo", {}))
        if photo.get("fichier") and not Path(photo["fichier"]).is_absolute():
            photo["fichier"] = str(RACINE / photo["fichier"])
        ev.photo = photo
        out.append(ev)
    return out


# ── publication ─────────────────────────────────────────────────────────────

def publier(jour: dt.date, cfg: dict, base_url: str, essai: bool) -> None:
    dossier = DOCS / jour.isoformat()
    manifeste = json.loads((dossier / "manifest.json").read_text("utf-8"))
    urls = [f"{base_url.rstrip('/')}/{jour.isoformat()}/{n}" for n in manifeste["slides"]]
    if essai:
        log.info("Mode essai — rien n'est publie.\n%s\n\nLegende :\n%s",
                 "\n".join(urls), manifeste["legende"])
        return
    from src.instagram import Instagram
    post_id = Instagram(cfg).publier_carrousel(urls, manifeste["legende"])
    manifeste["post_id"] = post_id
    (dossier / "manifest.json").write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=1), "utf-8")

    class _E:  # pour l'ecriture d'etat
        def __init__(self, cle): self.cle = cle
    etat.enregistrer(jour, [_E(e["cle"]) for e in manifeste["evenements"]], post_id)


# ── cli ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="commande", required=True)

    g = sp.add_parser("generer", help="fabrique le carrousel")
    g.add_argument("--date")
    g.add_argument("--fixture", type=Path, help="jeu d'essai hors ligne")
    g.add_argument("--sans-photos", action="store_true")

    b = sp.add_parser("publier", help="publie le carrousel deja genere")
    b.add_argument("--date")
    b.add_argument("--base-url", required=True)
    b.add_argument("--essai", action="store_true", help="affiche sans publier")
    b.add_argument("--garde-heure", type=int, default=None,
                   help="ne publie que si l'heure de Paris correspond")

    a = p.parse_args()
    cfg = config()
    jour = dt.date.fromisoformat(a.date) if a.date else aujourdhui_paris()

    if a.commande == "generer":
        generer(jour, cfg, a.fixture, a.sans_photos)
    else:
        if a.garde_heure is not None and heure_paris() != a.garde_heure:
            log.info("Il est %sh a Paris, publication prevue a %sh : on ne fait rien.",
                     heure_paris(), a.garde_heure)
            return
        publier(jour, cfg, a.base_url, a.essai)


if __name__ == "__main__":
    main()
