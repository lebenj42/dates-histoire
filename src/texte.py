"""Fabrication du titre et du resume de chaque evenement (francais)."""
from __future__ import annotations

import json
import logging
import os
import re

log = logging.getLogger("texte")

MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

# Abreviations frequentes derriere lesquelles un point ne termine pas la phrase.
_ABBR = (r"(?<!\bav\.)(?<!\bapr\.)(?<!\bJ\.-C\.)(?<!\bM\.)(?<!\bMme\.)(?<!\bMgr\.)"
         r"(?<!\bSt\.)(?<!\bSte\.)(?<!\bno\.)(?<!\bcf\.)(?<!\benv\.)(?<!\bvs\.)"
         r"(?<!\bca\.)(?<!\bfig\.)(?<!\bt\.)(?<!\bp\.)")
_FIN_PHRASE = re.compile(_ABBR + r"(?<=[.!?])\s+(?=[A-ZÉÈÀÂÎÔÛÇ«\"0-9])")


def _nettoyer(t: str) -> str:
    t = re.sub(r"\[\d+\]", "", t)                      # appels de note
    t = re.sub(r"\s*\((?:[^()]*?(?:écouter|prononc|API|/[^/]+/)[^()]*?)\)", "", t)
    t = re.sub(r"\s*\(\s*\)", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def phrases(t: str) -> list[str]:
    t = _nettoyer(t)
    return [p.strip() for p in _FIN_PHRASE.split(t) if p.strip()]


def _couper(t: str, maxi: int) -> str:
    if len(t) <= maxi:
        return t
    coupe = t[:maxi]
    for sep in (" — ", ", ", " : ", " "):
        i = coupe.rfind(sep)
        if i > maxi * 0.55:
            return coupe[:i].rstrip(" ,;:—-") + "…"
    return coupe.rstrip() + "…"


def titre(ev, maxi: int = 72) -> str:
    t = _nettoyer(ev.texte).rstrip(".")
    t = re.sub(r"^(?:le |la |les |l')?(?=\w)", lambda m: m.group(0), t)
    t = t[0].upper() + t[1:] if t else ev.titre_page
    return _couper(t, maxi)


def resume(ev, maxi: int = 240) -> str:
    """2 a 3 phrases de contexte, tirees de l'article, jamais une redite du titre."""
    source = ev.extrait or ev.texte
    ph = phrases(source)
    if not ph:
        return _couper(_nettoyer(ev.description or ev.texte), maxi)
    out = ""
    for p in ph:
        if len(out) + len(p) + 1 > maxi:
            break
        out = (out + " " + p).strip()
    if not out:
        out = _couper(ph[0], maxi)
    return out


def habiller(evenements, cfg) -> None:
    for e in evenements:
        e.titre = titre(e, cfg["contenu"]["titre_max_caracteres"])
        e.resume = resume(e, cfg["contenu"]["resume_max_caracteres"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        _polir_llm(evenements, cfg)


def _polir_llm(evenements, cfg) -> None:
    """Optionnel : reecriture des titres/resumes par Claude. Sans cle, on garde les regles."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        return
    charge = [{"i": i, "annee": e.annee, "fait": e.texte, "contexte": e.extrait[:600]}
              for i, e in enumerate(evenements)]
    consigne = (
        "Tu rediges les slides d'un carrousel Instagram d'histoire, en francais, ton factuel et "
        "vivant, sans emphase ni superlatif, sans emoji, sans inventer le moindre fait : tu ne peux "
        "utiliser que ce qui figure dans 'fait' et 'contexte'.\n"
        f"Pour chaque entree : 'titre' de {cfg['contenu']['titre_max_caracteres']} caracteres maximum "
        "(pas de point final, pas de date dans le titre) et 'resume' de "
        f"{cfg['contenu']['resume_max_caracteres']} caracteres maximum (1 a 3 phrases completes qui "
        "expliquent l'enjeu ou la consequence).\n"
        "Reponds uniquement par un tableau JSON [{\"i\":0,\"titre\":\"...\",\"resume\":\"...\"}].\n\n"
        + json.dumps(charge, ensure_ascii=False)
    )
    try:
        client = anthropic.Anthropic()
        rep = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            max_tokens=2000,
            messages=[{"role": "user", "content": consigne}],
        )
        txt = rep.content[0].text.strip()
        txt = txt[txt.find("["): txt.rfind("]") + 1]
        for item in json.loads(txt):
            e = evenements[int(item["i"])]
            if item.get("titre"):
                e.titre = _couper(item["titre"].strip().rstrip("."), cfg["contenu"]["titre_max_caracteres"])
            if item.get("resume"):
                e.resume = _couper(item["resume"].strip(), cfg["contenu"]["resume_max_caracteres"])
        log.info("Titres et resumes affines par Claude")
    except Exception as exc:  # noqa: BLE001
        log.warning("Reecriture LLM ignoree (%s) : on garde la version automatique", exc)


def date_longue(jour) -> str:
    return f"{jour.day if jour.day > 1 else '1er'} {MOIS_FR[jour.month - 1]}"
