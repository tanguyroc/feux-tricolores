from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time

import requests

log = logging.getLogger("feux.loaders")

USER_AGENT = "feux-tricolores/0.1 (outil personnel; contact: voir README)"
TIMEOUT = 60
# Hôtes pour lesquels `requests` échoue derrière certains proxies alors que curl --http1.1 passe.
PREFER_CURL_HOSTS = ("fred.stlouisfed.org",)


def http_get(url: str, retries: int = 3, **kwargs) -> requests.Response:
    """GET avec 3 tentatives (les proxies et FRED ont des hoquets) ; lève après la dernière."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)
    timeout = kwargs.pop("timeout", TIMEOUT)
    last_exc: Exception | None = None
    if any(h in url for h in PREFER_CURL_HOSTS):
        fb = _curl_fallback(url, headers, timeout)
        if fb is not None:
            return fb
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"{r.status_code} pour {url}", response=r)
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_exc = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise  # erreur client : inutile de réessayer
            log.warning("Tentative %d/%d échouée pour %s : %s", attempt + 1, retries, url, str(exc)[:160])
            if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
                fb = _curl_fallback(url, headers, timeout)
                if fb is not None:
                    return fb
            time.sleep(2 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


class _CurlResponse:
    """Réponse minimale (content/text/json) quand `requests` n'arrive pas à traverser le proxy local."""

    def __init__(self, content: bytes, status_code: int):
        self.content = content
        self.status_code = status_code

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.text)


def _curl_fallback(url: str, headers: dict, timeout: int):
    """Certains environnements (proxy d'agent) coupent les tunnels de `requests` vers quelques hôtes
    alors que curl passe. On n'en fait un repli que sur erreur de connexion, jamais sur un 4xx."""
    if shutil.which("curl") is None:
        return None
    # curl s'identifie comme curl (pas d'usurpation d'agent utilisateur)
    cmd = ["curl", "-sS", "-L", "--http1.1", "-m", str(timeout), "-w", "\n%{http_code}", url]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout + 10, check=False).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None
    body, _, code = out.rpartition(b"\n")
    try:
        status = int(code.strip() or 0)
    except ValueError:
        return None
    if status != 200:
        log.warning("Repli curl : HTTP %s pour %s", status, url)
        return None
    log.info("Repli curl réussi pour %s (%d octets)", url, len(body))
    return _CurlResponse(body, status)
