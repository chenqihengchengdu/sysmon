"""Terminal display: bar charts, line charts, review charts, alerts."""

import os
import re

# ─── ANSI Colors ───
R = "\033[31m"  # Red
G = "\033[32m"  # Green
Y = "\033[33m"  # Yellow
B = "\033[34m"  # Blue
M = "\033[35m"  # Magenta
C = "\033[36m"  # Cyan
W = "\033[37m"  # White
X = "\033[0m"   # Reset

COLORS = [R, G, Y, B, M, C]


def _color(c: str, idx: int) -> str:
    return f"{COLORS[idx % len(COLORS)]}{c}{X}"


def _format_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b /= 1024
    return f"{b:.1f} PB"


def _term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 80


def _visible_len(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _pad(s: str, width: int) -> str:
    vl = _visible_len(s)
    return s + " " * max(0, width - vl)


def _alert_row(line: str) -> str:
    """Wrap a row in red if it represents an alert."""
    return f"{R}{line}{X}"


# ═══════════════════════════════════════════════
#  Live bar chart (with optional alert thresholds)
# ═══════════════════════════════════════════════

def show_live(data: list[dict], user: str = None, top_n: int = None,
              alert_banner: str = None):
    """
    Bar chart with optional alert banner.
    alert_banner: if set, displays red banner at top.
    """
    if user:
        data = [d for d in data if d["username"] == user]
        if not data:
            print(f"\nUser not found: {user}\n")
            return
    elif top_n is not None:
        data = sorted(data, key=lambda d: d["mem_bytes"], reverse=True)[:top_n]

    active = data
    w = _term_width()
    name_w = max(len(d["username"]) for d in active) + 1
    bar_w = (w - name_w - 16) // 2
    bar_w = max(bar_w, 10)

    max_mem = max(d["mem_pct"] for d in active)
    max_cpu = max(d["cpu_pct"] for d in active)
    y_max_mem = min(max(int(max_mem) + 5 - int(max_mem) % 5, 10), 100)
    y_max_cpu = min(max(int(max_cpu) + 5 - int(max_cpu) % 5, 10), 100)
    if max_mem < 5:
        y_max_mem = 5
    if max_cpu < 5:
        y_max_cpu = 5

    ticks = [0, y_max_mem // 4, y_max_mem // 2, 3 * y_max_mem // 4, y_max_mem]

    title = " Resource Usage (by user) " if not user else f" Resource Usage — {user} "
    pad = (w - len(title)) // 2
    print(f"\n{'=' * pad}{title}{'=' * (w - pad - len(title))}")

    # Alert banner
    if alert_banner:
        print(f"{R}\033[1m  !!! {alert_banner} !!!  {X}")

    header = f"{'User':<{name_w}s}{'MEM':^{bar_w}s}{'CPU':^{bar_w}s}"
    print(header)

    for d in active:
        name = d["username"][:name_w - 1]
        mem_pct = d["mem_pct"]
        cpu_pct = d["cpu_pct"]

        mem_len = int(mem_pct / y_max_mem * bar_w) if y_max_mem > 0 else 0
        cpu_len = int(cpu_pct / y_max_cpu * bar_w) if y_max_cpu > 0 else 0

        mem_bar = _color("█" * mem_len, 3)
        cpu_bar = _color("█" * cpu_len, 0)

        line = f"{name:<{name_w}s}"
        line += _pad(mem_bar, bar_w)
        line += _pad(cpu_bar, bar_w)
        line += f"  {mem_pct:>5.1f}% {cpu_pct:>5.1f}%"
        print(line)

    mem_ticks = f"{'':<{name_w}s}"
    for t in ticks:
        pos = int(t / y_max_mem * bar_w) if y_max_mem > 0 else 0
        mem_ticks += f"{t}%".ljust(pos + 3)[:pos + 3] if pos > 0 else f"{t}% "
    print(f"\n{mem_ticks}")

    total_used_mem = sum(d["mem_pct"] for d in data)
    total_used_cpu = sum(d["cpu_pct"] for d in data)
    print(f"\n  {len(data)} users | Total MEM: {total_used_mem:.1f}% | Total CPU: {total_used_cpu:.1f}%\n")


# ═══════════════════════════════════════════════
#  Line chart (multi-user)
# ═══════════════════════════════════════════════

def _draw_line_chart(title, users, times, data_map, y_label="%"):
    w = min(_term_width(), 100)
    chart_h = 12
    chart_w = w - 16

    point_count = len(times)
    if point_count < 2:
        print("\nNot enough data points — try again later.\n")
        return

    all_vals = [v for vals in data_map.values() for v in vals]
    y_max = max(max(all_vals) * 1.1, 5) if all_vals else 5

    print(f"\n  ── {title} ──\n")

    for row in range(chart_h, -1, -1):
        y_val = y_max * row / chart_h
        label = f"{y_val:>5.0f}{y_label} │" if row % 2 == 0 else "       │"
        line = label
        for i in range(point_count):
            x = int(i * chart_w / max(point_count - 1, 1))
            while _visible_len(line) - 7 < x:
                line += " "
            char = " "
            for u_idx, user in enumerate(users):
                if user not in data_map:
                    continue
                vals = data_map[user]
                if i >= len(vals):
                    continue
                h = int(vals[i] / y_max * chart_h) if y_max > 0 else 0
                if h == row:
                    last = None
                    for u2_idx in range(u_idx + 1, len(users)):
                        if users[u2_idx] in data_map and i < len(data_map[users[u2_idx]]):
                            h2 = int(data_map[users[u2_idx]][i] / y_max * chart_h) if y_max > 0 else 0
                            if h2 == row:
                                last = u2_idx
                    marker = "▌" if last is not None else "█"
                    char = _color(marker, u_idx)
                    break
            line += char
        line += X
        print(line)

    x_axis = "       └" + "─" * chart_w
    print(x_axis)

    if point_count > 1:
        tick_count = min(6, point_count)
        tick_line = "        "
        for t in range(tick_count):
            i = int(t * (point_count - 1) / max(tick_count - 1, 1))
            x = int(i * chart_w / max(point_count - 1, 1))
            label = times[i].split()[0][5:]
            while len(tick_line) - 8 < x:
                tick_line += " "
            tick_line += label
        print(tick_line)

    print()
    for i, user in enumerate(users):
        if user in data_map:
            marker = _color("█", i)
            name_colored = f"{COLORS[i % len(COLORS)]}{user}{X}"
            print(f"    {marker} {name_colored}")
    print()


def show_history(history, metric: str = "mem"):
    if not history:
        print("\nNo history data. Wait for sysmon --record to accumulate data.\n")
        return

    label = "Memory" if metric == "mem" else "CPU"
    idx = 1 if metric == "mem" else 2

    all_times_set = set()
    for points in history.values():
        for p in points:
            all_times_set.add(p[0])
    all_times = sorted(all_times_set)

    if len(all_times) < 2:
        print("\nNot enough data points — wait a few minutes.\n")
        return

    top_users = sorted(
        history.keys(),
        key=lambda u: sum(p[idx] for p in history[u]) / max(len(history[u]), 1),
        reverse=True,
    )[:5]

    data_map = {}
    for user in top_users:
        up = {p[0]: p[idx] for p in history.get(user, [])}
        data_map[user] = [up.get(t, 0.0) for t in all_times]

    _draw_line_chart(f"Last 7 days — {label} Usage", top_users, all_times, data_map)


# ═══════════════════════════════════════════════
#  Review / spike analysis
# ═══════════════════════════════════════════════

def show_review(spikes: list[dict], hours: int, metric: str = "cpu"):
    metric_label = "CPU" if metric == "cpu" else "MEM"
    if not spikes:
        print(f"\nNot enough data in the last {hours}h for review.\n")
        return

    w = _term_width()
    name_w = max(len(s["username"]) for s in spikes) + 1
    bar_w = w - name_w - 25
    bar_w = max(bar_w, 20)

    max_spike = max(s["max_spike"] for s in spikes)
    y_max = min(max(int(max_spike) + 5 - int(max_spike) % 5, 10), 100)

    title = f" Review — Peak {metric_label} Spike (last {hours}h) "
    pad = (w - len(title)) // 2
    print(f"\n{'=' * pad}{title}{'=' * (w - pad - len(title))}")

    header = f"{'User':<{name_w}s}  {'Peak Spike (' + metric_label + '%)':^{bar_w}s}"
    print(header)

    for s in spikes:
        name = s["username"][:name_w - 1]
        spike_val = s["max_spike"]
        bar_len = int(spike_val / y_max * bar_w) if y_max > 0 else 0
        bar = _color("█" * bar_len, 0)
        peak_time = s["peak_time"].split()[1][:5] if " " in s["peak_time"] else s["peak_time"]
        line = f"{name:<{name_w}s} "
        line += _pad(bar, bar_w)
        line += f" {spike_val:>5.1f}%  ({peak_time})"
        print(line)

    print(f"\n  Last {hours}h | Top {len(spikes)} users by {metric_label} spike\n")


# ═══════════════════════════════════════════════
#  Single-user detail (dual-line chart)
# ═══════════════════════════════════════════════

def show_user_detail(username: str, records: list[tuple], current: dict = None):
    if len(records) < 2:
        print(f"\nNot enough history for {username} (need >= 2 records).\n")
        return

    times = [r[0] for r in records]
    mem_vals = [r[1] for r in records]
    cpu_vals = [r[2] for r in records]

    data_map = {"MEM": mem_vals, "CPU": cpu_vals}

    w = min(_term_width(), 100)
    chart_h = 10
    chart_w = w - 16

    all_vals = mem_vals + cpu_vals
    y_max = max(max(all_vals) * 1.1, 5) if all_vals else 5

    title = f" {username} — Last 7 Days CPU/MEM "
    pad = (w - len(title)) // 2
    print(f"\n{'=' * pad}{title}{'=' * (w - pad - len(title))}")

    if current:
        print(f"  Current: CPU {current['cpu_pct']:.1f}% | MEM {current['mem_pct']:.1f}%  ({_format_bytes(current['mem_bytes'])})\n")

    point_count = len(times)
    users = ["MEM", "CPU"]

    for row in range(chart_h, -1, -1):
        y_val = y_max * row / chart_h
        label = f"{y_val:>5.0f}% │" if row % 2 == 0 else "       │"
        line = label
        for i in range(point_count):
            x = int(i * chart_w / max(point_count - 1, 1))
            while _visible_len(line) - 7 < x:
                line += " "
            char = " "
            for u_idx, key in enumerate(users):
                vals = data_map[key]
                h = int(vals[i] / y_max * chart_h) if y_max > 0 else 0
                if h == row:
                    marker = _color("█", 3) if key == "MEM" else _color("▓", 0)
                    char = marker
                    break
            line += char
        line += X
        print(line)

    x_axis = "       └" + "─" * chart_w
    print(x_axis)

    if point_count > 1:
        tick_count = min(6, point_count)
        tick_line = "        "
        for t in range(tick_count):
            i = int(t * (point_count - 1) / max(tick_count - 1, 1))
            x = int(i * chart_w / max(point_count - 1, 1))
            label = times[i].split()[0][5:]
            while len(tick_line) - 8 < x:
                tick_line += " "
            tick_line += label
        print(tick_line)

    mem_label = _color("█", 3) + " MEM"
    cpu_label = _color("▓", 0) + " CPU"
    print(f"\n    {mem_label}    {cpu_label}\n")


# ═══════════════════════════════════════════════
#  Watch alert helper
# ═══════════════════════════════════════════════

def check_alerts(data: list[dict], alert_mem: float = None, alert_cpu: float = None) -> list[str]:
    """Check collected data against thresholds. Return list of alert messages."""
    msgs = []
    total_used_mem = sum(d["mem_pct"] for d in data)
    total_used_cpu = sum(d["cpu_pct"] for d in data)
    remain_mem = 100 - total_used_mem
    remain_cpu = 100 - total_used_cpu

    if alert_mem is not None and remain_mem < alert_mem:
        violators = [d["username"] for d in data if (100 - d["mem_pct"]) < alert_mem]
        msgs.append(f"MEM remaining {remain_mem:.1f}% < alert {alert_mem:.0f}% (top: {', '.join(violators[:3])})")
    if alert_cpu is not None and remain_cpu < alert_cpu:
        violators = [d["username"] for d in data if (100 - d["cpu_pct"]) < alert_cpu]
        msgs.append(f"CPU remaining {remain_cpu:.1f}% < alert {alert_cpu:.0f}% (top: {', '.join(violators[:3])})")
    return msgs
