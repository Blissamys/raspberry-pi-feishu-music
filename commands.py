"""Feishu text command parser. No network I/O."""

from __future__ import annotations

import os
from typing import Tuple


def parse_command(text: str, p2p: bool = False) -> Tuple[str, str]:
    raw = text.replace("@_user_1", "").strip()
    raw = " ".join(raw.split())
    if not raw:
        return "empty", ""
    if raw in {"帮助", "help", "?", "？"}:
        return "help", ""
    if raw in {"盘", "列表", "ls", "磁盘"}:
        return "disks", ""
    if raw in {"导入", "写入sd", "写入SD", "同步", "导出", "导入sd", "导入SD"}:
        return "export", ""
    if raw in {"进度", "状态"}:
        return "status", ""
    if raw in {"删除本地全部", "清空本地"}:
        return "delete_local", "全部"
    if raw.startswith("删除本地"):
        return "delete_local", raw[4:].lstrip(" ：:　")
    if raw.startswith("歌曲"):
        keyword = raw[2:].lstrip(" ：:　")
        if not keyword:
            return "download", ""
        return "download", keyword
    return "unknown", raw


def allowed_open_id(open_id: str) -> bool:
    allow = os.environ.get("FEISHU_ALLOW_OPEN_IDS", "").strip()
    if not allow:
        return False
    return open_id in {x.strip() for x in allow.split(",") if x.strip()}
