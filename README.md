# raspberry-pi-feishu-music

在树莓派上通过**飞书私聊**搜索下载音乐，再把文件导入 USB 读卡器里的 SD 卡，最后把卡插入艾利和播放器使用。桌面 GUI 来自上游 [MrsEWE44/musicDownload](https://github.com/MrsEWE44/musicDownload)（基于 [musicdl](https://github.com/CharlesPikachu/musicdl)），本仓库是面向树莓派 + 飞书的二次开发。

当前打开、提交的是 **Mac 上的本地目录**，不是树莓派远程目录。树莓派实际运行在 `musicpi` 用户 `shawpi` 的 `~/musicDownload-master`。

## 已实现功能

- 飞书长连接收消息（`im.message.receive_v1`），无需公网回调 URL
- 固定格式下载：`歌曲歌名`
- 下载完成后回复文件名、大小、码率、格式（能读到则含时长）
- 下载文件平铺到 `~/Music/inbox`（临时目录 `.musicdl_temp`）
- `盘`：列出本地 inbox 与 SD 卡上的音频
- `删除本地 关键词` / `删除本地全部`
- `导入`：rsync 音频和歌词到 SD 的 `MUSIC/`，排除 `.pkl` 等缓存，可卸载
- systemd 模板：`music-feishu.service`
- Mac 可选 GUI：`musicdownload.py`（PySide6）

## 工作流程

1. 曲库 SD 插入 USB 读卡器，读卡器插树莓派（系统卡仍在板载卡槽）。
2. 飞书发 `歌曲晴天` → 文件进入 `~/Music/inbox`。
3. 发 `导入` → 写入 SD → 进度显示导入完成。
4. 拔卡插入艾利和播放。

## 目录说明

| 路径 | 说明 |
|------|------|
| `feishu_bot.py` | 飞书 WebSocket 机器人入口 |
| `commands.py` | 飞书文本命令解析 |
| `download_core.py` | musicdl 搜索、下载、整理、读标签 |
| `export_to_player.py` | USB 分区识别、列出/删除本地、rsync 导入 |
| `musicdownload.py` | 上游桌面 GUI，树莓派 Lite 不需要 |
| `feishu.env.example` | 飞书环境变量占位符（复制为不提交的 `feishu.env`） |
| `music-feishu.service` | systemd 单元模板，把 `YOUR_USER` 换成实际用户 |
| `sudoers-iriver-mount` | 免密 mount/umount 模板 |
| `99-iriver-msc.rules` | 可选：卷标 `IRIVER` 自动挂载 |
| `docs/` | 部署、开发、状态 |
| `tests/` | 不依赖飞书/硬件的单元测试 |

## 环境要求

- 树莓派 4B 4G，**Raspberry Pi OS 64-bit Lite**（已验证主机名 `musicpi`）
- Python 3.13（当前 Pi OS Trixie 自带）或 3.11+
- 飞书企业自建应用 + 机器人能力，事件长连接
- USB 读卡器 + FAT32/exFAT 曲库卡（建议卷标 `IRIVER`）
- 官方建议电源 5V ≥3A；2.1A 在已能 SSH 的前提下可凑合

## 安装配置（摘要）

```bash
git clone git@github.com:Blissamys/raspberry-pi-feishu-music.git
cd raspberry-pi-feishu-music
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp feishu.env.example feishu.env   # 填入凭证，勿提交
```

完整树莓派步骤见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 启动

```bash
set -a && source feishu.env && set +a
python3 feishu_bot.py
```

或 systemd：`sudo systemctl start music-feishu.service`

## 飞书指令示例

```
歌曲晴天
盘
删除本地 晴天
删除本地全部
导入
进度
帮助
```

密钥只放在 `feishu.env` 或环境变量中，不要写入代码或提交到 Git。
