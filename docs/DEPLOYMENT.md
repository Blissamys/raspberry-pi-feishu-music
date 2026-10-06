# 树莓派部署

本文只记录本项目**已经用过**的做法。不要把飞书 App Secret 写进仓库。

## 已验证的运行环境

- 板子：Raspberry Pi 4B 4G
- 系统：Raspberry Pi OS 64-bit Lite（aarch64，内核 6.18.x）
- 用户 / 主机名：`shawpi` / `musicpi`
- 项目目录：`/home/shawpi/musicDownload-master`
- 本机缓存：`/home/shawpi/Music/inbox`
- 曲库分区示例：USB `/dev/sdd1`（vfat，约 58G，卷标 `IRIVER`）
- 挂载点：`/media/iriver`，导入子目录 `MUSIC/`

Mac 开发目录是 `/Users/shaolc/musicDownload/musicDownload-master`。两边代码可能不同步；更新前用 `scp` 覆盖 `.py` 文件，**不要**用本仓库覆盖派上的 `feishu.env` 和 `~/Music/inbox`。

本次整理**没有** SSH 进树莓派重启服务，也没有删除派上已有音乐。

## 1. 系统与 Python

Imager 刷 Lite 64-bit，打开 SSH、Wi-Fi。登录后：

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git rsync exfatprogs dosfstools usbutils
mkdir -p ~/Music/inbox
```

## 2. 放置代码

从 Git 克隆，或从 Mac 拷贝（勿覆盖 `feishu.env`）：

```bash
# Mac
scp feishu_bot.py commands.py download_core.py export_to_player.py \
  shawpi@musicpi.local:~/musicDownload-master/
```

虚拟环境：

```bash
cd ~/musicDownload-master
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 飞书环境变量

```bash
cp feishu.env.example feishu.env
nano feishu.env
```

填写 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ALLOW_OPEN_IDS`。该文件已被 `.gitignore` 排除。

## 4. 免密挂载

把 `sudoers-iriver-mount` 里的 `YOUR_USER` 换成 `shawpi` 后：

```bash
sudo tee /etc/sudoers.d/iriver-mount < sudoers-iriver-mount.fixed
sudo chmod 440 /etc/sudoers.d/iriver-mount
sudo visudo -c
```

实际用过的命令是 `sed` 替换用户名再 `tee`。

## 5. 飞书接入（真实实现：长连接）

本仓库 **`feishu_bot.py` 使用 `lark.ws.Client` WebSocket 长连接**，不使用「将回调发送至开发者服务器」的 HTTPS URL。

开发者后台：

1. 企业自建应用 → 添加**机器人**能力。
2. 权限：读取用户发给机器人的**单聊**消息；以应用身份发消息。不要开群内所有消息。
3. **事件配置**：订阅方式选**使用长连接接收事件**；添加 `im.message.receive_v1`。
4. **回调配置**：同样可选长连接（卡片按钮才需要额外回调；纯文字遥控未使用卡片回调）。
5. **必须创建版本并发布**，可用范围仅自己。未发布时客户端会显示「暂时无法给该机器人发消息」。
6. **先在树莓派启动** `python3 feishu_bot.py` 或 systemd 服务，再在后台保存长连接并点「验证」。
7. 私聊机器人拿到 `ou_` 填入 `FEISHU_ALLOW_OPEN_IDS` 后重启进程。

树莓派需要能访问公网（连飞书），不需要公网 IP 或域名。

## 6. systemd

将 `music-feishu.service` 中 `YOUR_USER` 换成 `shawpi`，复制到 `/etc/systemd/system/`：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now music-feishu.service
sudo systemctl status music-feishu.service
```

从 Mac 远程重启必须分配 TTY：

```bash
ssh -t shawpi@musicpi.local 'sudo systemctl restart music-feishu.service'
```

无 TTY 时会出现 `sudo: a terminal is required to read the password`。

## 7. 日志

```bash
journalctl -u music-feishu.service -f
```

手动启动则看运行 `feishu_bot.py` 的终端。

## 8. SD 卡

```bash
lsblk -o NAME,PATH,SIZE,FSTYPE,LABEL,TRAN,MOUNTPOINT
# 不要动 mmcblk0（系统卡）。空槽可能显示 sda/sdb/sdc 容量 0B。
sudo fatlabel /dev/sdd1 IRIVER   # 设备名以现场 lsblk 为准
```

导入：

```bash
source .venv/bin/activate
python3 export_to_player.py --source ~/Music/inbox --dest-subdir MUSIC --unmount
```

进度显示导入完成后再拔卡。

可选 udev：`99-iriver-msc.rules` 按卷标 `IRIVER` 自动挂到 `/media/iriver`。

## 9. 更新

1. 在 Mac 拉 Git / 改代码。
2. `scp` 上述 `.py` 到派上（不要覆盖 `feishu.env`）。
3. `ssh -t ... sudo systemctl restart music-feishu.service`。

## 10. 回滚

派上保留旧文件副本，或 `git clone` 到另一目录后把已知可用的 commit 里的 `.py` 拷回去再 restart。仓库若尚无 tag，用 commit hash。不要 `git push --force`。
