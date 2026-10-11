# 接手指南

本文给任何后续开发者或 AI 工具使用，不绑定特定产品。

**先读：** `AGENTS.md` → [docs/STATUS.md](docs/STATUS.md) → 按任务再读 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)、[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)、[docs/LOCAL_LLM.md](docs/LOCAL_LLM.md)。最短交接见 [docs/HANDOFF.md](docs/HANDOFF.md)。

文档可能落后于代码。开始前必须检查：当前分支、`git status`、实际 `.py` 内容是否与文档一致。

## 目标与范围

目标：飞书私聊遥控树莓派下载音乐，并导入 USB 上的播放器 SD。

当前范围：单聊机器人、固定指令、只读系统状态、可选自然语言确认下载、本机 inbox 或 UUID 双盘曲库、去重预览与确认复制。部署状态以 STATUS 为准。

不在范围（未做）：从飞书删除 SD 内歌曲、PDF/曲目清单、OCR、7B 级本地模型、公网 HTTP 回调、OpenClaw。

## 必须保留的行为

- 白名单外的 `open_id` 不得执行下载/导入/删除。
- `歌曲…` 仍表示**立即下载第一条**搜索结果；不要改成必须确认，除非产品明确要求。
- 闲聊不得再被默认当成歌名下载（历史事故）。
- 导入不得把 `.pkl` 等缓存拷到播放器 SD。
- 识别/写入存储时不得操作系统盘 `mmcblk0`。
- 不要提交 `feishu.env`、`.venv`、音频文件；不要在日志或回复中打印密钥。
- 未经用户明确要求，不要重启或修改树莓派上正在运行的服务，不要删除 inbox/SD 里的音乐。
- 不要 `git push --force`。

## 关键入口

| 文件 | 职责 |
|------|------|
| `feishu_bot.py` | `main()` 启动长连接；`on_message` 收消息；`handle_command` 分发 |
| `storage_roles.py` / `library_sync.py` | UUID 双盘角色、歌曲去重预览与确认复制 |
| `system_status.py` | `format_system_status`，只读系统指标 |
| `commands.py` | `parse_command`、`allowed_open_id` |
| `nl_intent.py` | `route_natural_language`（关键词，可选 LLM） |
| `download_core.py` | `search_candidates`、`download_song_info`、`search_and_download` |
| `export_to_player.py` | `format_library_list`、`delete_local_audio`、`export_once` |

## 命令（在仓库根目录）

开发机（已创建 `.venv` 时）：

```bash
python3 -m pytest -q
python3 -m py_compile commands.py nl_intent.py download_core.py export_to_player.py system_status.py feishu_bot.py
```

树莓派运行（需 `feishu.env`，**会占用该飞书应用的唯一长连接**）：

```bash
set -a && source feishu.env && set +a
python3 feishu_bot.py
# 或：sudo systemctl status music-feishu.service
```

单元测试不访问飞书、musicdl、USB。真机下载/导入/LLM 只有现场试过才能写「已验证」。

## 保护运行数据

树莓派（现场目录名 `musicDownload-master`）：

- 密钥：`feishu.env`（勿 scp 覆盖、勿入库）
- 音乐：`~/Music/inbox` 以及 SD 卡
- 服务：`/etc/systemd/system/music-feishu.service`

GitHub 有代码 ≠ 树莓派已部署该版本。部署须显式拷贝文件并重启服务。

## 改完后更新哪些文档

- 行为/接口变化：`README.md`、`docs/ARCHITECTURE.md`、必要时 `docs/DEVELOPMENT.md`
- 部署/飞书/systemd：`docs/DEPLOYMENT.md`
- 进度、验证、与派上差异：只在 `docs/STATUS.md` 维护详细状态
- 本地模型：`docs/LOCAL_LLM.md`
- 约束变化：本文件 `AGENTS.md`
