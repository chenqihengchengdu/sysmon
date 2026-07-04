# sysmon — Linux 终端系统资源监控工具·开发全记录

> 作者: chenqh (chenqihengchengdu)  
> 日期: 2026-07-02  
> 版本: v0.2.0  
> 仓库: https://github.com/chenqihengchengdu/sysmon

---

## 一、项目概述

**sysmon** 是一个 Linux 终端下的系统资源监控工具，按用户聚合 CPU 和内存使用情况。支持实时柱状图、7 天历史走势、复盘波动分析、内存报警四大核心功能。纯 Python 实现，无需 root 权限，一行 `pip install --user` 即可安装。

### 设计哲学

- **终端原生**：所有图表在终端内用 ANSI 颜色和 Unicode 字符渲染，不需要 Web 界面
- **零依赖安装**：只依赖 `psutil`，通过 `/proc` 文件系统读取系统数据
- **自动化优先**：cron 定时记录 + 自动报警，无需人为干预
- **简洁命令**：一级命令用 `-`（如 `sysmon -history`），子选项用 `--`（如 `--cpu`）

---

## 二、功能总览

### 2.1 实时柱状图 `sysmon`

```
=========================== Resource Usage (by user) ===========================
User                    MEM                      CPU
user1       ██████████████████████   █████████████████          40.4%  10.6%
root                                                             0.1%   0.1%
user2       █                                                    0.5%  50.1%

  5 users | Total MEM: 41.1% | Total CPU: 60.7%
```

- 默认显示前 5 用户，`-all` 显示全部
- 内存蓝色、CPU 红色
- 报警激活时超标用户整行标红

### 2.2 单人详情 `sysmon -user <name>`

双线折线图：蓝色 MEM + 红色 CPU，展示最近 7 天趋势。

### 2.3 历史走势 `sysmon -history` / `sysmon -history --cpu`

最近 7 天 Top 5 用户走势，每个用户不同颜色线条。

### 2.4 复盘分析 `sysmon -review`

- 扫描指定时间窗口内所有用户，找出单次间隔内增长最快的用户
- 支持 `--cpu`（CPU 波动）和 `--hour N`（时间窗口）
- 核心用途：发现谁在短时间内突然耗尽资源

### 2.5 内存报警 `sysmon -alert`

| 命令 | 说明 |
|------|------|
| `sysmon -alert start 50G` | 剩余内存 < 50GB 报警 |
| `sysmon -alert start 20%` | 剩余内存 < 20% 报警 |
| `sysmon -alert start 50G --row 5` | 报警时 wall 重复 5 行 |
| `sysmon -alert stat` | 查看配置 |
| `sysmon -alert stop` | 停止 |

- 自动写入 crontab，每分钟检查一次
- 触发后 `wall` 广播所有在线用户，自动停止（不刷屏）
- 报警期间所有 `sysmon` 命令显示红色横幅

---

## 三、架构设计

```
sysmon/
├── setup.py                # 安装配置（只需它，无 pyproject.toml）
├── README.md               # 英文文档
├── LICENSE                 # MIT
├── .gitignore
├── docs/
│   └── sysmon-guide-zh.html # 中文使用说明
└── sysmon/
    ├── __init__.py
    ├── cli.py              # CLI 入口 + 报警逻辑
    ├── collector.py        # 数据采集（psutil，两轮采样获取 CPU）
    ├── storage.py           # SQLite 存储（记录、历史查询、复盘查询）
    └── display.py           # 终端显示（柱状图、折线图、复盘图）
```

**数据流：**

```
psutil → collector.py → cli.py → display.py → 终端
                          ↓
                    storage.py → SQLite → history / review
```

**报警流：**

```
cron (每分钟) → cli.py __cron_check__ → check_threshold()
                → wall 广播 + auto-stop
```

---

## 四、核心技术实现

### 4.1 CPU 采集（两轮采样）

```python
def collect_by_user() -> list[dict]:
    # Round 1: prime CPU counters (returns 0)
    procs = {}
    for proc in psutil.process_iter(["username", "memory_info"]):
        _ = proc.cpu_percent()  # prime
        procs[proc.pid] = {"proc": proc, "username": ..., "mem_bytes": ...}

    time.sleep(0.2)  # let counters accumulate delta

    # Round 2: get actual CPU%
    for pid, entry in procs.items():
        cpu_pct = entry["proc"].cpu_percent()  # valid value
        ...
```

