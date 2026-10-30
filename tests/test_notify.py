"""The digest: what gets emailed, once, and what it says about eligibility."""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import notify, store

MAIL = {"to": "candidate@example.com", "from": "candidate@example.com",
        "username": "smtp-user@example.com", "password": "app-specific-password",
        "host": "smtp.example.com", "port": 2525}


class DigestTestCase(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def add(self, jid, total, title="Backend Engineer", description="", company="co"):
        self.con.execute(
            """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                 description, posted_at, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (jid, "src", company, title, "Remote", 1, "http://x", description,
             None, "2026-01-01", "2026-01-01"))
        self.con.execute(
            "INSERT INTO scores (job_id, total, breakdown, scored_at) VALUES (?,?,?,?)",
            (jid, total, "{}", "2026-01-01"))
        self.con.commit()


class UnsentTests(DigestTestCase):
    def test_a_scored_posting_above_the_bar_is_unsent(self):
        self.add("a", 80)
        self.assertEqual([r["id"] for r in notify.unsent(self.con, min_score=60)], ["a"])

    def test_a_posting_below_the_bar_is_not_offered(self):
        self.add("a", 40)
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_a_notified_posting_is_never_offered_again(self):
        self.add("a", 80)
        store.mark_notified(self.con, ["a"])
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_highest_score_comes_first(self):
        self.add("low", 70)
        self.add("high", 90)
        self.assertEqual([r["id"] for r in notify.unsent(self.con, min_score=60)], ["high", "low"])

    def test_the_limit_caps_one_digest(self):
        for i in range(5):
            self.add(f"j{i}", 70 + i)
        self.assertEqual(len(notify.unsent(self.con, min_score=60, limit=2)), 2)

    def test_a_disqualified_posting_never_reaches_the_digest(self):
        self.add("a", -1)
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_marking_notified_twice_does_not_error(self):
        self.add("a", 80)
        store.mark_notified(self.con, ["a"])
        store.mark_notified(self.con, ["a"])
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_the_send_record_is_what_gates_the_digest_not_a_time_window(self):
        # A missed run or a sleeping laptop must never drop a posting permanently.
        self.add("a", 80)
        self.assertEqual(len(notify.unsent(self.con, min_score=60)), 1)
        self.assertEqual(len(notify.unsent(self.con, min_score=60)), 1)


class TableTests(DigestTestCase):
    def test_the_table_renders_a_posting(self):
        self.add("a", 80, title="Backend Engineer")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("Backend Engineer", html)

    def test_a_region_locked_posting_is_flagged_in_the_digest(self):
        self.add("a", 80, title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("region-locked", html)

    def test_a_clean_posting_carries_no_flag_noise(self):
        self.add("a", 80, title="Backend Engineer", description="Build things.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertNotIn("region-locked", html)

    def test_a_flagged_posting_is_still_listed_never_hidden(self):
        self.add("a", 80, title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("Forward Deployed Engineer", html)


class SendTests(DigestTestCase):
    """The SMTP conversation, with smtplib stubbed so nothing leaves the machine."""

    def send(self, rows, cfg):
        with mock.patch.object(notify.smtplib, "SMTP") as smtp:
            sent = notify.send(rows, cfg=cfg)
        return sent, smtp

    def two_postings(self):
        self.add("a", 91.4, company="Contoso")
        self.add("b", 72, company="Fabrikam")
        return notify.unsent(self.con, min_score=60)

    def test_the_connection_is_encrypted_before_the_password_is_sent(self):
        _, smtp = self.send(self.two_postings(), MAIL)
        session = smtp.return_value.__enter__.return_value
        self.assertEqual([c[0] for c in session.method_calls], ["starttls", "login", "send_message"])

    def test_the_server_and_credentials_come_from_the_config(self):
        _, smtp = self.send(self.two_postings(), MAIL)
        smtp.assert_called_once_with("smtp.example.com", 2525, timeout=30)
        smtp.return_value.__enter__.return_value.login.assert_called_once_with(
            "smtp-user@example.com", "app-specific-password")

    def test_the_subject_names_the_count_and_the_top_posting(self):
        _, smtp = self.send(self.two_postings(), MAIL)
        msg = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(msg["Subject"], "2 new · top 91 Contoso")

    def test_nothing_to_send_opens_no_connection(self):
        sent, smtp = self.send([], MAIL)
        self.assertFalse(sent)
        smtp.assert_not_called()

    def test_an_unconfigured_send_fails_before_connecting(self):
        rows = self.two_postings()
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(notify, "CONFIG", Path(tmp) / "absent.toml"), \
             mock.patch.object(notify.smtplib, "SMTP") as smtp, \
             self.assertRaises(notify.MailNotConfigured):
            notify.send(rows)
        smtp.assert_not_called()


class ConfigTests(unittest.TestCase):
    """The mail config, read from a temporary path so a real one is never touched."""

    FULL = ('to = "candidate@example.com"\nfrom = "candidate@example.com"\n'
            'username = "candidate@example.com"\npassword = "app-specific-password"\n')

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "mail.toml"

    def tearDown(self):
        self._tmp.cleanup()

    def load(self, text=None):
        if text is not None:
            self.path.write_text(text)
        with mock.patch.object(notify, "CONFIG", self.path):
            return notify.config()

    def test_no_config_file_is_mail_not_configured(self):
        with self.assertRaises(notify.MailNotConfigured):
            self.load()

    def test_every_missing_key_is_named(self):
        with self.assertRaises(notify.MailNotConfigured) as caught:
            self.load('to = "candidate@example.com"\n')
        self.assertIn("from, username, password", str(caught.exception))

    def test_an_empty_password_counts_as_missing(self):
        with self.assertRaises(notify.MailNotConfigured) as caught:
            self.load(self.FULL.replace('"app-specific-password"', '""'))
        self.assertIn("password", str(caught.exception))

    def test_host_and_port_default_to_icloud_submission(self):
        cfg = self.load(self.FULL)
        self.assertEqual((cfg["host"], cfg["port"]), ("smtp.mail.me.com", 587))


if __name__ == "__main__":
    unittest.main()
