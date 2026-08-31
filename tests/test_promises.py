"""The claims the README makes, turned into checks.

Each test here corresponds to a sentence a reader is asked to believe. A promise
nothing verifies looks correct right up until someone tests it, which is the
moment it becomes expensive — so the sentence and its check live together.

These are structural assertions about the codebase rather than behavioural ones,
because that is the shape the claims take: "there is no send path" is a statement
about what the code contains, and only reading the code can falsify it.
"""

import ast
import sys
import unittest
from pathlib import Path
from typing import ClassVar

from jobhunt import cli, notify, store
from jobhunt.sources import ADAPTERS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACKAGE = ROOT / "jobhunt"


def runtime_modules():
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)


def calls_named(tree, names):
    """@return [Array<String>] the called attribute/function names matching `names`."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        label = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if label in names:
            found.append(label)
    return found


class NoSendPathTests(unittest.TestCase):
    """README: 'It never contacts an employer. There is no send path in the codebase.'"""

    # The only outbound destinations the tool is allowed to have: public job-board
    # JSON, and the user's own mail server for the digest.
    OUTBOUND_ALLOWED: ClassVar = {"jobhunt/sources/_http.py", "jobhunt/notify.py", "jobhunt/cadence.py"}

    def test_only_the_sanctioned_modules_open_the_network(self):
        offenders = []
        for path in runtime_modules():
            rel = str(path.relative_to(ROOT))
            src = path.read_text()
            if ("urlopen" in src or "http.client" in src or "smtplib" in src) \
                    and rel not in self.OUTBOUND_ALLOWED:
                offenders.append(rel)
        self.assertEqual(offenders, [], "new outbound path outside the sanctioned modules")

    def test_no_module_posts_anywhere(self):
        # An application is submitted with a POST. There is no POST.
        offenders = []
        for path in runtime_modules():
            src = path.read_text()
            for needle in ('method="POST"', "method='POST'", ".post(", "urlencode("):
                if needle in src:
                    offenders.append(f"{path.relative_to(ROOT)}: {needle}")
        self.assertEqual(offenders, [])

    def test_the_mail_path_sends_only_to_the_configured_recipient(self):
        src = (PACKAGE / "notify.py").read_text()
        self.assertIn("smtplib", src)
        # If a recipient could come from a posting, the tool could mail a company.
        self.assertNotIn("job[", src.split("def send")[-1].split("def ")[0])
        self.assertTrue(hasattr(notify, "send"))

    def test_no_apply_or_submit_entry_point_exists(self):
        parser_src = (PACKAGE / "cli.py").read_text()
        for verb in ('"apply"', '"submit"', '"send"'):
            self.assertNotIn(f'sub.add_parser({verb}', parser_src)
        self.assertTrue(hasattr(cli, "main"))


class ReadOnlyBoardsTests(unittest.TestCase):
    """README: 'Three job boards publish read-only JSON... jobhunt reads them directly.'"""

    def test_the_http_helper_only_ever_issues_a_get(self):
        src = (PACKAGE / "sources" / "_http.py").read_text()
        tree = ast.parse(src)
        # urllib.request.Request defaults to GET; anything else must name a method.
        self.assertNotIn("method=", src)
        self.assertTrue(calls_named(tree, {"urlopen"}))

    def test_no_adapter_bypasses_the_shared_helper(self):
        offenders = []
        for path in (PACKAGE / "sources").glob("*.py"):
            if path.name == "_http.py":
                continue
            if "urlopen" in path.read_text():
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [], "an adapter opening its own connection sidesteps the GET-only guarantee")

    def test_every_adapter_exposes_only_a_fetch(self):
        for name, mod in ADAPTERS.items():
            self.assertTrue(hasattr(mod, "fetch"), f"{name} has no fetch")
            self.assertFalse(hasattr(mod, "post"), f"{name} exposes a write path")


class NeverWritesCredentialsTests(unittest.TestCase):
    """notify.py: 'Credentials live in ~/.jobhunt-mail.toml, which this never writes.'"""

    def test_the_credentials_file_is_only_ever_opened_for_reading(self):
        src = (PACKAGE / "notify.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                mode = list(node.args[1:2])
                if mode and isinstance(mode[0], ast.Constant):
                    self.assertNotIn("w", str(mode[0].value),
                                     "notify opens a file for writing")

    def test_nothing_in_the_package_writes_the_credentials_path(self):
        offenders = []
        for path in runtime_modules():
            src = path.read_text()
            if "jobhunt-mail" not in src:
                continue
            for needle in ('"w"', "'w'", '"a"', "'a'", "write_text"):
                if needle in src:
                    offenders.append(f"{path.relative_to(ROOT)}: {needle}")
        self.assertEqual(offenders, [])


class DatabaseIsLocalTests(unittest.TestCase):
    """The store is one local sqlite file — nothing ships it anywhere."""

    def test_the_database_path_is_local_to_the_repo(self):
        self.assertIn("data", str(store.DB))
        self.assertFalse(str(store.DB).startswith("http"))


if __name__ == "__main__":
    unittest.main()
