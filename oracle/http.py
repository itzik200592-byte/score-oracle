import hashlib, json, time, threading
import requests
from .config import CACHE

_S = requests.Session()
_S.headers.update({"User-Agent": "Mozilla/5.0"})
_lock = threading.Lock()


def cache_path(url, params=None, cache_key=None):
    key = hashlib.sha1((cache_key or (url + json.dumps(params or {}, sort_keys=True))).encode()).hexdigest()
    return CACHE / f"{key}.txt"


def get(url, params=None, headers=None, ttl_hours=6.0, sleep=0.0, tries=4, cache_key=None, offline=False):
    """Disk-cached GET returning text. ttl_hours=None means cache forever. Returns None on failure.
    cache_key: stable key independent of the URL (e.g. when an API key in the URL changes). offline: cache only."""
    f = cache_path(url, params, cache_key)
    if f.exists():
        age_h = (time.time() - f.stat().st_mtime) / 3600
        if ttl_hours is None or age_h < ttl_hours or offline:
            return f.read_text(encoding="utf-8")
    if offline:
        return None
    for i in range(tries):
        try:
            if sleep:
                time.sleep(sleep)
            r = _S.get(url, params=params, headers=headers, timeout=40)
            if r.status_code == 200:
                r.encoding = r.encoding or "utf-8"
                txt = r.content.decode("utf-8-sig", errors="replace")
                f.write_text(txt, encoding="utf-8")
                return txt
            if r.status_code == 429:
                time.sleep(4 * (i + 1))
                continue
            if r.status_code in (400, 403, 404):
                break
        except requests.RequestException:
            time.sleep(1.5 * (i + 1))
    return f.read_text(encoding="utf-8") if f.exists() else None  # stale beats nothing
