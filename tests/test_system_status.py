from types import SimpleNamespace

import pytest

import system_status as s
from commands import parse_command


def test_system_status_commands_keep_task_status():
    for text in ('系统状态', '树莓派状态', '运行状态', '硬件状态'):
        assert parse_command(text) == ('system_status', '')
    assert parse_command('状态') == ('status', '')
    assert parse_command('进度') == ('status', '')


def test_cpu_usage_does_not_double_count_guest(monkeypatch):
    samples = iter(['cpu 100 0 50 850 0 0 0 0 20 0\n',
                    'cpu 130 0 60 910 0 0 0 0 30 0\n'])
    monkeypatch.setattr(s, '_read', lambda path: next(samples))
    monkeypatch.setattr(s.time, 'sleep', lambda seconds: None)
    assert s.cpu_usage() == '40.0%（短时采样）'


def test_memory_uses_available_and_handles_no_swap(monkeypatch):
    monkeypatch.setattr(s, '_read', lambda path: 'MemTotal: 4096000 kB\nMemAvailable: 3072000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n')
    text = s.memory_status()
    assert '25.0%' in text
    assert 'Swap：未启用' in text


def test_throttling_current_and_historical_are_distinct(monkeypatch):
    monkeypatch.setattr(s.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='throttled=0x10000\n'))
    text = s.power_status()
    assert '当前正常' in text
    assert '曾欠压' in text


def test_missing_metrics_do_not_break_report(monkeypatch, tmp_path):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError('unavailable')
    monkeypatch.setattr(s, '_read', unavailable)
    monkeypatch.setattr(s.os, 'getloadavg', unavailable)
    monkeypatch.setattr(s.subprocess, 'run', unavailable)
    monkeypatch.setattr(s.shutil, 'disk_usage', unavailable)
    text = s.format_system_status(tmp_path)
    assert '树莓派系统状态' in text
    assert text.count('不可用') >= 6
