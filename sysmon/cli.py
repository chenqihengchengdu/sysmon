#!/usr/bin/env python3
"""sysmon — System resource monitor for Linux.

Commands:
    sysmon                          Live bar chart (top 5 users)
    sysmon -alert start [N]G       Start alert: warn if free memory < N GB (default 50G)
    sysmon -alert start [N]%       Start alert: warn if free memory < N%
    sysmon -alert stat              Show alert config
    sysmon -alert stop              Stop alert

Examples:
    sysmon -alert start               Alert if free mem < 50 GB (default)
    sysmon -alert start 100G --row 5  Alert 100G, repeat 5 lines on trigger
    sysmon -alert start 20%           Alert if free mem < 20%
    sysmon -alert stat                Show current thresholds
    sysmon -alert stop                Disable alert
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

import psutil

from sysmon.collector import collect_by_user, get_total_memory
from sysmon.storage import (
    insert_snapshot, query_history, query_review, query_user_history, DB_PATH,
)
from sysmon.display import (
    show_live, show_history, show_review, show_user_detail, R, X,
)


ALERT_DIR = os.path.expanduser("~/.local/share/sysmon")
ALERT_FILE = os.path.join(ALERT_DIR, "alert.json")
_CRON_MARKER = "# sysmon-auto-alert"
DEFAULT_ALERT = "50G"
DEFAULT_ROW = 9


def _read_alert_config():
    if not os.path.exists(ALERT_FILE):
        return None
    with open(ALERT_FILE) as f:
        return json.load(f)


def _write_alert_config(cfg):
    os.makedirs(ALERT_DIR, exist_ok=True)
    with open(ALERT_FILE, "w") as f:
        json.dump(cfg, f)


def _delete_alert_config():
    if os.path.exists(ALERT_FILE):
        os.remove(ALERT_FILE)


def _install_cron(threshold_arg):
    cmd = f"* * * * * {sys.executable} -m sysmon.cli __cron_check__ {threshold_arg} {_CRON_MARKER}"
    try:
        existing = subprocess.check_output(["crontab", "-l"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        existing = ""
    lines = [l for l in existing.splitlines() if _CRON_MARKER not in l]
    lines.append(cmd)
    lines.append("")
    subprocess.run(["crontab", "-"], input="\n".join(lines).encode(), check=True)


def _remove_cron():
    try:
        existing = subprocess.check_output(["crontab", "-l"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return
    lines = [l for l in existing.splitlines() if _CRON_MARKER not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines).encode() + b"\n", check=True)


def _notify_wall(msg: str, repeat: int = 1):
    """Broadcast to all logged-in users, repeated `repeat` times."""
    text = (msg + "\n") * repeat
    try:
        subprocess.run(["wall"], input=text.encode(), timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _parse_threshold(arg):
    arg = arg.strip().upper()
    if arg.endswith("G"):
        return ("gb", float(arg[:-1]))
    elif arg.endswith("%"):
        return ("pct", float(arg[:-1]))
    raise ValueError(f"Invalid threshold: {arg}. Use 50G or 20%.")


def _check_threshold(threshold_arg):
    unit, val = _parse_threshold(threshold_arg)
    mem = psutil.virtual_memory()
    if unit == "gb":
        return mem.available / (1024**3) < val
    return mem.available / mem.total * 100 < val


def _describe_threshold(arg):
    unit, val = _parse_threshold(arg)
    return f"free memory < {val:.0f} GB" if unit == "gb" else f"free memory < {val:.0f}%"


def _handle_cron_check(threshold_arg):
    if not _check_threshold(threshold_arg):
        return 0
    desc = _describe_threshold(threshold_arg)
    mem = psutil.virtual_memory()
    free_gb = mem.available / (1024**3)
    free_pct = mem.available / mem.total * 100
    msg = f"!!! SERVER MEMORY LOW — {desc} | Current: {free_gb:.1f} GB free ({free_pct:.1f}%) !!!"

    cfg = _read_alert_config()
    repeat = cfg.get("row", DEFAULT_ROW) if cfg else DEFAULT_ROW
    _notify_wall(msg, repeat)

    _delete_alert_config()
    _remove_cron()
    sys.stderr.write(f"[sysmon] Alert triggered and auto-stopped: {msg}\n")
    return 1


def _cmd_alert_start(threshold=DEFAULT_ALERT, row=DEFAULT_ROW):
    try:
        _parse_threshold(threshold)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    _write_alert_config({"threshold": threshold, "row": row})
    _install_cron(threshold)
    print(f"Alert ON — {_describe_threshold(threshold)}")
    print(f"  Repeat: {row} lines on trigger")
    print("  Checked every minute. On trigger: wall broadcast + auto-stop.")


def _cmd_alert_stat():
    cfg = _read_alert_config()
    if not cfg:
        print("No alert configured.")
        return
    print(f"Alert ACTIVE — {_describe_threshold(cfg['threshold'])}")
    print(f"  Repeat: {cfg.get('row', DEFAULT_ROW)} lines")


def _cmd_alert_stop():
    _delete_alert_config()
    _remove_cron()
    print("Alert stopped.")


def _get_alert_banner():
    cfg = _read_alert_config()
    if not cfg:
        return None
    if _check_threshold(cfg["threshold"]):
        desc = _describe_threshold(cfg["threshold"])
        mem = psutil.virtual_memory()
        free_gb = mem.available / (1024**3)
        free_pct = mem.available / mem.total * 100
        return f"MEMORY LOW — {desc} | Current: {free_gb:.1f} GB free ({free_pct:.1f}%)"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="sysmon — per-user CPU & memory monitor for Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sysmon                         Live bar chart
  sysmon -alert start            Alert if free mem < 50 GB (default)
  sysmon -alert start 100G       Alert if free mem < 100 GB
  sysmon -alert start 20%        Alert if free mem < 20%
  sysmon -alert start 50G --row 3  Alert with 3 repeated lines
  sysmon -alert stat             Show alert config
  sysmon -alert stop             Stop alert
        """,
    )

    parser.add_argument("-alert", nargs=argparse.REMAINDER, default=None,
                        help="Alert: start [50G|20%%] | stat | stop")
    parser.add_argument("-record", action="store_true", help="Save current snapshot to DB")
    parser.add_argument("-history", action="store_true", help="Show 7-day usage trend")
    parser.add_argument("-user", type=str, default=None, help="Single-user detail (dual-line chart)")
    parser.add_argument("-all", action="store_true", help="Show all users (default: top 5)")
    parser.add_argument("-review", action="store_true", help="Review: find users with largest resource spikes")
    parser.add_argument("--cpu", action="store_true", help="Use CPU metric (with -review or -history)")
    parser.add_argument("--hour", type=int, default=None, help="Review window in hours (default: 12, with -review)")
    parser.add_argument("--row", type=int, default=DEFAULT_ROW, help=f"Alert repeat lines (default: {DEFAULT_ROW})")

    parser.add_argument("-db-path", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("__cron_check__", nargs="*", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if hasattr(args, '__cron_check__') and args.__cron_check__:
        _handle_cron_check(args.__cron_check__[-1])
        return

    if args.alert is not None:
        sub = args.alert
        if not sub:
            parser.print_help()
            sys.exit(1)
        action = sub[0]
        if action == "start":
            threshold = sub[1] if len(sub) > 1 else DEFAULT_ALERT
            _cmd_alert_start(threshold, args.row)
        elif action == "stat":
            _cmd_alert_stat()
        elif action == "stop":
            _cmd_alert_stop()
        else:
            print(f"Unknown alert action: {action}")
            sys.exit(1)
        return

    if getattr(args, 'db_path', None):
        print(DB_PATH)
        return

    if args.record:
        data = collect_by_user()
        insert_snapshot(data)
        total_gb = sum(d["mem_bytes"] for d in data) / 1024**3
        print(f"Snapshot saved: {len(data)} users, {total_gb:.1f} GB memory")
        return

    if args.user:
        data = collect_by_user()
        current = next((d for d in data if d["username"] == args.user), None)
        if current is None:
            print(f"\nUser not found: {args.user}\n")
            return
        records = query_user_history(args.user, days=7)
        show_user_detail(args.user, records, current)
        return

    if args.review:
        hours = args.hour if args.hour else 12
        metric = "cpu" if args.cpu else "mem"
        spikes = query_review(hours=hours, metric=metric)
        show_review(spikes, hours, metric)
        return

    if args.history:
        hist = query_history(days=7)
        metric = "cpu" if args.cpu else "mem"
        show_history(hist, metric)
        return

    data = collect_by_user()
    banner = _get_alert_banner()
    if args.all:
        show_live(data, alert_banner=banner)
    else:
        show_live(data, top_n=5, alert_banner=banner)


if __name__ == "__main__":
    main()
