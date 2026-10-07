"""Shared HTTP session for the external data APIs."""

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .. import app_settings

logger = logging.getLogger(__name__)

_session = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers["User-Agent"] = app_settings.SHIPYARD_USER_AGENT
        s.headers["Accept"] = "application/json"
        retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _session = s
    return _session


def get_json(url: str, params=None, timeout=None):
    r = session().get(url, params=params, timeout=timeout or app_settings.SHIPYARD_HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def polite_pause():
    time.sleep(app_settings.SHIPYARD_REQUEST_DELAY)
