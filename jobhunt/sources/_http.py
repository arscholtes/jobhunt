"""What every adapter needs: a GET that returns JSON, and markup turned to words.

Stdlib only, so the tool has no install step.
"""
import html as htmlmod
import json
import re
import urllib.error
import urllib.request

TAG = re.compile(r"<[^>]+>")

UA = "jobhunt/0.1 (personal job search)"


class FetchError(RuntimeError):
    pass


def text(fragment):
    """Markup as the words a scorer can read.

    A description reaching scoring with its tags still on it is counted as text:
    every `strong` and `href` becomes a term the posting never said.

    @param fragment [String, nil] a snippet of HTML
    @return [String] plain text, whitespace collapsed
    """
    if not fragment:
        return ""
    plain = htmlmod.unescape(TAG.sub(" ", fragment)).replace("\xa0", " ")
    return " ".join(plain.split())


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
