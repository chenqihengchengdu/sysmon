<p align="center">
  <strong>sysmon</strong>
  <br>Per-user CPU &amp; memory monitor for Linux
  <br>Bar charts · Line charts · Spike detection · Alerting
</p>

<p align="center">
  <a href="#quick-install"><img src="https://img.shields.io/badge/install-pip%20--user-blue" alt="pip install --user"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"></a>
  <a href="https://pypi.org/project/psutil/"><img src="https://img.shields.io/badge/deps-psutil-lightgrey" alt="psutil"></a>
</p>

---

sysmon is a **terminal-native** tool that shows you **who** is using your server's resources — right now and over time.  
No web dashboard, no agent, no root required.

---

## Quick Install

```bash
pip install --user git+https://github.com/chenqihengchengdu/sysmon.git
```

If `sysmon` is not found after install:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Requires: Python 3.9+, `psutil` (auto-installed). Read-only on `/proc`.

---

## Auto-Recording

Add a cron job (every 5 minutes) and history + review come alive:

```bash
*/5 * * * * /path/to/sysmon -record
```

Data stored in `~/.local/share/sysmon/sysmon.db` (SQLite).

---

## Live Bar Chart

```
sysmon                  # top 5 users
sysmon -all             # every user
sysmon -user user1      # single-user detail
```

```
=========================== Resource Usage (by user) ===========================
User                    MEM                      CPU
user1       ██████████████████████   █████████████████          40.4%  10.6%
root                                                             0.1%   0.1%
gdm                                                              0.1%   0.0%
user2       █                                                    0.5%  50.1%
user3                                                            0.0%   0.0%

  5 users | Total MEM: 41.1% | Total CPU: 60.7%
```

Blue bars = Memory &nbsp;|&nbsp; Red bars = CPU

---

## Single-User Detail

`sysmon -user user1` draws a **dual-line chart** with CPU and memory over the last 7 days:

```
=========================== user1 — Last 7 Days CPU/MEM ===========================
  Current: CPU 3.2% | MEM 39.7%  (299.4 GB)

   46% │
       │█ █                               ← MEM
   37% │      █  █   █  █   █  █   █  █
       │
   27% │
       │▓ ▓   ▓                           ← CPU
   18% │         ▓   ▓  ▓
       │                    ▓  ▓   ▓
    9% │                               ▓  ▓   ▓
       │
    0% │
       └────────────────────────────────────
        07-02    07-02     07-02     07-02

    █ MEM    ▓ CPU
```

---

## Spike Review — Detect Anomalies

### The killer feature.

`sysmon -review` scans **every user, every record** over a time window and finds the **largest single-interval spike** — who jumped from idle to 100% CPU in 5 minutes? Who suddenly allocated 10 GB of memory?

```
============================ Review — Peak MEM Spike (last 12h) =============================
User                         Peak Spike (MEM%)
user1   ██████████████████████████████████████████████    12.4%  (14:35)
user2   ██████████████                                   3.1%  (09:10)
user3   ████                                            1.2%  (16:50)
```

| Scenario | Command |
|----------|---------|
| Memory leak? | `sysmon -review` |
| CPU storm? | `sysmon -review --cpu` |
| Narrow window? | `sysmon -review --hour 3` |

> **Why this matters:** In multi-user servers, one user running a runaway job can starve everyone else.  
> `sysmon -review` tells you **who spiked, by how much, and when** — before users start complaining.

---

## 7-Day History

`sysmon -history` charts memory trends across your top 5 users over the past week.  
Add `--cpu` for CPU trends. Each user gets a distinct line style.

```
  ── Last 7 days — Memory Usage ──

   49% │
   41% │█████████████           █████████████
   33% │             ███████████             ███████████
   25% │
    0% │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
       └─────────────────────────────────────────
        06-25       06-27       06-29       07-01

    █ user1   ▓ user2   ● user3   ◆ root   ▲ user4
```

---

## Memory Alert

Auto-monitor free memory and broadcast warnings to all logged-in users via `wall`.

```bash
sysmon -alert start 50G        # Alert if free memory < 50 GB
sysmon -alert start 20%        # Alert if free memory < 20%
sysmon -alert start 50G --row 5  # Repeat 5 lines on alert
sysmon -alert stat              # Show current alert config
sysmon -alert stop              # Stop alert
```

**How it works:**
1. `sysmon -alert start 50G` installs a cron job (every minute)
2. When free memory drops below the threshold, a `wall` broadcast alerts all logged-in users
3. Alert fires **once then auto-stops** — no spam
4. While alert is active, **every `sysmon` command** shows a red `!!! MEMORY LOW !!!` banner
5. Use `--row N` to repeat the alert message N times (default: 9)

---

## Full Command Reference

| Command | What it does |
|---------|-------------|
| `sysmon` | Live bar chart — top 5 users |
| `sysmon -all` | Live bar chart — all users |
| `sysmon -user <name>` | Single-user MEM + CPU dual-line chart |
| `sysmon -history` | 7-day memory trend (top 5 users) |
| `sysmon -history --cpu` | 7-day CPU trend |
| `sysmon -review` | Peak memory spikes (last 12h) |
| `sysmon -review --cpu` | Peak CPU spikes |
| `sysmon -review --hour N` | Peak spikes over last N hours |
| `sysmon -record` | Save snapshot (for cron) |
| `sysmon -alert start 50G` | Alert if free mem < 50 GB |
| `sysmon -alert start 20%` | Alert if free mem < 20% |
| `sysmon -alert start 50G --row 5` | Alert with 5 repeated lines |
| `sysmon -alert stat` | Show alert config |
| `sysmon -alert stop` | Stop alert |
| `sysmon --help` | Full help |

---

## License

MIT — use it, fork it, ship it.
