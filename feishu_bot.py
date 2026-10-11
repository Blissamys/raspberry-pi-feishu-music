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
import time
import re
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

from commands import allowed_open_id, parse_command
from download_core import INBOX_DEFAULT, download_song_info, search_and_download, search_candidates
from export_to_player import DEST_SUBDIR_DEFAULT, delete_local_audio, export_once, format_library_list
from nl_intent import route_natural_language
from system_status import format_system_status
import library_sync
import storage_roles
import search_ui
from export_to_player import _format_audio_block

HELP = """可以说固定指令，或自然语言（需树莓派上的小模型或关键词）。

固定指令：
• 歌曲晴天 — 直接搜第一首并下载
• 盘 / 导入 / 进度 / 删除本地 晴天 / 删除本地全部 / 帮助
• 系统状态 — CPU、温度、内存、磁盘空间、开机时长、供电/降频
• 存储 — 查看下载 U 盘与播放器 SD 的绑定
• 导入预览 → 确认导入 — 跳过同歌名＋歌手的歌曲，保留 SD 版本
• 弹出SD — 同步并安全卸载播放器 SD（下载 U 盘不卸载）
• 换一批 / 上一批 / 只搜QQ 晴天 / 重新搜索 — 比较各来源和版本
• 待处理 / 冲突详情 1 / 标记同曲 1 / 跳过冲突 1 / 确认新增 1
「确认新增」只调整本次计划，仍需「确认导入」才复制，不能覆盖同名文件。
双盘模式下「导入」也先预览；只复制新增项，不删除 SD 已有歌曲。

自然语言示例：
• 帮我下载周杰伦的晴天
• 删掉本地那首情歌
• 把歌拷到SD

搜到候选后会问你：回复「确认」下载第1首，或发 2 / 3，或「取消」。
下载完成后会主动发文件大小、码率、格式。"""

_lock = threading.Lock()
_job = {"state": "idle", "detail": "没有进行中的任务"}
_pending = {}
_import_pending = {}
_last_search = {}
_app_id = ""
_app_secret = ""


def _set_job(state: str, detail: str) -> None:
    with _lock:
        _job["state"] = state
        _job["detail"] = detail
        if state == "idle":
            _job.pop("started", None)
        else:
            _job.setdefault("started", time.monotonic())


def _get_job() -> str:
    with _lock:
        elapsed = f"\n已用时 {int(time.monotonic() - _job['started'])} 秒" if _job['state'] == 'running' and 'started' in _job else ''
        return f"{_job['state']}：{_job['detail']}{elapsed}"


