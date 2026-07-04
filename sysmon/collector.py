"""Collect CPU and memory usage aggregated by user."""

import time
import psutil


def get_total_memory() -> int:
    """Return total system memory in bytes."""
    return psutil.virtual_memory().total


def collect_by_user() -> list[dict]:
    """
    Collect all processes, aggregate CPU and memory by user.

    CPU requires two sampling rounds (~0.2s apart) for meaningful percentages.

    Returns sorted list of dicts:
        {username, mem_bytes, mem_pct, cpu_pct}
    """
    # Round 1: cache all processes and prime CPU counters
    procs: dict[int, dict] = {}
    for proc in psutil.process_iter(["username", "memory_info"]):
        try:
            _ = proc.cpu_percent()  # prime, returns 0
            info = proc.info
            username = info["username"] or "?"
            mem_bytes = info["memory_info"].rss
            procs[proc.pid] = {
                "proc": proc,
                "username": username,
                "mem_bytes": mem_bytes,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Brief pause for CPU counters to accumulate delta
    time.sleep(0.2)

    # Round 2: aggregate
    users: dict[str, dict] = {}
    for pid, entry in list(procs.items()):
        proc = entry["proc"]
        try:
            cpu_pct = proc.cpu_percent() or 0.0
            username = entry["username"]
            mem_bytes = entry["mem_bytes"]

            if username not in users:
                users[username] = {"mem_bytes": 0, "cpu_pct": 0.0}
            users[username]["mem_bytes"] += mem_bytes
            users[username]["cpu_pct"] += cpu_pct
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    total_mem = get_total_memory()
    cpu_count = psutil.cpu_count() or 1
    result = []
    for username in sorted(users):
        u = users[username]
        result.append({
            "username": username,
            "mem_bytes": u["mem_bytes"],
            "mem_pct": round(u["mem_bytes"] / total_mem * 100, 1),
            "cpu_pct": round(u["cpu_pct"] / cpu_count, 1),
        })

    return result
