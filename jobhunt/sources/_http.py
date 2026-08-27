"""Minimal JSON fetch. Stdlib only, so the tool has no install step."""
import json, urllib.request, urllib.error

UA = "jobhunt/0.1 (personal job search; contact arscholtes@gmail.com)"


class FetchError(RuntimeError):
    pass


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise FetchError(f"{url} returned HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"{url} unreachable: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise FetchError(f"{url} did not return JSON") from e
