"""The repository is public, so identity stays in the ignored files.

Who the candidate is lives in resume.toml and profile.toml, which git ignores.
Code names no one. Two leaks reached the public history before this guard: a
profile backup committed by accident, and a contact address written into the
HTTP User-Agent.

The identity is read from the local resume.toml, so this file names no one. With
no resume.toml, as on CI, there is nothing to compare against and that test skips.
"""

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import resume


def personal(path):
    """Whether a path is the candidate's own: facts, profile and their backups, the
    beads issue export, or the run's database and output. The examples are not.

    @param path [str] a repo-relative path
    @return [bool]
    """
    if path in ("resume.example.toml", "profile.example.toml"):
        return False
    return path.startswith(("resume.toml", "profile.toml", "data/", "out/")) or path == ".beads/issues.jsonl"


def git(*args):
    return subprocess.run(["git", "-C", str(resume.ROOT), *args], capture_output=True, text=True, check=False)


def identity(me):
    """The strings that identify the candidate: name, surname, email, phone, GitHub handle.

    @param me [dict] the [me] table of resume.toml
    @return [list[str]] non-empty identifiers
    """
    terms = [me.get("name"), me.get("email"), me.get("phone")]
    if me.get("name"):
        terms.append(me["name"].split()[-1])
    if me.get("github"):
        terms.append(me["github"].rstrip("/").rsplit("/", 1)[-1])
    return [t for t in terms if t]


class StagedFilesTests(unittest.TestCase):
    def test_no_staged_text_file_contains_the_resume_identity(self):
        if not resume.PATH.exists():
            self.skipTest("no resume.toml to read an identity from")
        terms = identity(resume.load()["me"])
        args = ["grep", "--cached", "-I", "-i", "-F", "-l"]
        for t in terms:
            args += ["-e", t]
        found = git(*args)
        self.assertIn(found.returncode, (0, 1), found.stderr)
        self.assertEqual(found.stdout.split(), [], "files carrying the identity from resume.toml")

    def test_no_personal_file_is_staged(self):
        listed = git("ls-files", "--cached")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual([p for p in listed.stdout.splitlines() if personal(p)], [])


if __name__ == "__main__":
    unittest.main()
