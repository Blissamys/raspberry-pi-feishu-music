# Agent notes

## 这是什么

树莓派飞书遥控下载器。入口是 `feishu_bot.py`（`lark.ws.Client` 长连接），不是 HTTP 回调，也不是 Mac GUI。

## 环境

- 本地仓库：Mac `/Users/shaolc/musicDownload/musicDownload-master`
- 生产：树莓派 `shawpi@musicpi`，`/home/shawpi/musicDownload-master`，systemd `music-feishu.service`
- 密钥：`feishu.env`，永不提交、不在回复中打印

## 开发命令

```bash
python3 -m pytest -q
python3 -m py_compile commands.py download_core.py export_to_player.py feishu_bot.py
```

## 修改约束

- 不要把闲聊重新当成下载；下载必须 `歌曲` 前缀。
- 不要把 `.pkl` 同步到播放器 SD。
- 不要提交 `feishu.env`、`.venv`、音频文件。
- 不要重启或改用户树莓派上正在跑的服务，除非用户明确要求。
- 不要 `git push --force`。不要把 App Secret 写进文档示例以外的占位符。
- 识别 SD 时不要碰 `mmcblk0`。

## 验证

- 解析/删除：跑 `tests/`。
- 飞书、musicdl、USB：只有用户在真机上试过才能写「已验证」。