def handle_command(cmd: str, arg: str, message_id: str = "", open_id: str = "") -> str:
    search_sources = None
    if cmd == "unknown" and arg:
        cmd, arg = route_natural_language(arg)
    if cmd in {"empty", "help"}:
        return HELP
    if cmd == "status":
        return _get_job()
    if cmd in {"search_next", "search_previous"}:
        with _lock:
            session = _pending.get(open_id)
            if not session or not session.get("results"):
                return "当前没有可翻页的搜索候选，请先说：帮我下载歌名。"
            try:
                search_ui.move(session, 1 if cmd == "search_next" else -1)
                return search_ui.render(session)
            except ValueError as exc:
                return str(exc)
    if cmd in {"search_retry", "search_source"}:
        with _lock:
            previous = dict(_last_search.get(open_id) or {})
        try:
            if cmd == "search_source":
                source, query = search_ui.source_query(arg)
                search_sources = [source]
                arg = query or previous.get("query", "")
            else:
                arg = arg or previous.get("query", "")
                search_sources = previous.get("sources")
        except ValueError as exc:
            return str(exc)
        if not arg:
            return "请加上歌名，例如：只搜QQ 晴天，或说：帮我下载晴天。"
        cmd = "nl_download"
    if cmd in {"import_issues", "import_issue_detail", "import_same", "import_skip", "import_add"}:
        return _review_import(cmd, arg, open_id)
    if cmd == "system_status":
        if storage_roles.configured():
            try:
                cfg = storage_roles.load_config()
                storage_roles._mounted(cfg.source_uuid, cfg.source_mount)
                return format_system_status(inbox=cfg.source_mount)
            except Exception:
                return format_system_status(inbox_error="下载 U 盘未就绪，容量不可用")
        return format_system_status(inbox=INBOX_DEFAULT)
    if cmd == "storage":
        try:
            return storage_roles.status()
        except Exception as exc:
            return f"存储配置读取失败：{exc}"
    if cmd == "export" and storage_roles.configured():
        cmd = "import_preview"
    if cmd in {"import_preview", "import_confirm", "eject_sd"}:
        return _start_storage_job(cmd, message_id, open_id)
    if cmd in {"disks", "delete_local"}:
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
            _job.update(state="running", detail="正在读取/更新曲库")
        try:
            source = storage_roles.source_directory(INBOX_DEFAULT)
            if cmd == "delete_local":
                return delete_local_audio(arg, inbox=source)
            if storage_roles.configured():
                lines = [storage_roles.status()]
                lines.extend(_format_audio_block("【下载 U 盘】", source, "尚无 inbox 曲库"))
                cfg = storage_roles.load_config()
                try:
                    storage_roles._mounted(cfg.target_uuid, cfg.target_mount)
                    lines.extend(_format_audio_block("【播放器 SD】", cfg.target_mount, "卡未就绪"))
                except ValueError:
                    lines.append("SD 未挂载或未插入；发「导入预览」识别并挂载绑定的卡。")
                return "\n".join(lines)
            return format_library_list()
        except Exception as exc:
            return f"曲库操作失败：{exc}"
        finally:
            _set_job("idle", "曲库操作结束")
    if cmd == "cancel":
        with _lock:
            _pending.pop(open_id, None)
            _import_pending.pop(open_id, None)
        return "已取消待确认操作；已开始的下载/复制不会停止。"
    if cmd == "confirm":
        try:
            idx = max(1, int(arg or 1)) - 1
        except ValueError:
            idx = 0
        with _lock:
            pending = _pending.get(open_id) or {}
            choices = pending.get("choices") or []
            if not choices:
                return "当前没有待确认的下载。可以说：帮我下载晴天"
            try:
                search_ui.ensure_fresh(pending)
            except ValueError as exc:
                return str(exc)
            if idx >= len(choices):
                return f"只有 {len(choices)} 首候选，请发 1 / 2 / 3 或「确认」。"
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
            _job.update(state="running", detail=f"正在下载 {choices[idx]['title']}")
            _pending.pop(open_id, None)
        return _start_download_info(choices[idx]["info"], choices[idx]["title"], message_id)
    if cmd == "export":
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
            _job.update(state="running", detail="正在导入 SD")

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
    if cmd == "nl_download":
        if not arg:
            return "请说出歌名，例如：帮我下载晴天"
        origin = message_id
        oid = open_id
        pending = {"choices": [], "query": arg, "sources": search_sources}
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
            _job.update(state="running", detail=f"正在搜索 {arg}")
            _pending[oid] = pending
            _last_search[oid] = {"query": arg, "sources": search_sources}

        def search_work() -> None:
            found = []
            try:
                with storage_roles.source_session(INBOX_DEFAULT, create=True) as (source, validate):
                    kwargs = {"validate": validate} if validate else {}
                    found = search_candidates(arg, limit=20, work_dir=source, sources=search_sources, diverse=True, **kwargs)
                if not found:
                    msg = f"本次搜索「{arg}」未返回可用候选，不能据此判断歌曲未收录。\n可补充歌手、发「只搜QQ」换源，或「重新搜索」。"
            except Exception as e:
                found = []
                msg = f"搜索未完成：{_failure_hint(e)}\n设备就绪后可发「重新搜索」，也可补充歌手或换源。"
            with _lock:
                if _pending.get(oid) is not pending:
                    _job.update(state="idle", detail="已取消搜索。")
                    return
                if found:
                    pending.update(results=found, created=time.monotonic(), offset=0)
                    msg = search_ui.render(pending)
                else:
                    _pending.pop(oid, None)
                _job.update(state="idle", detail=msg)
            if origin:
                reply_text(origin, msg)

        threading.Thread(target=search_work, daemon=True).start()
        return f"正在按「{arg}」搜索可能的歌曲，找到后请确认再下载。"
    if cmd == "download":
        if not arg:
            return "请写成：歌曲歌名\n例如：歌曲晴天"
        with _lock:
            if _job["state"] == "running":
                return "已有任务进行中：" + _job["detail"]
            _job.update(state="running", detail=f"正在下载 {arg}")
        return _start_keyword_download(arg, message_id)
    if cmd == "unknown":
        return (
            f"无法识别：{arg}\n"
            "可以说：帮我下载晴天\n"
            "或固定指令：歌曲晴天 / 盘 / 导入 / 删除本地 晴天"
        )
    return HELP


