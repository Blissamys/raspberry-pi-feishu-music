# 后续开发

开发在 Git 仓库根目录进行。不要把 `feishu.env` 或 `~/Music` 提交进 Git。状态见 [STATUS.md](STATUS.md)。

## 准备环境

执行目录：仓库根。开发机：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

可选 GUI（开发机，非 Pi Lite 必需）：

```bash
pip install -r requirements-gui.txt
python3 musicdownload.py
```

## 运行与调试

- **单元测试不需要飞书。** 同一飞书应用不要同时在开发机和树莓派跑两个长连接。
- 前台调试（会连飞书，需真实 `feishu.env`）：

```bash
set -a && source feishu.env && set +a
python3 feishu_bot.py
```

- 生产：树莓派 systemd，见 [DEPLOYMENT.md](DEPLOYMENT.md)。
- 调试自然语言确认：看进程日志；内存 `_pending` 重启即丢失。

## 测试

仓库根：

```bash
python3 -m pytest -q
python3 -m py_compile commands.py nl_intent.py download_core.py export_to_player.py system_status.py feishu_bot.py
```

`tests/`：命令解析、白名单、临时目录删除、NL 启发式、bot 确认/取消与任务状态、虚构设备的系统盘拒绝，以及临时目录里的真实 rsync 过滤。需安装 requirements.txt 中的 lark-oapi 和系统 rsync；**不**调用真实 musicdl 下载、飞书 API 或 USB。

需要真机或飞书的验证：

- 下载、导入、艾利和播放、`盘` 读 SD、删除本地、候选确认、Ollama

未跑过的不要写成已通过。

## 如何加飞书指令

1. 在 `commands.py` 的 `parse_command` 增加**固定口令**（优先匹配）。
2. 在 `feishu_bot.handle_command` 增加对应 `cmd` 分支。
3. 若是自然语言，改 `nl_intent.heuristic_intent` 和/或 LLM 的 `SYSTEM` 提示与 `llm_to_command` 映射。
4. 在 `tests/test_commands.py` 或 `tests/test_nl_intent.py` 加断言。
5. 更新 `README.md` 指令表；状态写入 `STATUS.md`。

下载逻辑入口：`download_core.search_candidates` / `download_song_info` / `search_and_download`。导入入口：`export_to_player.export_once`。

## 故障排查

**已发生过：**

| 现象 | 处理 |
|------|------|
| 飞书不能发消息 | 应用未发布 / 无机器人能力 |
| 闲聊被下载 | 必须用 `歌曲` 前缀；NL 下载走确认 |
| `FSTAB_LABEL is not defined` | 更新 `export_to_player.py` 并重启服务 |
| `scp` 后行为不变 | 服务没重启，或在错误的机器上执行了命令 |
| 远程 sudo 无 TTY | `ssh -t` 或在派上执行 sudo |
| 在派上执行空的 `ssh -t` | 已在派上则直接 `sudo systemctl …` |
| 合盖中断 Ollama 安装 | 用 tmux 或保持开发机不休眠后重装 |

**一般建议：** `journalctl -u music-feishu.service -n 50 --no-pager`；确认 `.venv` 路径与单元文件 `ExecStart` 一致；`LLM_ENABLED=1` 但 Ollama 未监听时，关键词仍可用，LLM 分支会失败并回落到 unknown。

## 建议顺序（部分已是现有习惯）

1. 改代码 → `pytest` / `py_compile`（现有）
2. 用户同意后再 `scp` 到派上（现有）
3. 派上 restart（现有；需 TTY 或本地 sudo）
4. 飞书点指令验收（现有）
5. 提交推送（需用户明确要求；本轮文档任务**要求不要做**）

部署后在 `STATUS.md` 更新「派上版本」和验证表。

## musicdl 结果类型

派上 musicdl 2.14.0 返回 SongInfo 对象，支持 get 但不继承 dict。不要用 isinstance(item, dict) 过滤搜索结果，也不要把下载参数转换成普通 dict；download 需要原对象的 source 属性。测试需包含非 dict 的 SongInfo 协议对象，多源网络可用性须另行验证。

系统状态测试见 tests/test_system_status.py：CPU guest 计数、MemAvailable、无 Swap、历史欠压与当前正常的区分、缺失接口降级；test_bot_flow 验证查询不占用或改变下载任务状态。


双盘测试新增 tests/test_library_sync.py 和 tests/test_storage_roles.py，全部使用临时文件或虚构设备；bot 测试覆盖导入转预览、用户隔离、卸载失败以及缺下载盘不回退。部署前需另做 Linux renameat2 与目标 FAT/exFAT 验证，不能仅依靠 macOS 测试。真实 storage.json 不要放入测试工作目录，可从 storage.example.json 复制后在独立部署目录设置 UUID。


三项交互测试补充：tests/test_search_ui.py（版本线索、分页、过期）；test_download_core（跨源同曲保留、来源参数、空下载文件/旧缓存不能冒充成功）；test_library_sync（稳定冲突编号、人工新增不写入、过期/同名/同曲保护、阶段反馈及歌词中断计数）；test_bot_flow（翻页确认、跨用户隔离、来源复用、输入错误提示）；test_storage_safety（旧路径卸载失败不可吞掉）。全部只操作临时目录或 mock 外部调用。
