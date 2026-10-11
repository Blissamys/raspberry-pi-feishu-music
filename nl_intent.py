"""Optional tiny local LLM + heuristics for Feishu natural language."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional, Tuple

SYSTEM = """你是树莓派音乐助手的意图分类器。只输出一个 JSON 对象，不要其它文字。
字段：
intent: download|delete_local|export|list|status|help|confirm|cancel|chat
query: 歌曲名或删除关键词，没有则空字符串
index: 若用户选第几首，1-3 的整数，否则 0
示例：
帮我下晴天 -> {"intent":"download","query":"晴天","index":0}
删掉本地那首情歌 -> {"intent":"delete_local","query":"情歌","index":0}
写入SD -> {"intent":"export","query":"","index":0}
看看有哪些歌 -> {"intent":"list","query":"","index":0}
对，就这首 -> {"intent":"confirm","query":"","index":0}
不要了 -> {"intent":"cancel","query":"","index":0}
第二首 -> {"intent":"confirm","query":"","index":2}
随便聊聊 -> {"intent":"chat","query":"","index":0}
"""


def llm_enabled() -> bool:
    return os.environ.get("LLM_ENABLED", "").strip() in {"1", "true", "yes"}


def heuristic_intent(text: str) -> Optional[Tuple[str, str]]:
    t = re.sub(r"^(?:请)?(?:帮我)?\s*", "", text.strip()).rstrip(" 。！!")
    if re.fullmatch(r"(?:导入|写入\s*sd|同步到卡|拷到卡|把歌拷到\s*sd)", t, re.I):
        return "export", ""
    if re.search(r"(有哪些歌|看看盘|本地有什么|sd上有什么)", t, re.I):
        return "disks", ""
    if re.search(r"(进度|下完了吗|导完了吗)", t, re.I):
        return "status", ""
    if re.search(r"(帮助|你能做什么)", t, re.I):
        return "help", ""
    m = re.fullmatch(r"(删除本地全部|清空本地|把本地歌全删)", t)
    if m:
        return "delete_local", "全部"
    m = re.fullmatch(r"(删除本地|删掉本地|去掉本地)\s*(.+)", t)
    if m and m.group(2):
        return "delete_local", m.group(2).strip()
    m = re.fullmatch(r"(删掉|删除)\s*(.+)", t)
    if m and m.group(2) and "sd" not in m.group(2).lower():
        return "delete_local", m.group(2).strip()
    m = re.fullmatch(
        r"(?:帮我)?(?:下载|下一下|下首|来一首|我想听|放一首|搜一下)\s*(.+)$",
        t,
    )
    if m and m.group(1):
        return "nl_download", m.group(1).strip(" 。.！!?")
    return None


def _chat_complete(user_text: str) -> Optional[dict]:
    base = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "qwen2.5:0.5b")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0,
            "max_tokens": 120,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def llm_to_command(data: dict) -> Optional[Tuple[str, str]]:
    intent = str(data.get("intent") or "chat")
    query = str(data.get("query") or "").strip()
    try:
        index = int(data.get("index") or 0)
    except (TypeError, ValueError):
        index = 0
    mapping = {
        "download": ("nl_download", query),
        "delete_local": ("delete_local", query),
        "export": ("export", ""),
        "list": ("disks", ""),
        "status": ("status", ""),
        "help": ("help", ""),
        "confirm": ("confirm", str(index or 1)),
        "cancel": ("cancel", ""),
    }
    if intent == "chat":
        return None
    mapped = mapping.get(intent)
    if mapped and mapped[0] == "nl_download" and not query:
        return None
    return mapped


def route_natural_language(text: str) -> Tuple[str, str]:
    hit = heuristic_intent(text)
    if hit:
        return hit
    if llm_enabled():
        data = _chat_complete(text)
        if data:
            mapped = llm_to_command(data)
            if mapped:
                return mapped
    return "unknown", text
