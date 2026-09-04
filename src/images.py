"""Recherche d'illustrations libres de droit + tracabilite de la licence.

Ordre de priorite :
  1. l'illustration de l'article Wikipedia, si elle est hebergee sur Wikimedia Commons
     (Commons n'accepte que des fichiers libres, reutilisables commercialement ET modifiables) ;
  2. une recherche d'image sur Commons a partir du sujet ;
  3. Openverse, restreint aux licences CC0 / domaine public / CC BY
     (ni ND -- interdit de recadrer et d'incruster du texte -- ni SA -- contaminerait le carrousel) ;
  4. aucune photo : la slide bascule sur un fond typographique.
Toute image retenue repart avec son credit et sa licence, affiches sur la slide et en legende.
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

from .net import get_bytes, get_json

log = logging.getLogger("images")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
META = "LicenseShortName|LicenseUrl|Artist|Credit|AttributionRequired|Restrictions|UsageTerms"

INTERDITS = re.compile(r"(fair use|non-?free|copyright|tous droits)", re.I)
FICHIERS_INUTILES = re.compile(
    r"(blason|coat of arms|flag of|drapeau|logo|icon|\.svg$|\.ogv$|\.webm$|\.pdf$|"
    r"location map|carte de localisation|signature)", re.I)


def _nom_fichier(url: str) -> str | None:
    """Retrouve le nom du fichier Commons a partir d'une URL upload.wikimedia."""
    if "/wikipedia/commons/" not in url:
        return None                      # fichier local a fr.wikipedia => souvent non libre
    seg = url.split("/")
    if "/thumb/" in url:
        return unquote(seg[-2])
    return unquote(seg[-1])


def _texte_brut(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _photo_commons(page: dict, largeur_min: int) -> dict | None:
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None
    m = info.get("extmetadata") or {}
    licence = _texte_brut(m.get("LicenseShortName", {}).get("value", "")) or "Wikimedia Commons"
    if INTERDITS.search(licence):
        return None
    if info.get("mime") in ("image/svg+xml",) or (info.get("width") or 0) < largeur_min:
        return None
    auteur = _texte_brut(m.get("Artist", {}).get("value", "")) or "Auteur inconnu"
    auteur = auteur[:60]
    return {
        "url": info.get("thumburl") or info.get("url"),
        "auteur": auteur,
        "licence": licence,
        "licence_url": _texte_brut(m.get("LicenseUrl", {}).get("value", "")),
        "source": "Wikimedia Commons",
        "page": info.get("descriptionurl", ""),
        "restrictions": _texte_brut(m.get("Restrictions", {}).get("value", "")),
    }


def _commons_par_fichier(nom: str, largeur: int, largeur_min: int) -> dict | None:
    data = get_json(COMMONS_API, {
        "action": "query", "format": "json", "formatversion": "2",
        "titles": f"File:{nom}", "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": largeur,
        "iiextmetadatafilter": META,
    })
    pages = ((data or {}).get("query") or {}).get("pages") or []
    return _photo_commons(pages[0], largeur_min) if pages else None


def _commons_par_recherche(requete: str, largeur: int, largeur_min: int) -> dict | None:
    data = get_json(COMMONS_API, {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": f'filetype:bitmap {requete}',
        "gsrnamespace": "6", "gsrlimit": "8", "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": largeur,
        "iiextmetadatafilter": META,
    })
    pages = ((data or {}).get("query") or {}).get("pages") or []
    pages.sort(key=lambda p: p.get("index", 99))
    for p in pages:
        if FICHIERS_INUTILES.search(p.get("title", "")):
            continue
        photo = _photo_commons(p, largeur_min)
        if photo:
            return photo
    return None


def _openverse(requete: str, licences: str, largeur_min: int) -> dict | None:
    data = get_json(OPENVERSE, {"q": requete, "license": licences, "page_size": 8,
                                "mature": "false"}, tries=2)
    for r in (data or {}).get("results", []):
        if (r.get("width") or 0) < largeur_min or not r.get("url"):
            continue
        lic = f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip()
        if r.get("license") in ("pdm", "cc0"):
            lic = "Domaine public" if r["license"] == "pdm" else "CC0"
        return {
            "url": r["url"],
            "auteur": (r.get("creator") or "Auteur inconnu")[:60],
            "licence": lic,
            "licence_url": r.get("license_url", ""),
            "source": (r.get("source") or "Openverse").capitalize(),
            "page": r.get("foreign_landing_url", ""),
            "restrictions": "",
        }
    return None


def _telecharger(url: str, cache: Path) -> Path | None:
    cache.mkdir(parents=True, exist_ok=True)
    cible = cache / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
    if cible.exists():
        return cible
    brut = get_bytes(url)
    if not brut:
        return None
    try:
        img = Image.open(io.BytesIO(brut))
        img = img.convert("RGB")
        img.thumbnail((2000, 2000), Image.LANCZOS)
        img.save(cible, "JPEG", quality=92)
        return cible
    except Exception as e:  # noqa: BLE001
        log.warning("Image illisible (%s) : %s", url, e)
        return None


def illustrer(evenements, cfg, cache: Path) -> None:
    conf = cfg["images"]
    lmin = conf["largeur_min"]
    for e in evenements:
        if e.photo.get("fichier"):
            continue                      # photo deja fournie (jeu d'essai ou reprise)
        photo = None
        nom = _nom_fichier(e.image_source or "")
        if nom:
            photo = _commons_par_fichier(nom, 1600, lmin)
        if not photo:
            photo = _commons_par_recherche(e.titre_page, 1600, lmin)
        if not photo:
            photo = _openverse(e.titre_page, conf["openverse_licences"], lmin)
        if photo:
            chemin = _telecharger(photo["url"], cache)
            if chemin:
                photo["fichier"] = str(chemin)
                e.photo = photo
                log.info("%s : %s (%s, %s)", e.annee, photo["source"], photo["licence"],
                         photo["auteur"][:30])
                continue
        e.photo = {}
        log.info("%s : aucune photo libre trouvee, slide typographique", e.annee)


def credit_court(photo: dict) -> str:
    if not photo:
        return ""
    return f"{photo['auteur']} · {photo['licence']} · {photo['source']}"