**为什么需要两轮？** psutil 的 `cpu_percent()` 第一次调用永远返回 0，因为它需要两个时间点的差值。第一轮初始化计数器，睡眠 0.2 秒后再取有效值。

### 4.2 ANSI 颜色方案

```python
R = "\033[31m"  # 红 — CPU / 报警行
B = "\033[34m"  # 蓝 — 内存
G = "\033[32m"  # 绿
Y = "\033[33m"  # 黄
M = "\033[35m"  # 品红
C = "\033[36m"  # 青
X = "\033[0m"   # 重置

COLORS = [R, G, Y, B, M, C]  # 循环分配给不同用户

def _color(c: str, idx: int) -> str:
    return f"{COLORS[idx % len(COLORS)]}{c}{X}"
```

### 4.3 折线图渲染

```python
def _draw_line_chart(title, users, times, data_map, y_label="%"):
    chart_h = 12  # 12 行高
    for row in range(chart_h, -1, -1):  # 从上到下
        y_val = y_max * row / chart_h
        label = f"{y_val:>5.0f}% │" if row % 2 == 0 else "       │"
        line = label
        for i in range(point_count):
            # 检查每个用户在该时间点是否穿过此行
            for u_idx, user in enumerate(users):
                h = int(vals[i] / y_max * chart_h)
                if h == row:
                    # 如果多线重叠，用 ▌（半块）标识
                    marker = "▌" if has_overlap else "█"
                    char = _color(marker, u_idx)
                    break
            line += char
        print(line + X)
```

### 4.4 复盘算法

```python
def query_review(hours: int = 12, metric: str = "cpu"):
    # 获取最近 N 小时所有用户的原始记录
    rows = db.execute("SELECT timestamp, username, cpu_pct FROM records ...")

    # 按用户分组，计算相邻记录差值
    for username, points in user_data.items():
        for i in range(1, len(points)):
            diff = points[i][1] - points[i-1][1]  # CPU/内存增长量
            if diff > max_spike:
                max_spike = diff
                peak_time = points[i][0]

    # 按增长量降序，返回 Top 10
    spikes.sort(key=lambda s: s["max_spike"], reverse=True)
```

### 4.5 报警系统

```python
def _cmd_alert_start(threshold="50G", row=9):
    cfg = {"threshold": threshold, "row": row}
    _write_alert_config(cfg)        # 存到 ~/.local/share/sysmon/alert.json
    _install_cron(threshold)         # 写入 crontab: 每分钟检查

def _handle_cron_check(threshold_arg):
    if not _check_threshold(threshold_arg):
        return 0  # 阈值未触发
    # 触发！
    _notify_wall(msg, repeat=cfg["row"])  # wall 广播 N 行
    _delete_alert_config()                 # 清除配置
    _remove_cron()                         # 删除 cron
    return 1                               # 自动停止
```

**阈值解析：**
```python
def _parse_threshold(arg: str):
    arg = arg.strip().upper()
    if arg.endswith("G"): return ("gb", float(arg[:-1]))
    if arg.endswith("%"): return ("pct", float(arg[:-1]))

def _check_threshold(threshold_arg):
    unit, val = _parse_threshold(threshold_arg)
    mem = psutil.virtual_memory()
    if unit == "gb": return mem.available / (1024**3) < val
    return mem.available / mem.total * 100 < val
```

---

## 五、安装方式

```bash
# 在线安装
pip install --user git+https://github.com/chenqihengchengdu/sysmon.git

# 本地安装
tar -xzf sysmon.tar.gz && cd sysmon && pip install --user -e .

# PATH 修复
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

**特点：** 不需要 sudo，不需要 root，不需要 docker。

---

## 六、数据库设计

```
~/.local/share/sysmon/sysmon.db  (SQLite)

CREATE TABLE records (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,     -- "2026-07-02 14:30:00"
    username  TEXT    NOT NULL,
    mem_bytes INTEGER NOT NULL,     -- RSS bytes
    mem_pct   REAL    NOT NULL,     -- 百分比
    cpu_pct   REAL    NOT NULL      -- 百分比（已归一化）
);

