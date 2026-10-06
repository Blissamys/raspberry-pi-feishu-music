#!/usr/bin/env python3
"""Feishu dialog remote control via official WebSocket long connection.

No public domain needed. The Pi only needs outbound internet.

    pip install lark-oapi
    export FEISHU_APP_ID=cli_xxx
    export FEISHU_APP_SECRET=xxx
    export FEISHU_ALLOW_OPEN_IDS=ou_xxx
    python3 feishu_bot.py

Console order:
  1) Start this process first (must show connected)
  2) 事件与回调 → 事件配置 → 使用长连接接收事件 → 保存
  3) 添加事件：im.message.receive_v1
  4) 回调配置也可选长连接（卡片按钮才用；纯文字遥控可先不管）
  5) Click 验证
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

from commands import allowed_open_id, parse_command
from download_core import INBOX_DEFAULT, search_and_download
from export_to_player import DEST_SUBDIR_DEFAULT, delete_local_audio, export_once, format_library_list

HELP = """遥控命令（须按固定格式）：
• 歌曲歌名 — 例如：歌曲晴天
• 盘 — 列出树莓派 inbox 和 SD 卡上的歌曲
• 删除本地 关键词 — 例如：删除本地 晴天
• 删除本地全部 — 清空 inbox 里所有音频
• 导入 — 把已下载歌曲写入 SD
• 进度 — 当前任务
• 帮助

未以「歌曲」开头的句子不会下载。
导入完成后进度显示「导入完成」再拔卡。"""

_lock = threading.Lock()
_job = {"state": "idle", "detail": "没有进行中的任务"}
_app_id = ""
_app_secret = ""


def _set_job(state: str, detail: str) -> None:
    with _lock:
        _job["state"] = state
        _job["detail"] = detail


def _get_job() -> str:
    with _lock:
        return f"{_job['state']}：{_job['detail']}"


def handle_command(cmd: str, arg: str, message_id: str = "") -> str:
    if cmd in {"empty", "help"}:
        return HELP
    if cmd == "status":
        return _get_job()
    if cmd == "disks":
        return format_library_list()
    if cmd == "delete_local":
        return delete_local_audio(arg)
    if cmd == "export":
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
        _set_job("running", "正在导入 SD")

        def work() -> None:
            try:
                dest = export_once(
                    source=INBOX_DEFAULT,
                    dest_subdir=DEST_SUBDIR_DEFAULT,
                    unmount=True,
                    progress=lambda line: _set_job("running", line[-80:] if line else "导入中"),
                )
                _set_job("idle", f"导入完成 → {dest}。请拔卡插入艾利和。")
            except Exception as e:
                _set_job("idle", f"导入失败：{e}")

        threading.Thread(target=work, daemon=True).start()
        return "开始把 inbox 写入 USB 上的 SD。完成后发「进度」查看。写完请拔卡再插入艾利和。"
    if cmd == "download":
        if not arg:
            return "请写成：歌曲歌名\n例如：歌曲晴天"
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
        _set_job("running", f"正在下载 {arg}")
        origin = message_id

        def work() -> None:
            try:
                title, dest, details = search_and_download(arg, INBOX_DEFAULT)
                text = (
                    f"已下载 {title}\n"
                    f"{details}\n"
                    f"目录 {dest}\n"
                    "发「导入」写入 SD。"
                )
                _set_job("idle", text)
                if origin:
                    reply_text(origin, text)
            except Exception as e:
                err = f"下载失败：{e}"
                _set_job("idle", err)
                if origin:
                    reply_text(origin, err)

        threading.Thread(target=work, daemon=True).start()
        return f"开始搜索并下载：{arg}\n完成后发「进度」或「导入」。"
    if cmd == "unknown":
        return (
            f"无法识别：{arg}\n"
            "下载必须写成：歌曲歌名\n"
            "例如：歌曲晴天\n"
            "导入发「导入」，查状态发「进度」。"
        )
    return HELP


def reply_text(message_id: str, text: str) -> None:
    client = lark.Client.builder().app_id(_app_id).app_secret(_app_secret).build()
    req = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .msg_type("text")
            .build()
        )
        .build()
    )
    resp = client.im.v1.message.reply(req)
    if not resp.success():
        print(f"reply failed code={resp.code} msg={resp.msg} log_id={resp.get_log_id()}")


def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    event = data.event
    message = event.message
    open_id = ""
    if event.sender and event.sender.sender_id:
        open_id = event.sender.sender_id.open_id or ""
    if not allowed_open_id(open_id):
        if message.message_id:
            reply_text(
                message.message_id,
                f"未授权。你的 open_id 是：\n{open_id}\n请把它填进树莓派的 FEISHU_ALLOW_OPEN_IDS 后重启。",
            )
        return
    if message.message_type != "text":
        reply_text(message.message_id, "请发文字。可用飞书语音转文字后再发。")
        return
    try:
        content = json.loads(message.content or "{}")
        text = content.get("text") or ""
    except json.JSONDecodeError:
        text = ""
    p2p = (message.chat_type or "") in {"p2p", "private"}
    cmd, arg = parse_command(text, p2p=p2p)
    reply_text(message.message_id, handle_command(cmd, arg, message_id=message.message_id))


def main() -> None:
    global _app_id, _app_secret
    _app_id = os.environ.get("FEISHU_APP_ID", "")
    _app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not _app_id or not _app_secret:
        raise SystemExit("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
    if not os.environ.get("FEISHU_ALLOW_OPEN_IDS"):
        print("警告：FEISHU_ALLOW_OPEN_IDS 为空时将拒绝所有人")
    Path(INBOX_DEFAULT).mkdir(parents=True, exist_ok=True)

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    cli = lark.ws.Client(
        _app_id,
        _app_secret,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    print("connecting Feishu long connection… then save 长连接 in the console")
    cli.start()


if __name__ == "__main__":
    main()