def _failure_hint(exc):
    if isinstance(exc, OSError) and exc.errno == 28:
        return "空间不足，请先检查「系统状态」和「存储」。"
    if isinstance(exc, PermissionError):
        return "没有写入或挂载权限，请检查存储目录和挂载权限。"
    text = re.sub(r"https?://\S+", "[地址已省略]", str(exc))[:220]
    return text or type(exc).__name__


def _review_import(cmd, arg, open_id):
    with _lock:
        if _job["state"] == "running":
            return "已有任务进行中：" + _job["detail"]
        pending = _import_pending.get(open_id)
        if not pending or "plan" not in pending:
            return "当前没有待确认的导入，请先发「导入预览」。"
        _job.update(state="running", detail="正在处理导入计划", started=time.monotonic())
    detail = "等待确认：导入计划未变更"
    try:
        raw_index = arg or ("1" if cmd == "import_issues" else "0")
        if not raw_index.isdecimal():
            return "请输入正整数编号，例如：冲突详情 1。"
        index = int(raw_index)
        if index < 1:
            return "请输入正整数编号，例如：冲突详情 1。"
        plan = pending["plan"]
        if cmd == "import_issues":
            return library_sync.format_conflicts(plan, index)
        if cmd == "import_issue_detail":
            return library_sync.conflict_details(plan, index)
        storage_roles.verify_import(pending["config"])
        action = {"import_same":"same", "import_skip":"skip", "import_add":"add"}[cmd]
        updated = library_sync.resolve_conflict(plan, index, action)
        with _lock:
            if _import_pending.get(open_id) is not pending:
                return "计划已取消，请重新预览。"
            pending["plan"] = updated
        detail = library_sync.format_preview(updated)
        return "本次决定已记录，尚未复制或修改音乐。\n" + detail
    except Exception as exc:
        return "未修改计划：" + _failure_hint(exc)
    finally:
        _set_job("idle", detail)


