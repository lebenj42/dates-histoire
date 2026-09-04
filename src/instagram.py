"""Publication du carrousel via l'API officielle Instagram (Content Publishing API).

Fonctionne avec les deux configurations :
  - Instagram Login       -> api_base = https://graph.instagram.com  (recommande, jeton renouvelable)
  - Facebook Login / Page -> api_base = https://graph.facebook.com
Les images doivent etre accessibles publiquement : le workflow les publie d'abord
sur le depot (raw.githubusercontent.com) avant d'appeler l'API.
"""
from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger("instagram")


class Instagram:
    def __init__(self, cfg):
        p = cfg["publication"]
        self.base = f"{p['api_base']}/{p['api_version']}"
        self.uid = os.environ["IG_USER_ID"]
        self.token = os.environ["IG_ACCESS_TOKEN"]

    def _post(self, chemin: str, data: dict) -> dict:
        data = {**data, "access_token": self.token}
        r = requests.post(f"{self.base}/{chemin}", data=data, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Instagram {r.status_code} sur {chemin} : {r.text[:400]}")
        return r.json()

    def _statut(self, container: str) -> str:
        r = requests.get(f"{self.base}/{container}",
                         params={"fields": "status_code,status", "access_token": self.token},
                         timeout=30)
        return (r.json() or {}).get("status_code", "ERROR") if r.ok else "ERROR"

    def _attendre(self, container: str, limite: int = 120) -> None:
        debut = time.time()
        while time.time() - debut < limite:
            s = self._statut(container)
            if s == "FINISHED":
                return
            if s in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Conteneur {container} en echec ({s})")
            time.sleep(5)
        raise RuntimeError(f"Conteneur {container} toujours en traitement apres {limite}s")

    def publier_carrousel(self, urls: list[str], legende: str) -> str:
        if not 2 <= len(urls) <= 10:
            raise ValueError("Un carrousel Instagram accepte de 2 a 10 images")
        enfants = []
        for u in urls:
            rep = self._post("me/media" if "graph.instagram" in self.base else f"{self.uid}/media",
                             {"image_url": u, "is_carousel_item": "true"})
            enfants.append(rep["id"])
            log.info("Slide envoyee : %s", rep["id"])
        for c in enfants:
            self._attendre(c)

        chemin = "me/media" if "graph.instagram" in self.base else f"{self.uid}/media"
        parent = self._post(chemin, {"media_type": "CAROUSEL",
                                     "children": ",".join(enfants),
                                     "caption": legende})["id"]
        self._attendre(parent)
        pub = "me/media_publish" if "graph.instagram" in self.base else f"{self.uid}/media_publish"
        post = self._post(pub, {"creation_id": parent})
        log.info("Publie : %s", post.get("id"))
        return post.get("id", "")
