"""Test de fumée de l'application (JavaScript exécuté dans jsdom) : lancé si node et jsdom sont disponibles.

Installation locale : npm install --prefix /chemin jsdom@24, puis JSDOM_PATH=/chemin/node_modules python -m pytest.
Le workflow quotidien l'exécute avant toute publication."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _jsdom() -> str | None:
    for p in (os.environ.get("JSDOM_PATH"), str(ROOT / "node_modules")):
        if p and (Path(p) / "jsdom").exists():
            return p
    return None


@pytest.mark.skipif(shutil.which("node") is None or _jsdom() is None, reason="node ou jsdom absent")
def test_page_runs_without_javascript_errors():
    r = subprocess.run(["node", str(ROOT / "tests" / "page_smoke.js"), str(ROOT / "docs" / "index.html")],
                       env={**os.environ, "NODE_PATH": _jsdom()}, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr + r.stdout
