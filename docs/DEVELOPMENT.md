# 本地开发

## 工作区

在 Mac 上打开本仓库根目录。不要把树莓派 `feishu.env` 或 `~/Music` 同步进 Git。

## 命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python3 -m pytest -q
python3 -m py_compile commands.py download_core.py export_to_player.py feishu_bot.py
```

Mac 桌面 GUI（可选）：

```bash
pip install -r requirements-gui.txt
python3 musicdownload.py
```

飞书机器人需要真实 `FEISHU_*` 环境变量，且会占用该应用唯一长连接。本地和树莓派不要同时用同一应用跑两个 `lark.ws.Client`。

## 测试范围

`tests/` 覆盖命令解析、白名单、临时目录下列表/删除。不访问飞书、不调用 musicdl、不挂载 USB。

## 关键模块

- `commands.parse_command`：把用户文本映射到 `download` / `disks` / `export` 等。
- `download_core.search_and_download`：musicdl 搜索第一首、下载、平铺、tinytag 详情。
- `export_to_player`：`lsblk` 识别 USB FAT/exFAT、`format_library_list`、`delete_local_audio`、`export_once`（rsync）。
- `feishu_bot.py`：长连接、回复、后台线程任务。

## 已知限制

- 每个关键词只下载搜索结果第一首。
- 旧下载可能仍在 `KuwoMusicClient/...` 子目录；新逻辑才平铺到 inbox 根目录。
- 「盘」列出 SD 时若卡未识别会失败；读卡器多槽空位容量为 0B，不要格式化。
- 飞书文本长度有限，「盘」最多各列 40 首。
- 码率依赖 tinytag，个别文件可能显示未知。
- 上游 GUI 需要 Python 3.13 的说明来自上游 README，树莓派用系统 Python 即可跑 bot。

## 常见问题

- 私聊无输入框：应用未发布或未加机器人能力。见 DEPLOYMENT。
- 误把闲聊当下载：必须使用 `歌曲` 前缀。
- scp 后逻辑没变：服务未重启，或在 Mac 上执行了派上的命令。
- `FSTAB_LABEL is not defined`：旧版 `export_to_player.py` 的 bug，更新该文件后重启服务。
