"""Couche HTTP unique : User-Agent conforme aux règles Wikimedia + retries."""
from __future__ import annotations

import os
import time
import logging
from typing import Any

import requests

log = logging.getLogger("net")

CONTACT = os.environ.get("CONTACT_EMAIL", "contact@example.com")
UA = f"DatesHistoireBot/1.0 (page Instagram automatisee; {CONTACT}) python-requests"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        _session = s
    return _session


def get_json(url: str, params: dict | None = None, tries: int = 3, timeout: int = 25) -> Any:
    last = None
    for i in range(tries):
        try:
            r = session().get(url, params=params, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("GET %s a echoue (%s/%s) : %s", url, i + 1, tries, e)
            time.sleep(1.5 * (i + 1))
    log.warning("GET %s abandonne : %s", url, last)
    return None


def get_bytes(url: str, tries: int = 3, timeout: int = 40) -> bytes | None:
    for i in range(tries):
        try:
            r = session().get(url, timeout=timeout, headers={"Accept": "*/*"})
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            log.warning("Telechargement %s echoue (%s/%s) : %s", url, i + 1, tries, e)
            time.sleep(1.5 * (i + 1))
    return None
