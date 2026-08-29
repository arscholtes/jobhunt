"""A board token is an address, not a company name.

Podium's Greenhouse board is served under the token "podium81", so every posting
it produced was filed under a company called podium81. That name is what the
digest shows, what boilerplate detection groups on, and what culture scoring keys
to — so an address leaking into it is not merely cosmetic.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cli


def row(company="podium81", jid="greenhouse:podium81:1"):
    return {"id": jid, "source": "greenhouse", "company": company, "title": "Engineer",
            "location": "Remote", "remote": 1, "url": "http://x", "description": "d",
            "posted_at": None}


class DisplayNameTests(unittest.TestCase):
    def test_a_board_without_a_name_keeps_its_token_as_the_company(self):
        board = {"source": "greenhouse", "token": "stripe"}
        out = cli.apply_board_name([row(company="stripe")], board)
        self.assertEqual(out[0]["company"], "stripe")

    def test_a_board_with_a_name_uses_it_as_the_company(self):
        board = {"source": "greenhouse", "token": "podium81", "name": "podium"}
        out = cli.apply_board_name([row()], board)
        self.assertEqual(out[0]["company"], "podium")

    def test_every_row_from_the_board_is_renamed(self):
        board = {"source": "greenhouse", "token": "podium81", "name": "podium"}
        out = cli.apply_board_name([row(), row(jid="greenhouse:podium81:2")], board)
        self.assertEqual({r["company"] for r in out}, {"podium"})

    def test_the_posting_id_is_left_alone_so_nothing_is_re_imported(self):
        # The id encodes the board address. Rewriting it would make every known
        # posting look new and re-notify the whole shortlist.
        board = {"source": "greenhouse", "token": "podium81", "name": "podium"}
        out = cli.apply_board_name([row()], board)
        self.assertEqual(out[0]["id"], "greenhouse:podium81:1")

    def test_an_empty_name_is_ignored_rather_than_blanking_the_company(self):
        board = {"source": "greenhouse", "token": "podium81", "name": ""}
        out = cli.apply_board_name([row()], board)
        self.assertEqual(out[0]["company"], "podium81")

    def test_renaming_an_empty_result_set_is_harmless(self):
        self.assertEqual(cli.apply_board_name([], {"source": "x", "token": "y", "name": "z"}), [])


if __name__ == "__main__":
    unittest.main()
