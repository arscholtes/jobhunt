"""Email the qualifying postings that have not been emailed yet.

Deliberately reports the DELTA, not the standing list. An hourly mail carrying the
same 70 rows becomes wallpaper by the second day; one carrying "3 new, here they
are" stays worth opening. If nothing new qualified, nothing is sent at all.

The delta is defined by the `notified` table, not by a time window. A window is a
proxy that fails silently in every interesting case — a missed run, a laptop
asleep past the window, mail configured after the postings landed — and each
failure loses a posting permanently. Rows are marked notified only after the send
returns, so a failed send is retried on the next run rather than swallowed.

Credentials live in ~/.jobhunt-mail.toml, which this never writes and nobody but
the account holder should fill in:

    to       = "you@icloud.com"
    from     = "you@icloud.com"
    username = "you@icloud.com"
    password = "app-specific-password"   # appleid.apple.com -> Sign-In and Security
    host     = "smtp.mail.me.com"
    port     = 587
"""
import email.message
import pathlib
import smtplib
import tomllib

from . import gate

TITLE_CLIP = 46  # keeps a posting on one line on a phone

CONFIG = pathlib.Path.home() / ".jobhunt-mail.toml"



class MailNotConfigured(RuntimeError):
    pass


def config():
    if not CONFIG.exists():
        raise MailNotConfigured(
            f"No mail config at {CONFIG}. See the docstring in notify.py for the shape."
        )
    with CONFIG.open("rb") as fh:
        cfg = tomllib.load(fh)
    missing = [k for k in ("to", "from", "username", "password") if not cfg.get(k)]
    if missing:
        raise MailNotConfigured(f"{CONFIG} is missing: {', '.join(missing)}")
    cfg.setdefault("host", "smtp.mail.me.com")
    cfg.setdefault("port", 587)
    return cfg


def unsent(con, min_score=60, limit=200):
    """Postings at or above `min_score` that have never been emailed.

    @param min_score [float] the shortlist bar
    @param limit [int] cap on one digest; the remainder rides the next run
    @return [list<sqlite3.Row>] highest score first
    """
    return con.execute(
        """SELECT j.id, j.company, j.title, j.location, j.remote, j.url, j.description, s.total
           FROM jobs j
           JOIN scores s ON s.job_id = j.id
           LEFT JOIN notified n ON n.job_id = j.id
           WHERE n.job_id IS NULL AND s.total >= ?
           ORDER BY s.total DESC LIMIT ?""",
        (min_score, limit),
    ).fetchall()


def _table(rows):
    """A narrow HTML table. Phone-first: no wrapper chrome, no images, no CSS
    beyond what one line needs. Title is clipped rather than wrapped so each
    posting stays one line on a small screen."""
    out = [
        '<table cellpadding="3" cellspacing="0" '
        'style="border-collapse:collapse;font:13px -apple-system,sans-serif">'
    ]
    for r in rows:
        title = r["title"]
        if len(title) > TITLE_CLIP:
            title = title[:45] + "…"
        where = "remote" if r["remote"] else (r["location"] or "")[:18]
        # Eligibility rides along with the posting rather than removing it. A
        # region lock or a degree line is something to read before applying, not
        # grounds for the digest to decide on someone's behalf.
        labels = gate.flag_labels(dict(r))
        flag = f'<div style="color:#b45309;font-size:11px">⚑ {labels}</div>' if labels else ""
        out.append(
            f'<tr style="border-top:1px solid #eee">'
            f'<td align="right"><b>{r["total"]:.0f}</b></td>'
            f'<td>{r["company"]}</td>'
            f'<td><a href="{r["url"]}">{title}</a>{flag}</td>'
            f'<td style="color:#777">{where}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def send(rows, cfg=None):
    """Send the digest. Returns False when there was nothing worth sending."""
    if not rows:
        return False
    cfg = cfg or config()

    msg = email.message.EmailMessage()
    msg["Subject"] = f"{len(rows)} new · top {rows[0]['total']:.0f} {rows[0]['company']}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    # Flagged so it surfaces on a locked phone rather than sitting in a pile.
    msg["X-Priority"] = "1"
    msg["Importance"] = "high"
    msg["Priority"] = "urgent"

    plain = "\n".join(
        f"{r['total']:.0f}  {r['company']}  {r['title']}  "
        f"{'remote' if r['remote'] else (r['location'] or '')}\n{r['url']}"
        for r in rows
    )
    msg.set_content(plain)
    msg.add_alternative(_table(rows), subtype="html")

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
        s.starttls()
        s.login(cfg["username"], cfg["password"])
        s.send_message(msg)
    return True