def _start_storage_job(cmd: str, message_id: str, open_id: str) -> str:
    token = {}
    with _lock:
        if _job["state"] == "running":
            return "已有任务进行中：" + _job["detail"]
        if cmd == "import_confirm":
            pending = _import_pending.get(open_id)
            if not pending or "plan" not in pending:
                return "当前没有待确认的导入，请先发「导入预览」。"
            _import_pending.pop(open_id, None)
        elif cmd == "import_preview":
            _import_pending[open_id] = token
        _job.update(state="running", detail="扫描中：正在检查双盘存储", started=time.monotonic())

    def work():
        started = time.monotonic()
        phase, count = "扫描中", 0
        def report(message):
            nonlocal phase
            phase = message.split("：", 1)[0]
            _set_job("running", message)
        try:
            if cmd == "import_preview":
                cfg, source, target = storage_roles.prepare_import()
                with storage_roles.import_session(cfg) as verify:
                    plan = library_sync.preview(source, target, dest_subdir="MUSIC", progress=report)
                    verify()
                text = library_sync.format_preview(plan)
                with _lock:
                    if _import_pending.get(open_id) is not token:
                        _job.update(state="idle", detail="已取消导入预览。")
                        return
                    token.update(plan=plan, config=cfg)
            elif cmd == "import_confirm":
                cfg, plan = pending["config"], pending["plan"]
                with storage_roles.import_session(cfg) as verify:
                    count = library_sync.execute(
                        plan,
                        verify=verify,
                        progress=report,
                    )
                # Failure to sync/unmount is an error, never a safe-to-remove message.
                phase = "安全卸载中"
                report("安全卸载中：同步写入并卸载 SD，请勿拔卡")
                safe = storage_roles.eject_target()
                text = f"导入完成：已复制并校验 {count} 首，跳过重复 {len(plan.duplicates)} 首，待处理 {len(plan.conflicts)} 首。耗时 {int(time.monotonic()-started)} 秒。\n{safe}"
            else:
                report("安全卸载中：同步写入并卸载 SD，请勿拔卡")
                text = storage_roles.eject_target()
            _set_job("idle", text)
        except Exception as exc:
            with _lock:
                if _import_pending.get(open_id) is token:
                    _import_pending.pop(open_id, None)
            completed = exc.completed if isinstance(exc, library_sync.ImportInterrupted) else count
            reason = exc.cause if isinstance(exc, library_sync.ImportInterrupted) else exc
            next_step = '可发「弹出SD」重试卸载，无须重复复制。' if phase == "安全卸载中" else '先发「存储」检查设备，再重新「导入预览」；已完成歌曲会跳过。'
            text = f"{phase}未完成：{_failure_hint(reason)}\n本次已完成 {completed} 首音频。请勿拔卡。{next_step}"
            _set_job("idle", text)
        if message_id:
            reply_text(message_id, text)

    threading.Thread(target=work, daemon=True).start()
    if cmd == "import_preview":
        return "正在扫描两盘曲库生成预览，不复制或删除音乐。完成后回复「确认导入」。"
    if cmd == "import_confirm":
        return "正在按预览复制新增歌曲并校验；请等明确的安全卸载提示后再拔卡。"
    return "正在同步并卸载播放器 SD，请等完成提示。"


def _start_keyword_download(keyword: str, message_id: str) -> str:
    origin = message_id

    def work() -> None:
        try:
            with storage_roles.source_session(INBOX_DEFAULT, create=True) as (source, validate):
                kwargs = {"validate": validate} if validate else {}
                title, dest, details = search_and_download(keyword, source, **kwargs)
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
            err = f"下载未完成：{_failure_hint(e)}\n检查「存储」后，可用自然语言重新搜索并换源。"
            _set_job("idle", err)
            if origin:
                reply_text(origin, err)

    threading.Thread(target=work, daemon=True).start()
    return f"开始搜索并下载：{keyword}\n完成后会主动发详情，也可发「进度」。"


def _start_download_info(song_info: dict, title: str, message_id: str) -> str:
    origin = message_id

    def work() -> None:
        try:
            with storage_roles.source_session(INBOX_DEFAULT, create=True) as (source, validate):
                kwargs = {"validate": validate} if validate else {}
                got_title, dest, details = download_song_info(song_info, source, **kwargs)
            text = (
                f"已下载 {got_title}\n"
                f"{details}\n"
                f"目录 {dest}\n"
                "发「导入」写入 SD。"
            )
            _set_job("idle", text)
            if origin:
                reply_text(origin, text)
        except Exception as e:
            err = f"下载未完成：{_failure_hint(e)}\n检查「存储」后，可用自然语言重新搜索并换源。"
            _set_job("idle", err)
            if origin:
                reply_text(origin, err)

    threading.Thread(target=work, daemon=True).start()
    return f"开始下载：{title}\n完成后会主动发大小、码率、格式。"


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
    reply_text(
        message.message_id,
        handle_command(cmd, arg, message_id=message.message_id, open_id=open_id),
    )


def main() -> None:
    global _app_id, _app_secret
    _app_id = os.environ.get("FEISHU_APP_ID", "")
    _app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not _app_id or not _app_secret:
        raise SystemExit("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
    if not os.environ.get("FEISHU_ALLOW_OPEN_IDS"):
        print("警告：FEISHU_ALLOW_OPEN_IDS 为空时将拒绝所有人")
    if not storage_roles.configured():
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
