"""SQLite persistence for cluster health snapshots and diagnosis history."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sentinel.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not already exist."""
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diagnosis_history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT    NOT NULL,
                focus            TEXT,
                summary          TEXT    NOT NULL,
                root_cause       TEXT    NOT NULL,
                kubectl_commands TEXT    NOT NULL,
                anomaly_count    INTEGER NOT NULL,
                pod_count        INTEGER NOT NULL
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


def insert_diagnosis(
    focus: str | None,
    summary: str,
    root_cause: str,
    kubectl_commands: list[str],
    anomaly_count: int,
    pod_count: int,
) -> None:
    """Insert a diagnosis record with the current UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO diagnosis_history "
            "(timestamp, focus, summary, root_cause, kubectl_commands, anomaly_count, pod_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, focus, summary, root_cause, json.dumps(kubectl_commands), anomaly_count, pod_count),
        )
        conn.commit()
    finally:
        conn.close()


def get_diagnosis_history(limit: int = 50) -> list[dict]:
    """Return diagnosis records ordered newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, timestamp, focus, summary, root_cause, kubectl_commands, "
            "anomaly_count, pod_count "
            "FROM diagnosis_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_diagnosis(query: str, limit: int = 50) -> list[dict]:
    """Search diagnosis records by summary or root_cause using LIKE."""
    like = f"%{query}%"
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, timestamp, focus, summary, root_cause, kubectl_commands, "
            "anomaly_count, pod_count "
            "FROM diagnosis_history "
            "WHERE summary LIKE ? OR root_cause LIKE ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (like, like, limit),
        ).fetchall()
        return [dict(row) for row in rows]
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
