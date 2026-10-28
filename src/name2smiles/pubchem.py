"""Small, rate-limited PubChem PUG REST client.

The client is deliberately conservative: one shared rate limiter, bounded
retries, and no API key. PubChem asks programmatic users to stay at or below
five requests per second.
"""

from __future__ import annotations

import threading
import time
from typing import Iterable

import requests

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
VIEW_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
PROPERTIES = ",".join(
    [
        "MolecularFormula",
        "SMILES",
        "ConnectivitySMILES",
        "InChIKey",
        "IUPACName",
        "Charge",
        "HeavyAtomCount",
        "DefinedAtomStereoCount",
        "UndefinedAtomStereoCount",
        "BondStereoCount",
        "DefinedBondStereoCount",
        "UndefinedBondStereoCount",
    ]
)

_MIN_INTERVAL = 0.24
_RETRY_STATUS = {403, 429, 500, 502, 503, 504}
_SPLIT_STATUS = {400, 404, 414}

_lock = threading.Lock()
_last_request = 0.0
_session = requests.Session()
_session.headers.update({"User-Agent": "name2smiles-bench/0.1"})


def _throttle() -> None:
    global _last_request
    with _lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def request(url: str, *, timeout: int = 90, retries: int = 5) -> requests.Response | None:
    """GET a URL with throttling and exponential backoff.

    Returns the final response, or None when all retries fail.
    """
    for attempt in range(retries):
        _throttle()
        try:
            response = _session.get(url, timeout=timeout)
        except requests.RequestException:
            if attempt == retries - 1:
                return None
            time.sleep(2**attempt)
            continue

        if response.status_code in _RETRY_STATUS:
            if attempt == retries - 1:
                return response
            time.sleep(2**attempt)
            continue
        return response
    return None


def _chunks(items: list[int], size: int) -> Iterable[list[int]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _property_url(cids: list[int]) -> str:
    cid_text = ",".join(str(cid) for cid in cids)
    return f"{BASE}/compound/cid/{cid_text}/property/{PROPERTIES}/JSON"


def _fetch_property_batch(cids: list[int]) -> list[dict]:
    response = request(_property_url(cids))
    if response is None:
        return []
    if response.status_code == 200:
        try:
            return response.json()["PropertyTable"]["Properties"]
        except (KeyError, ValueError):
            return []
    if response.status_code in _SPLIT_STATUS and len(cids) > 1:
        middle = len(cids) // 2
        return _fetch_property_batch(cids[:middle]) + _fetch_property_batch(cids[middle:])
    return []


def fetch_properties(cids: list[int], *, batch_size: int = 200) -> list[dict]:
    """Fetch PubChem properties for one or more CIDs."""
    records: list[dict] = []
    for batch in _chunks(cids, batch_size):
        records.extend(_fetch_property_batch(batch))
    return records


def fetch_synonyms(cid: int) -> list[str]:
    """Return PubChem synonyms for one CID."""
    response = request(f"{BASE}/compound/cid/{cid}/synonyms/JSON")
    if response is None or response.status_code != 200:
        return []
    try:
        information = response.json()["InformationList"]["Information"]
    except (KeyError, ValueError):
        return []
    if not information:
        return []
    return list(information[0].get("Synonym", []))


def fetch_png(cid: int, *, size: int = 500) -> bytes | None:
    """Return PubChem's 2D PNG depiction."""
    url = f"{BASE}/compound/cid/{cid}/PNG?record_type=2d&image_size={size}x{size}"
    response = request(url, timeout=60)
    if response is None or response.status_code != 200:
        return None
    return response.content


def fetch_sdf(cid: int, *, record_type: str = "3d") -> str | None:
    """Return a PubChem SDF record, usually the 3D conformer."""
    url = f"{BASE}/compound/cid/{cid}/record/SDF?record_type={record_type}"
    response = request(url, timeout=90)
    if response is None or response.status_code != 200:
        return None
    return response.text


def fetch_create_date(cid: int) -> str | None:
    """Return the PubChem record creation date, if available."""
    url = f"{VIEW_BASE}/data/compound/{cid}/JSON?heading=Create%20Date"
    response = request(url)
    if response is None or response.status_code != 200:
        return None
    try:
        sections = response.json()["Record"]["Section"]
    except (KeyError, ValueError):
        return None
    for section in sections:
        for child in section.get("Section", []):
            if child.get("TOCHeading") == "Create Date":
                information = child.get("Information", [])
                if information:
                    return information[0].get("Value", {}).get("DateISO8601", [None])[0]
    return None
