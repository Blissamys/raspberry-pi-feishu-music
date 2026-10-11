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
    if raw == "换一批":
        return "search_next", ""
    if raw == "上一批":
        return "search_previous", ""
    for prefix, cmd in [("重新搜索", "search_retry"), ("只搜", "search_source"),
                        ("冲突详情", "import_issue_detail"), ("标记同曲", "import_same"),
                        ("跳过冲突", "import_skip"), ("确认新增", "import_add"),
                        ("待处理", "import_issues")]:
        if raw.startswith(prefix):
            return cmd, raw[len(prefix):].strip()
    if raw in {"盘", "列表", "ls", "磁盘"}:
        return "disks", ""
    if raw == "存储":
        return "storage", ""
    if raw == "导入预览":
        return "import_preview", ""
    if raw == "确认导入":
        return "import_confirm", ""
    if raw in {"弹出SD", "弹出sd", "弹出 SD", "弹出卡"}:
        return "eject_sd", ""
    if raw in {"导入", "写入sd", "写入SD", "同步", "导出", "导入sd", "导入SD"}:
        return "export", ""
    if raw in {"进度", "状态"}:
        return "status", ""
    if raw in {"系统状态", "树莓派状态", "运行状态", "硬件状态"}:
        return "system_status", ""
    if raw in {"删除本地全部", "清空本地"}:
        return "delete_local", "全部"
    if raw.startswith("删除本地"):
        return "delete_local", raw[4:].lstrip(" ：:　")
    if raw.startswith("歌曲"):
        keyword = raw[2:].lstrip(" ：:　")
        if not keyword:
            return "download", ""
        return "download", keyword
    if raw in {"确认", "确定", "是", "对", "好", "要", "下载这首", "就是这首"}:
        return "confirm", "1"
    if raw in {"取消", "不要", "不是", "算了"}:
        return "cancel", ""
    if raw in {"1", "2", "3", "一", "二", "三", "第一首", "第二首", "第三首"}:
        num = {"1": "1", "2": "2", "3": "3", "一": "1", "二": "2", "三": "3", "第一首": "1", "第二首": "2", "第三首": "3"}[raw]
        return "confirm", num
    return "unknown", raw


def allowed_open_id(open_id: str) -> bool:
    allow = os.environ.get("FEISHU_ALLOW_OPEN_IDS", "").strip()
    if not allow:
        return False
    return open_id in {x.strip() for x in allow.split(",") if x.strip()}
