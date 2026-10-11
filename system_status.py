"""Read-only Raspberry Pi health snapshot; no credentials or raw block access."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def _read(path: str) -> str:
    return Path(path).read_text()


def cpu_usage() -> str:
    def sample():
        values = [int(x) for x in _read('/proc/stat').splitlines()[0].split()[1:9]]
        return sum(values), values[3] + values[4]
    total_before, idle_before = sample()
    time.sleep(0.2)
    total_after, idle_after = sample()
    elapsed = total_after - total_before
    if elapsed <= 0:
        raise ValueError('No CPU sample interval')
    percent = 100 * (1 - (idle_after - idle_before) / elapsed)
    return f'{max(0, min(100, percent)):.1f}%（短时采样）'


def _size(n: int) -> str:
    return f'{n / (1024 ** 3):.2f} GiB'


def memory_status() -> str:
    data = {}
    for line in _read('/proc/meminfo').splitlines():
        key, value = line.split(':', 1)
        data[key] = int(value.split()[0]) * 1024
    total, available = data['MemTotal'], data['MemAvailable']
    if total <= 0:
        raise ValueError('Invalid memory total')
    used = max(0, min(total, total - available))
    text = f'{_size(used)} / {_size(total)}（{used / total:.1%}），可用 {_size(available)}'
    swap = data['SwapTotal']
    if swap:
        text += f"\nSwap：{_size(max(0, swap - data['SwapFree']))} / {_size(swap)}"
    else:
        text += '\nSwap：未启用'
    return text


def uptime() -> str:
    seconds = int(float(_read('/proc/uptime').split()[0]))
    return f'{seconds // 86400} 天 {seconds % 86400 // 3600} 小时 {seconds % 3600 // 60} 分钟'


def temperature() -> str:
    return f"{int(_read('/sys/class/thermal/thermal_zone0/temp').strip()) / 1000:.1f} °C"


def load_status() -> str:
    values = os.getloadavg()
    cores = os.cpu_count()
    return ' / '.join(f'{x:.2f}' for x in values) + f'（1/5/15 分钟，{cores or "未知"} 核）'


def disk_status(path: Path) -> str:
    usage = shutil.disk_usage(path)
    return f'可用 {_size(usage.free)} / 共 {_size(usage.total)}（已用 {usage.used / usage.total:.1%}）'


def power_status() -> str:
    result = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True, check=True, timeout=2)
    match = re.fullmatch(r'throttled=(0x[0-9a-fA-F]+)', result.stdout.strip())
    if not match:
        raise ValueError('Unknown throttling response')
    flags = int(match.group(1), 16)
    labels = ['欠压', '频率受限', '降频', '温度软限制']
    current = [label for bit, label in enumerate(labels) if flags & (1 << bit)]
    history = ['曾' + label for bit, label in enumerate(labels) if flags & (1 << (bit + 16))]
    return ('当前：' + '、'.join(current) if current else '当前正常') + '；开机以来：' + ('、'.join(history) if history else '无记录')


def _metric(read) -> str:
    try:
        return read()
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError, subprocess.SubprocessError):
        return '不可用'


def format_system_status(inbox: Path | None = None, inbox_error: str | None = None) -> str:
    inbox = inbox if inbox is not None else Path.home() / 'Music' / 'inbox'
    lines = [f'【树莓派系统状态】{datetime.now():%Y-%m-%d %H:%M:%S}']
    for label, read in [
        ('开机时长', uptime),
        ('CPU 使用率', cpu_usage),
        ('CPU 负载', load_status),
        ('CPU 温度', temperature),
        ('内存', memory_status),
        ('系统文件系统', lambda: disk_status(Path('/'))),
        ('inbox 所在文件系统', lambda: inbox_error or disk_status(inbox)),
        ('供电/降频', power_status),
    ]:
        lines.append(f'{label}：{_metric(read)}')
    lines.append('内存按 total − available 估算；同一文件系统的空间可能重复显示。任务进度请发「进度」。')
    return '\n'.join(lines)
