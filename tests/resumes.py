"""The resumes the tests build variants from.

The owner's resume.toml is gitignored, so a checkout without it, CI included, has
only the fictional candidate. Rules about how a variant is built run against both.
Checks on the owner's own facts run only where those facts exist.
"""

import unittest
from pathlib import Path

from jobhunt import resume

CANDIDATE = Path(__file__).resolve().parent / "fixtures" / "candidate.toml"

owners_resume = unittest.skipUnless(
    resume.PATH.exists(), "no resume.toml: this checks the owner's own resume, which git ignores")


def every_resume():
    """The fictional candidate, then the owner's resume where this checkout has one.

    @return [list[tuple[str, dict]]] a label and the loaded facts for each
    """
    found = [("candidate", resume.load(CANDIDATE))]
    if resume.PATH.exists():
        found.append(("resume.toml", resume.load()))
    return found
