"""Services of the Doctrines plugin: the fitting parser (pure), EVE type lookups, prices, insurance."""

import time

import requests

USER_AGENT = "orlov-auth doctrines (Alliance Auth plugin, auth.orlovfamily.space)"
ESI_BASE = "https://esi.evetech.net/latest"
_session = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return _session


def get_json(url: str, params=None, timeout: int = 30):
    r = session().get(url, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post_json(url: str, payload, params=None, timeout: int = 30):
    r = session().post(url, json=payload, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def polite_pause(seconds: float = 0.2) -> None:
    time.sleep(seconds)
