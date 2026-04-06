"""SQLite persistence for cluster health snapshots."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sentinel.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create health_snapshots table if it does not already exist."""
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                score           INTEGER NOT NULL,
                pod_count       INTEGER NOT NULL,
                unhealthy_count INTEGER NOT NULL,
                warning_count   INTEGER NOT NULL,
                anomaly_count   INTEGER NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_snapshot(
    score: int,
    pod_count: int,
    unhealthy_count: int,
    warning_count: int,
    anomaly_count: int,
) -> None:
    """Insert a health snapshot with the current UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO health_snapshots "
            "(timestamp, score, pod_count, unhealthy_count, warning_count, anomaly_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, score, pod_count, unhealthy_count, warning_count, anomaly_count),
        )
        conn.commit()
    finally:
        conn.close()


def get_timeline(hours: int = 24) -> list[dict]:
    """Return snapshots from the last N hours, ordered oldest to newest."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, timestamp, score, pod_count, unhealthy_count, "
            "warning_count, anomaly_count "
            "FROM health_snapshots WHERE timestamp >= ? ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
