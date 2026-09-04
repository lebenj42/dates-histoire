#!/usr/bin/env python3
"""Prolonge le jeton Instagram longue duree (60 jours) et l'ecrit dans le secret GitHub.

A lancer une fois par mois (le workflow s'en charge). Necessite IG_ACCESS_TOKEN et,
pour la mise a jour automatique du secret, GH_PAT (droit 'secrets: write' sur le depot).
"""
import os
import subprocess
import sys

import requests

token = os.environ["IG_ACCESS_TOKEN"]
r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
r.raise_for_status()
neuf = r.json()["access_token"]
print(f"Jeton prolonge, valide {r.json().get('expires_in', 0) // 86400} jours.")

if os.environ.get("GH_PAT"):
    env = {**os.environ, "GH_TOKEN": os.environ["GH_PAT"]}
    subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--body", neuf],
                   check=True, env=env)
    print("Secret IG_ACCESS_TOKEN mis a jour.")
else:
    print("GH_PAT absent : reporte ce jeton manuellement dans les secrets du depot.", file=sys.stderr)
