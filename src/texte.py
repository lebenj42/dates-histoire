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
    t = re.sub(r"\[[^\]]{0,120}\]", "", t)             # notes et transcriptions phonetiques
    t = re.sub(r"\s*\((?:photo|image|illustration|illustré|en photo)\)", "", t, flags=re.I)
    t = re.sub(r"\s*\((?:[^()]*?(?:écouter|prononc|API|/[^/]+/)[^()]*?)\)", "", t)
    t = re.sub(r"\s*\(\s*\)", "", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
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


_DEFINITION = re.compile(
    r"^[^,]{0,60}\b(?:est|était|sont|fut)\s+(?:un|une|le|la|l'|les|l\u2019)\b|"
    r"\bné(?:e)?\s+le\b|\bmort(?:e)?\s+le\b|\bsouvent\s+abrégé\b|"
    r"\ben\s+forme\s+longue\b", re.I)

_VIDES = {"dans", "avec", "pour", "cette", "leurs", "entre", "ainsi", "selon",
          "depuis", "apres", "après", "elles", "celui", "celle", "plus", "sont",
          "etre", "être", "leur", "meme", "même"}


def _mots_cles(t: str) -> set[str]:
    return {m.lower() for m in re.findall(r"[A-Za-zÀ-ÿ]{6,}", t)} - _VIDES


def resume(ev, maxi: int = 240) -> str:
    """Les phrases de l'article qui parlent de l'EVENEMENT, pas la definition du sujet.

    Sans cle Claude, c'est une heuristique : on privilegie les phrases qui citent
    l'annee ou reprennent le vocabulaire du fait, et on ecarte les phrases de
    definition (« X est un navigateur britannique ne le... »).
    """
    ph = phrases(ev.extrait or ev.texte)
    if not ph:
        return _couper(_nettoyer(ev.description or ev.texte), maxi)

    cles = _mots_cles(ev.texte)
    annee = str(ev.annee)
    notes = []
    for i, phrase in enumerate(ph):
        n = 3.0 if annee in phrase else 0.0
        n += len(cles & _mots_cles(phrase)) * 1.2
        if re.search(r"\b(fond|cré|proclam|élu|élue|signé|adopt|inaugur|découvr|"
                     r"aperç|conclu|renvers|abdiqu|promulg|lanc|ouvr)", phrase, re.I):
            n += 1.5                          # phrases qui racontent un fait, pas un etat
        if _DEFINITION.search(phrase):
            n -= 2.5
        n -= i * 0.15                       # a egalite, le debut de l'article
        notes.append((n, i, phrase))

    # on place d'abord la meilleure phrase, puis on complete tant que ca tient :
    # sinon une phrase de definition, souvent la premiere, mange tout le budget.
    retenues, place = [], 0
    for note, i, phrase in sorted(notes, key=lambda x: -x[0]):
        if len(retenues) >= 3:
            break
        cout = len(phrase) + (1 if retenues else 0)
        if place + cout > maxi:
            continue
        if note < 0 and retenues:
            break                            # pas de remplissage avec du hors-sujet
        retenues.append((i, phrase))
        place += cout

    if not retenues:
        return _couper(max(notes, key=lambda x: x[0])[2], maxi)
    return " ".join(p for _, p in sorted(retenues))


def habiller(evenements, cfg) -> None:
    for e in evenements:
        e.titre = titre(e, cfg["contenu"]["titre_max_caracteres"])
        e.resume = resume(e, cfg["contenu"]["resume_max_caracteres"])
    if omniroute_url(cfg):
        _polir_llm(evenements, cfg, _appel_omniroute, "OmniRoute")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        _polir_llm(evenements, cfg, _appel_anthropic, "Claude")


def omniroute_url(cfg) -> str:
    """URL de la passerelle OmniRoute (ex. http://localhost:20128/v1), ou "" si absente."""
    url = os.environ.get("OMNIROUTE_BASE_URL") or (cfg.get("llm") or {}).get("omniroute_url") or ""
    return url.rstrip("/")


def _appel_omniroute(consigne: str, cfg) -> str:
    """OmniRoute parle le format OpenAI : POST {base}/chat/completions."""
    import requests
    llm = cfg.get("llm") or {}
    entetes = {"Content-Type": "application/json"}
    if os.environ.get("OMNIROUTE_API_KEY"):    # inutile en local, utile si la passerelle est exposee
        entetes["Authorization"] = f"Bearer {os.environ['OMNIROUTE_API_KEY']}"
    r = requests.post(
        f"{omniroute_url(cfg)}/chat/completions",
        headers=entetes,
        json={"model": os.environ.get("OMNIROUTE_MODEL") or llm.get("modele") or "auto",
              "max_tokens": 2000,
              "messages": [{"role": "user", "content": consigne}]},
        timeout=llm.get("timeout", 120),
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _appel_anthropic(consigne: str, cfg) -> str:
    import anthropic  # type: ignore
    rep = anthropic.Anthropic().messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=2000,
        messages=[{"role": "user", "content": consigne}],
    )
    return rep.content[0].text


def _polir_llm(evenements, cfg, appel, nom: str) -> None:
    """Optionnel : reecriture des titres/resumes par un LLM. Sans LLM, on garde les regles."""
    charge = [{"i": i, "annee": e.annee, "fait": e.texte, "contexte": e.extrait[:600]}
              for i, e in enumerate(evenements)]
    consigne = (
        "Tu rediges les slides d'un carrousel Instagram d'histoire, en francais, ton factuel et "
        "vivant, sans emphase ni superlatif, sans emoji, sans inventer le moindre fait : tu ne peux "
        "utiliser que ce qui figure dans 'fait' et 'contexte'.\n"
        "Le resume doit parler de L'EVENEMENT (ce qui s'est passe cette annee-la, pourquoi cela "
        "compte, ce que cela a change), jamais definir le sujet : « Los Angeles est la deuxieme "
        "ville des Etats-Unis » est un mauvais resume pour la fondation de 1781. Si le contexte "
        "n'apporte rien sur l'evenement, developpe le fait lui-meme plutot que de decrire le sujet.\n"
        f"Pour chaque entree : 'titre' de {cfg['contenu']['titre_max_caracteres']} caracteres maximum "
        "(pas de point final, pas de date dans le titre) et 'resume' de "
        f"{cfg['contenu']['resume_max_caracteres']} caracteres maximum (1 a 3 phrases completes qui "
        "expliquent l'enjeu ou la consequence).\n"
        "Reponds uniquement par un tableau JSON [{\"i\":0,\"titre\":\"...\",\"resume\":\"...\"}].\n\n"
        + json.dumps(charge, ensure_ascii=False)
    )
    try:
        txt = appel(consigne, cfg).strip()
        txt = txt[txt.find("["): txt.rfind("]") + 1]
        for item in json.loads(txt):
            e = evenements[int(item["i"])]
            if item.get("titre"):
                e.titre = _couper(item["titre"].strip().rstrip("."), cfg["contenu"]["titre_max_caracteres"])
            if item.get("resume"):
                e.resume = _couper(item["resume"].strip(), cfg["contenu"]["resume_max_caracteres"])
        log.info("Titres et resumes affines par %s", nom)
    except Exception as exc:  # noqa: BLE001
        log.warning("Reecriture LLM ignoree (%s) : on garde la version automatique", exc)


def date_longue(jour) -> str:
    return f"{jour.day if jour.day > 1 else '1er'} {MOIS_FR[jour.month - 1]}"
