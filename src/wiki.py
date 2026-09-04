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


GENERIQUES = re.compile(
    r"^(France|États-Unis|Etats-Unis|Royaume-Uni|Allemagne|Italie|Espagne|Russie|Chine|"
    r"Japon|Europe|Afrique|Asie|Amérique|Paris|Londres|New York|Union européenne|"
    r"Empire|Guerre mondiale)\b", re.I)


def _mots(t: str) -> set[str]:
    return {m.lower() for m in re.findall(r"[A-Za-zÀ-ÿ]{5,}", t)}


def _page_de(ev: dict) -> dict | None:
    """La page qui parle vraiment de l'evenement, pas le pays ou il s'est produit.

    Le flux Wikipedia lie plusieurs articles a un meme fait ; prendre le premier
    qui porte une image faisait remonter « France » ou « Etats-Unis », dont la
    frequentation enorme faussait ensuite le classement.
    """
    pages = ev.get("pages") or []
    if not pages:
        return None
    fait = _mots(ev.get("text", ""))
    notes = []
    for i, p in enumerate(pages):
        titre = p.get("normalizedtitle") or p.get("title", "")
        n = len(fait & _mots(titre)) * 2.0
        n += 1.0 if (p.get("originalimage") or p.get("thumbnail")) else 0.0
        n += 0.6 if len(p.get("extract") or "") > 200 else 0.0
        n -= 4.0 if GENERIQUES.match(titre) else 0.0
        n -= i * 0.4
        notes.append((n, i, p))
    return max(notes, key=lambda x: (x[0], -x[1]))[2]


def _illustration(ev: dict, page: dict) -> str | None:
    """L'image de la page de reference, sinon celle d'une autre page du meme fait."""
    for p in [page] + list(ev.get("pages") or []):
        src = (p.get("originalimage") or {}).get("source") or (p.get("thumbnail") or {}).get("source")
        if src:
            return src
    return None


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
                image_source=_illustration(ev, page),
                selectionne=(kind == "selected"),
            )
            if e.cle in brut:
                brut[e.cle].selectionne |= e.selectionne
            elif e.texte and e.titre_page:
                brut[e.cle] = e
    log.info("%s evenements bruts pour le %s", len(brut), jour.strftime("%d/%m"))
    return list(brut.values())


INTRO = "https://fr.wikipedia.org/w/api.php"


def enrichir(evenements: list[Evenement]) -> None:
    """Recupere l'introduction complete des articles retenus.

    Le flux 'onthisday' ne donne que 1 a 3 phrases, presque toujours la definition
    du sujet (« Los Angeles est la deuxieme plus grande ville... »). L'introduction
    complete contient en general le passage qui parle vraiment de l'evenement.
    """
    if not evenements:
        return
    titres = "|".join(e.titre_page for e in evenements[:20])
    data = get_json(INTRO, {"action": "query", "format": "json", "formatversion": "2",
                            "prop": "extracts", "exintro": "1", "explaintext": "1",
                            "redirects": "1", "titles": titres})
    pages = ((data or {}).get("query") or {}).get("pages") or []
    par_titre = {p.get("title", ""): (p.get("extract") or "") for p in pages}
    for e in evenements:
        texte_long = par_titre.get(e.titre_page, "")
        if len(texte_long) > len(e.extrait):
            e.extrait = texte_long
            log.info("%s : introduction complete (%s caracteres)", e.annee, len(texte_long))


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