CREATE INDEX idx_ts_user ON records(timestamp, username);

~/.local/share/sysmon/alert.json  (报警配置)
{"threshold": "50G", "row": 9}
```

---

## 七、开发历程

### v0.1 — 基础功能
- 实时柱状图：按用户聚合 CPU/内存，ANSI 彩色
- 历史折线图：SQLite 存储，7 天走势
- crontab 自动记录

### v0.1.1 — 复盘分析
- `--review` 命令：找出短时间内增长最快的用户
- 柱状图展示峰值和触发时间

### v0.2.0 — 报警系统 + 简化命令
- `-alert start/stat/stop` 子命令
- wall 广播通知所有在线用户
- `--row` 控制报警消息重复行数
- 所有一级命令改为 `-` 前缀（`-history`、`-review` 等）
- 去除 pyproject.toml，仅用 setup.py（最大兼容性）
- 去掉 email 功能（需 sendmail，灵皴用户环境不可用）
- README 英文完整文档
- docs/sysmon-guide-zh.html 中文使用说明

### 踩坑记录
1. **build-backend 错误**：`setuptools.backends._legacy:_Backend` 不存在，改成 `setuptools.build_meta`
2. **nargs 冲突**：`-h` 与 argparse `--help` 冲突，改用 `-hour`
3. **cron 参数传递**：`nargs='?'` 只消费一个参数 → 改 `nargs='*'`
4. **ANSI 被 wall 显示**：`\033[31m` 在 wall 中不渲染 → 去掉颜色，用 `!!!` + 大写
5. **CPU 始终 0%**：psutil cpu_percent() 首次返回 0 → 两轮采样

---

## 八、完整命令速查

| 命令 | 说明 |
|------|------|
| `sysmon` | 实时柱状图（前 5 用户） |
| `sysmon -all` | 所有用户 |
| `sysmon -user <name>` | 单人 CPU+MEM 双线图 |
| `sysmon -history` | 7 天内存走势 |
| `sysmon -history --cpu` | 7 天 CPU 走势 |
| `sysmon -review` | 复盘 12h 内存波动 |
| `sysmon -review --cpu` | 复盘 12h CPU 波动 |
| `sysmon -review --hour N` | 复盘 N 小时 |
| `sysmon -record` | 记录快照 |
| `sysmon -alert start 50G` | 开启报警 |
| `sysmon -alert start 20%` | 百分比报警 |
| `sysmon -alert start 50G --row 5` | 报警重复 5 行 |
| `sysmon -alert stat` | 查看报警 |
| `sysmon -alert stop` | 停止报警 |
| `sysmon --help` | 帮助 |

---

## 九、附录：全部源代码

### 9.1 setup.py

```python
from setuptools import setup, find_packages

setup(
    name="sysmon",
    version="0.2.0",
    description="Terminal system resource monitor — live bar charts, history trends, spike review",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    python_requires=">=3.9",
    install_requires=["psutil>=5.0"],
    packages=find_packages(),
    entry_points={"console_scripts": ["sysmon = sysmon.cli:main"]},
)
```

### 9.2 sysmon/collector.py

```python
"""Collect CPU and memory usage aggregated by user."""
import time
import psutil

def get_total_memory() -> int:
    return psutil.virtual_memory().total

def collect_by_user() -> list[dict]:
    procs: dict[int, dict] = {}
    for proc in psutil.process_iter(["username", "memory_info"]):
        try:
            _ = proc.cpu_percent()
            info = proc.info
            username = info["username"] or "?"
            mem_bytes = info["memory_info"].rss
            procs[proc.pid] = {"proc": proc, "username": username, "mem_bytes": mem_bytes}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.2)

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
```

### 9.3 sysmon/storage.py

```python
"""SQLite storage for CPU/memory history records."""
import os, sqlite3
from datetime import datetime, timedelta

DB_DIR = os.path.expanduser("~/.local/share/sysmon")
DB_PATH = os.path.join(DB_DIR, "sysmon.db")

def _ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL, username TEXT NOT NULL,
        mem_bytes INTEGER NOT NULL, mem_pct REAL NOT NULL, cpu_pct REAL NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts_user ON records(timestamp, username)")
    conn.commit()
    return conn

