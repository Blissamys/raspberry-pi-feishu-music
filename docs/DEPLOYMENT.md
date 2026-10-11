# 树莓派部署与维护

以当前代码和已经做过的现场操作为准。密钥只放在未入库的 `feishu.env`。

**GitHub 有新提交 ≠ 树莓派已运行该版本。** 部署 = 拷贝文件 + 重启服务。进度见 [STATUS.md](STATUS.md)。

## 已知环境

| 项 | 值 | 备注 |
|----|----|------|
| 硬件 | 树莓派 4B 4G | 已验证能 SSH、跑 bot、下载 |
| 系统 | Raspberry Pi OS 64-bit Lite | 内核 6.18.x 曾出现在登录横幅 |
| 用户 / 主机 | `shawpi` / `musicpi` | `shawpi@musicpi.local` |
| 项目目录 | `/home/shawpi/musicDownload-master` | 与 GitHub 仓库名不同，历史目录名 |
| Python | 系统 `python3` + `~/musicDownload-master/.venv` | 精确版本待在派上 `python3 --version` 确认 |
| 电源 | 用过 5V 2.1A | 官方建议 ≥3A；欠压风险待长期观察 |
| 曲库卡 | USB 曾为 `/dev/sdd1` vfat ~58G 卷标 `IRIVER` | **设备名会变**，每次 `lsblk` |

系统盘是 `mmcblk0`，不要格式化、不要当曲库。

## 首次安装（环境：树莓派 SSH）

前提：Imager 已刷 Lite 64-bit，已开 SSH/Wi-Fi。执行目录任意，除非注明。

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git rsync exfatprogs dosfstools usbutils
mkdir -p ~/Music/inbox
```

代码：克隆仓库或从开发机 `scp`。目录若保持 `~/musicDownload-master`，与现有 systemd 一致。

```bash
cd ~
# 若从 Git（执行目录：家目录）
# git clone git@github.com:Blissamys/raspberry-pi-feishu-music.git musicDownload-master
cd ~/musicDownload-master
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp feishu.env.example feishu.env
```

编辑 `feishu.env`（必填三项，LLM 可选）。不要提交该文件。

免密挂载（已在本机用过 `sed` 把模板用户换成 `shawpi`）：

```bash
# 执行目录：~/musicDownload-master
# 将 sudoers-iriver-mount 中 YOUR_USER 换成 shawpi 后安装
sudo chmod 440 /etc/sudoers.d/iriver-mount
sudo visudo -c
```

## 飞书应用（以代码为准）

实现：**长连接** `lark.ws.Client`，不是「回调到开发者服务器」。

1. 企业自建应用，添加**机器人**。
2. 权限：读取用户发给机器人的**单聊**消息；以应用身份发消息。不要开「群内所有消息」。
3. 事件：长连接；添加 `im.message.receive_v1`。
4. 回调页：可保持长连接；纯文字路径未注册卡片回调。
5. **创建版本并发布**，可用范围仅自己。未发布会出现「暂时无法给该机器人发消息」（已发生过）。
6. 先在派上启动 bot，再在后台保存长连接并点验证。
7. 私聊拿到 `open_id`（`ou_…`）写入 `FEISHU_ALLOW_OPEN_IDS` 后重启进程。

树莓派需要能访问公网。不需要公网 IP。

## 配置项

复制自 `feishu.env.example`：

| 变量 | 必填 | 获取 | 示例 |
|------|------|------|------|
| `FEISHU_APP_ID` | 是 | 开发者后台 → 凭证与基础信息 | `cli_your_app_id` |
| `FEISHU_APP_SECRET` | 是 | 同上，查看密钥 | `your_app_secret` |
| `FEISHU_ALLOW_OPEN_IDS` | 是 | 未授权时机器人会回复 `ou_…` | `ou_your_open_id` |
| `LLM_ENABLED` | 否 | 本地决定 | `0` |
| `LLM_BASE_URL` | 否 | Ollama 默认 | `http://127.0.0.1:11434/v1` |
| `LLM_MODEL` | 否 | `ollama pull` 的名称 | `qwen2.5:0.5b` |

## systemd

模板在仓库 `music-feishu.service`，须把 `YOUR_USER` 换成 `shawpi`，`WorkingDirectory`/`EnvironmentFile`/`ExecStart` 指向实际路径。

