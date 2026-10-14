import hashlib, json, time, threading
import requests
from .config import CACHE

_S = requests.Session()
_S.headers.update({"User-Agent": "Mozilla/5.0"})
_lock = threading.Lock()


def get(url, params=None, headers=None, ttl_hours=6.0, sleep=0.0, tries=4):
    """Disk-cached GET returning text. ttl_hours=None means cache forever. Returns None on failure."""
    key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.txt"
    if f.exists():
        age_h = (time.time() - f.stat().st_mtime) / 3600
        if ttl_hours is None or age_h < ttl_hours:
            return f.read_text(encoding="utf-8")
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
