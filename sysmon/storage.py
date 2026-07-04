"""SQLite storage for CPU/memory history records."""

import os
import sqlite3
from datetime import datetime, timedelta

DB_DIR = os.path.expanduser("~/.local/share/sysmon")
DB_PATH = os.path.join(DB_DIR, "sysmon.db")


def _ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            mem_bytes INTEGER NOT NULL,
            mem_pct REAL NOT NULL,
            cpu_pct REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ts_user
        ON records(timestamp, username)
    """)
    conn.commit()
    return conn


def insert_snapshot(data: list[dict]):
    """Write a time-snapshot of all users."""
    conn = _ensure_db()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        (ts, d["username"], d["mem_bytes"], d["mem_pct"], d["cpu_pct"])
        for d in data
    ]
    conn.executemany(
        "INSERT INTO records (timestamp, username, mem_bytes, mem_pct, cpu_pct) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def query_history(days: int = 7):
    """Query the last N days of data, aggregated by hour.

    Returns: {username: [(timestamp, avg_mem_pct, avg_cpu_pct), ...]}
    """
    conn = _ensure_db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            username,
            AVG(mem_pct) as avg_mem,
            AVG(cpu_pct) as avg_cpu
        FROM records
        WHERE timestamp >= ?
        GROUP BY hour, username
        ORDER BY hour, username
        """,
        (since,),
    ).fetchall()
    conn.close()

    result: dict[str, list[tuple]] = {}
    for hour, username, avg_mem, avg_cpu in rows:
        if username not in result:
            result[username] = []
        result[username].append((hour, round(avg_mem, 1), round(avg_cpu, 1)))

    return result


def query_review(hours: int = 12, metric: str = "cpu") -> list[dict]:
    """Review: find per-user peak spike (delta) over the last N hours.

    metric: "cpu" or "mem"
    Returns list sorted by max_spike descending.
    """
    conn = _ensure_db()
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    col = "cpu_pct" if metric == "cpu" else "mem_pct"

    rows = conn.execute(
        f"""
        SELECT timestamp, username, {col}
        FROM records
        WHERE timestamp >= ?
        ORDER BY username, timestamp
        """,
        (since,),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    # Group by user, compute delta between consecutive records
    user_data: dict[str, list[tuple[str, float]]] = {}
    for ts, username, val in rows:
        if username not in user_data:
            user_data[username] = []
        user_data[username].append((ts, val))

    spikes = []
    for username, points in user_data.items():
        if len(points) < 2:
            continue
        max_spike = 0.0
        peak_time = points[0][0]
        for i in range(1, len(points)):
            diff = points[i][1] - points[i - 1][1]
            if diff > max_spike:
                max_spike = diff
                peak_time = points[i][0]
        if max_spike > 0.1:
            spikes.append({
                "username": username,
                "max_spike": round(max_spike, 1),
                "peak_time": peak_time,
            })

    spikes.sort(key=lambda s: s["max_spike"], reverse=True)
    return spikes[:10]


def query_user_history(username: str, days: int = 7):
    """Get raw records for a specific user over the last N days.

    Returns: [(timestamp, mem_pct, cpu_pct), ...]
    """
    conn = _ensure_db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT timestamp, mem_pct, cpu_pct
        FROM records
        WHERE username = ? AND timestamp >= ?
        ORDER BY timestamp
        """,
        (username, since),
    ).fetchall()
    conn.close()
    return rows