现场已存在：`/etc/systemd/system/music-feishu.service`（用户曾 `restart` 成功）。仓库模板与现场是否逐字节相同：**待确认**。

执行环境：树莓派，需 sudo。

```bash
sudo cp music-feishu.service /etc/systemd/system/   # 先改好 YOUR_USER
sudo systemctl daemon-reload
sudo systemctl enable --now music-feishu.service
sudo systemctl status music-feishu.service --no-pager
sudo systemctl restart music-feishu.service
sudo systemctl stop music-feishu.service
journalctl -u music-feishu.service -n 50 --no-pager
```

从**开发机**远程重启必须分配 TTY（已踩坑）：

```bash
# 执行环境：开发机，不要在已经 SSH 进派的会话里再 ssh -t 空跑
ssh -t shawpi@musicpi.local 'sudo systemctl restart music-feishu.service'
```

已在派上的会话直接 `sudo systemctl restart …`。

## 数据位置与更新时保留

| 路径 | 保留 |
|------|------|
| `feishu.env` | 更新代码时**不要覆盖** |
| `~/Music/inbox` | 用户的下载；不要删除非用户要求 |
| SD / `MUSIC/` | 播放器曲库 |
| `.venv/` | 可重建，勿提交 |

更新（开发机 → 派），执行目录为开发机仓库根：

```bash
scp feishu_bot.py commands.py nl_intent.py download_core.py export_to_player.py system_status.py \
  shawpi@musicpi.local:~/musicDownload-master/
```

若漏传 `nl_intent.py`，新版 `feishu_bot.py` 会无法启动。然后在派上 restart。该 scp 列表含 NL 文件；**是否已对当前派执行过：待确认**。

## SD 卡

执行环境：树莓派。读卡器插入后再执行。

```bash
lsblk -o NAME,PATH,SIZE,FSTYPE,LABEL,TRAN,MOUNTPOINT
# 不要动 mmcblk0。空槽可能是 0B 的 sda/sdb/sdc。
# 卷标命令中的 /dev/sdd1 仅为例，以 lsblk 为准（未验证每次都是 sdd1）
```

导入：

```bash
# 执行目录：~/musicDownload-master，已 source .venv
python3 export_to_player.py --source ~/Music/inbox --dest-subdir MUSIC --unmount
```

可选：`99-iriver-msc.rules` 安装到 `/etc/udev/rules.d/`（自动挂载是否一直在用：**待确认**）。

## 回滚

用 Git 某次 commit 的 `.py` 覆盖派上文件并 restart。不要 force push。派上可先复制一份 `feishu_bot.py.bak`。

## 可选 Ollama

见 [LOCAL_LLM.md](LOCAL_LLM.md)。安装、模型与启用的实际状态见 [STATUS.md](STATUS.md)。可执行文件存在不等于模型已就绪；本轮暂缓拉取模型。

新增系统状态指令时必须同步 system_status.py、commands.py、feishu_bot.py；遗漏 system_status.py 会使新版 bot 导入失败。实际部署状态仍以 STATUS.md 为准。


## 双盘模式部署（待现场验收）

完整新增模块为 library_sync.py、storage_roles.py；需同时更新 commands.py、feishu_bot.py、system_status.py，并创建本机 storage.json。新模块遗漏会导致 bot 导入失败。保留 feishu.env 和服务文件。

storage.json 的 source_uuid/target_uuid 必须先经用户只读识别确认；source_mount 推荐 /home/shawpi/mnt/music-library，target_mount 为现有 /media/iriver。挂载目录仅在实际挂载命令时创建；mount/umount 使用 sudo -n，沿用已有权限，不安装或修改 sudoers/fstab/systemd。权限不足时应报告错误，不写入未挂载目录。

先备份涉及文件和原配置，上传到隔离候选目录并检查依赖/编译；获得用户明确批准后再替换及重启。设备 UUID 配置不包含密钥，但仍不入库。未授权时不迁移原本机 inbox、不格式化、不清理 SD。真机依次验收存储、预览、确认导入、重复导入、卸载及播放器播放；只验证过的阶段才记录通过。


交互优化版本需一起部署 search_ui.py、download_core.py、library_sync.py、commands.py、feishu_bot.py、export_to_player.py。search_ui 为新依赖，不能漏传。保持 storage.json、feishu.env、systemd 单元不变；先备份及隔离候选导入检查，再在用户明确同意后重启。搜索/冲突缓存为内存状态，重启后重新搜索和预览。
