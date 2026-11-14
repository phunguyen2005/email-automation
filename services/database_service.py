import sqlite3
from datetime import datetime, timezone


def connect(path: str):
    connection = sqlite3.connect(path, timeout=15)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS send_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        recipient_key TEXT NOT NULL,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        sent_at TEXT,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        error TEXT NOT NULL DEFAULT '',
        UNIQUE(campaign_id, recipient_key, mode)
    )""")
    connection.commit()
    return connection


def claim(path: str, campaign: str, key: str, email: str, subject: str, mode: str, retry_failed=False) -> bool:
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT status FROM send_log WHERE campaign_id=? AND recipient_key=? AND mode=?",
            (campaign, key, mode),
        ).fetchone()
        if existing:
            if not retry_failed or existing[0] != "Failed":
                return False
            db.execute(
                "UPDATE send_log SET status='Sending', error='', subject=?, sent_at=NULL WHERE campaign_id=? AND recipient_key=? AND mode=?",
                (subject, campaign, key, mode),
            )
        else:
            db.execute(
                "INSERT INTO send_log(campaign_id,recipient_key,recipient_email,subject,mode,status) VALUES(?,?,?,?,?,'Sending')",
                (campaign, key, email, subject, mode),
            )
        db.commit()
        return True


def finish(path: str, campaign: str, key: str, mode: str, status: str, error=""):
    with connect(path) as db:
        db.execute(
            "UPDATE send_log SET status=?, error=?, sent_at=? WHERE campaign_id=? AND recipient_key=? AND mode=?",
            (status, error[:500], datetime.now(timezone.utc).isoformat(), campaign, key, mode),
        )
        db.commit()


def history(path: str, campaign: str, mode: str):
    with connect(path) as db:
        rows = db.execute(
            "SELECT recipient_email,subject,sent_at,mode,status,error FROM send_log WHERE campaign_id=? AND mode=? ORDER BY id",
            (campaign, mode),
        ).fetchall()
    return rows