def insert_snapshot(data: list[dict]):
    conn = _ensure_db()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [(ts, d["username"], d["mem_bytes"], d["mem_pct"], d["cpu_pct"]) for d in data]
    conn.executemany("INSERT INTO records (timestamp,username,mem_bytes,mem_pct,cpu_pct) VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

def query_history(days: int = 7):
    conn = _ensure_db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
        username, AVG(mem_pct), AVG(cpu_pct) FROM records WHERE timestamp >= ?
        GROUP BY hour, username ORDER BY hour, username""", (since,)).fetchall()
    conn.close()
    result = {}
    for hour, username, avg_mem, avg_cpu in rows:
        if username not in result: result[username] = []
        result[username].append((hour, round(avg_mem, 1), round(avg_cpu, 1)))
    return result

def query_review(hours: int = 12, metric: str = "cpu"):
    conn = _ensure_db()
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    col = "cpu_pct" if metric == "cpu" else "mem_pct"
    rows = conn.execute(f"SELECT timestamp, username, {col} FROM records WHERE timestamp >= ? ORDER BY username, timestamp", (since,)).fetchall()
    conn.close()
    if not rows: return []
    user_data = {}
    for ts, username, val in rows:
        if username not in user_data: user_data[username] = []
        user_data[username].append((ts, val))
    spikes = []
    for username, points in user_data.items():
        if len(points) < 2: continue
        max_spike, peak_time = 0.0, points[0][0]
        for i in range(1, len(points)):
            diff = points[i][1] - points[i-1][1]
            if diff > max_spike: max_spike, peak_time = diff, points[i][0]
        if max_spike > 0.1:
            spikes.append({"username": username, "max_spike": round(max_spike, 1), "peak_time": peak_time})
    spikes.sort(key=lambda s: s["max_spike"], reverse=True)
    return spikes[:10]

def query_user_history(username: str, days: int = 7):
    conn = _ensure_db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("SELECT timestamp, mem_pct, cpu_pct FROM records WHERE username = ? AND timestamp >= ? ORDER BY timestamp", (username, since)).fetchall()
    conn.close()
    return rows
```

### 9.4 sysmon/cli.py（报警核心逻辑）

```python
# Alert config storage
ALERT_DIR = os.path.expanduser("~/.local/share/sysmon")
ALERT_FILE = os.path.join(ALERT_DIR, "alert.json")
_CRON_MARKER = "# sysmon-auto-alert"
DEFAULT_ALERT = "50G"
DEFAULT_ROW = 9

def _install_cron(threshold_arg):
    cmd = f"* * * * * {sys.executable} -m sysmon.cli __cron_check__ {threshold_arg} {_CRON_MARKER}"
    existing = subprocess.check_output(["crontab", "-l"], ...)
    lines = [l for l in existing.splitlines() if _CRON_MARKER not in l]
    lines.append(cmd)
    subprocess.run(["crontab", "-"], input="\n".join(lines).encode(), check=True)

def _notify_wall(msg: str, repeat: int = 1):
    text = (msg + "\n") * repeat
    subprocess.run(["wall"], input=text.encode(), ...)

def _handle_cron_check(threshold_arg):
    if not _check_threshold(threshold_arg): return 0
    # Alert triggered!
    msg = f"!!! SERVER MEMORY LOW — {desc} | Current: {free_gb:.1f} GB free ({free_pct:.1f}%) !!!"
    cfg = _read_alert_config()
    repeat = cfg.get("row", DEFAULT_ROW) if cfg else DEFAULT_ROW
    _notify_wall(msg, repeat)
    _delete_alert_config()
    _remove_cron()
    return 1
```

### 9.5 sysmon/display.py（终端渲染引擎）

完整代码见项目仓库 `sysmon/display.py`（约 350 行），包含：

- `show_live()`：ANSI 彩色柱状图 + 报警横幅
- `_draw_line_chart()`：通用折线图引擎（12 行高、多用户多色、重叠时半块标识）
- `show_history()`：7 天走势 Top 5 用户
- `show_review()`：复盘柱状图
- `show_user_detail()`：单人 MEM(蓝)+CPU(红) 双线图
- `check_alerts()`：报警阈值检查

---

*文档生成时间: 2026-07-02 | sysmon v0.2.0*
