"""Recuperation et classement des evenements du jour (Wikipedia FR)."""
from __future__ import annotations

import datetime as dt
import logging
import math
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from .net import get_json

log = logging.getLogger("wiki")

FEED = "https://fr.wikipedia.org/api/rest_v1/feed/onthisday/{kind}/{mm}/{dd}"
PAGEVIEWS = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "fr.wikipedia/all-access/user/{title}/monthly/{start}/{end}"
)


@dataclass
class Evenement:
    annee: int
    texte: str
    titre_page: str
    extrait: str
    description: str
    url_page: str
    image_source: str | None      # URL de l'image d'illustration Wikipedia (souvent Commons)
    selectionne: bool             # present dans le flux "selected" (evenements phares)
    vues: int = 0
    score: float = 0.0
    photo: dict = field(default_factory=dict)   # rempli par images.py
    titre: str = ""                             # rempli par texte.py
    resume: str = ""

    @property
    def cle(self) -> str:
        return f"{self.annee}|{self.titre_page}"


def _page_de(ev: dict) -> dict | None:
    """La page la plus pertinente d'un evenement : celle qui a une illustration."""
    pages = ev.get("pages") or []
    if not pages:
        return None
    avec_image = [p for p in pages if p.get("originalimage") or p.get("thumbnail")]
    return (avec_image or pages)[0]


def _feed(kind: str, jour: dt.date) -> list[dict]:
    data = get_json(FEED.format(kind=kind, mm=f"{jour.month:02d}", dd=f"{jour.day:02d}"))
    if not data:
        return []
    return data.get(kind) or data.get("events") or []


def collecter(jour: dt.date) -> list[Evenement]:
    """Fusionne les flux 'selected' (evenements phares) et 'events' (exhaustif)."""
    brut: dict[str, Evenement] = {}
    for kind in ("selected", "events"):
        for ev in _feed(kind, jour):
            page = _page_de(ev)
            if not page or not isinstance(ev.get("year"), int):
                continue
            e = Evenement(
                annee=ev["year"],
                texte=(ev.get("text") or "").strip(),
                titre_page=page.get("normalizedtitle") or page.get("title", ""),
                extrait=(page.get("extract") or "").strip(),
                description=(page.get("description") or "").strip(),
                url_page=(page.get("content_urls", {}).get("desktop", {}).get("page") or ""),
                image_source=(page.get("originalimage") or {}).get("source")
                or (page.get("thumbnail") or {}).get("source"),
                selectionne=(kind == "selected"),
            )
            if e.cle in brut:
                brut[e.cle].selectionne |= e.selectionne
            elif e.texte and e.titre_page:
                brut[e.cle] = e
    log.info("%s evenements bruts pour le %s", len(brut), jour.strftime("%d/%m"))
    return list(brut.values())


def _mois_complets(n: int = 3) -> tuple[str, str]:
    fin = dt.date.today().replace(day=1) - dt.timedelta(days=1)
    debut = fin.replace(day=1)
    for _ in range(n - 1):
        debut = (debut - dt.timedelta(days=1)).replace(day=1)
    return debut.strftime("%Y%m%d"), fin.strftime("%Y%m%d")


def mesurer_notoriete(evenements: list[Evenement]) -> None:
    """Vues mensuelles moyennes de l'article : proxy fiable de 'evenement majeur'."""
    debut, fin = _mois_complets()
    for e in evenements:
        titre = quote(e.titre_page.replace(" ", "_"), safe="")
        data = get_json(PAGEVIEWS.format(title=titre, start=debut, end=fin), tries=2)
        items = (data or {}).get("items") or []
        e.vues = int(sum(i["views"] for i in items) / len(items)) if items else 0


def _score(e: Evenement) -> float:
    s = math.log10(max(e.vues, 1) + 1) * 2.0
    if e.selectionne:
        s += 2.5
    if e.image_source:
        s += 1.5
    if len(e.extrait) > 200:
        s += 0.5
    if len(e.texte) < 25:
        s -= 1.0
    return round(s, 3)


def classer(evenements: list[Evenement], nb: int, max_par_decennie: int = 2,
            deja_publies: set[str] | None = None) -> list[Evenement]:
    """Trie par notoriete, en evitant les repetitions d'annees et les redites."""
    deja_publies = deja_publies or set()
    for e in evenements:
        e.score = _score(e) - (1.5 if e.cle in deja_publies else 0.0)

    retenus: list[Evenement] = []
    decennies: dict[int, int] = {}
    titres_vus: set[str] = set()
    for e in sorted(evenements, key=lambda x: -x.score):
        if len(retenus) >= nb:
            break
        dec = e.annee // 10
        if decennies.get(dec, 0) >= max_par_decennie:
            continue
        if e.titre_page in titres_vus:
            continue
        retenus.append(e)
        titres_vus.add(e.titre_page)
        decennies[dec] = decennies.get(dec, 0) + 1

    retenus.sort(key=lambda x: x.annee)   # ordre chronologique dans le carrousel
    return retenus
