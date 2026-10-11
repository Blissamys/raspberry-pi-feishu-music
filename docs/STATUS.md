# 当前进度与交接状态

**最后更新：2026-10-11，当前功能版本已提交并归档到 GitHub。三处交互优化已部署、重启并由用户完成飞书验收；未实际触发的写入和异常路径仍按下文标为待验证。** 状态以本页为主；本地测试、真机离线调用和飞书验收分别记录。

## 项目归档状态

- 用户确认当前项目开发完成；此版本进入稳定维护阶段，后续有明确功能需求时再升级。
- 归档范围包括机器人、双盘 UUID 绑定、多源搜索与确认、曲库去重预览、系统状态、部署文档、交接文档和测试。
- 归档不包含 `feishu.env`、真实 `storage.json`、音频、缓存、虚拟环境或树莓派运行数据。
- 线上运行版本已核实：PID 4910，于 2026-10-11 20:05:46 CST 启动，服务和飞书长连接正常；六个交互优化文件哈希匹配已部署候选。
- 用户已验收搜索候选、分页、来源切换、取消、导入预览和进度。真实确认导入、冲突决定、安全卸载失败恢复仍未实际触发，不能因归档改写为已通过。
- 归档前重新执行全量测试：114 passed、1 个 SDK 弃用警告；核心模块编译通过，暂存差异检查通过。扫描 40 个归档文件，没有发现私钥、真实飞书凭证、GitHub token、音频或超过 5 MiB 的文件。
- `origin/main` 在提交前与本地基线一致。功能归档提交为 `b8326f9`（`Archive stable Feishu Pi music station`），已通过普通 `git push origin main` 推送；未 force push。

## 第五轮部署：搜索、导入反馈与冲突交互（2026-10-11）

- 用户明确同意本轮部署并单次重启。部署前重新执行全量测试：**114 passed**，1 个 SDK datetime 弃用警告；六个模块编译通过。
- 部署前线上仍为 2026-10-09 22:27:04 启动的 PID 1522，active/running、NRestarts=0；`search_ui.py` 原先不存在，其余五文件为上一轮双盘版本。
- 备份目录：`/home/shawpi/musicDownload-master/deploy-backups/20261011-181020-interaction/`。包含原文件、manifest.json 与 candidate/；manifest 记录 `search_ui.py` 原先缺失。
- 候选六文件在派上逐项核对 SHA-256、内存编译和导入通过；临时目录冒烟验证了搜索来源/分页、冲突“确认新增”只改计划、确认执行后复制和复制/校验阶段反馈。没有启动第二条飞书连接、请求音乐源或访问真实音乐。
- 六文件已按 `search_ui.py`、`download_core.py`、`library_sync.py`、`export_to_player.py`、`commands.py`、`feishu_bot.py` 顺序原子替换，并与本地清单一致。保留 `storage.json`、`feishu.env`、systemd 和音乐。
- `sudo -n systemctl restart music-feishu.service` 返回需要密码，未执行重启。复核仍为 PID 1522、2026-10-09 22:27:04 启动、active/running、NRestarts=0。
- 用户随后在 Mac 终端完成重启。只读核实新 PID **4910**，启动于 **2026-10-11 20:05:46 CST**，active/running、ExecMainStatus=0、NRestarts=0；六文件哈希全部匹配本轮候选。
- 当前进程日志摘要 2 条，连接成功信号 1 条，traceback 0、error/failed 信号 0；派上导入 `commands`、`search_ui`、`library_sync`、`feishu_bot` 成功，新指令解析为预期。新版进程已生效，本次核查未再次重启或操作音乐。
- 下一步由用户在飞书验收搜索分页/来源切换、导入阶段反馈和冲突处理。未执行真实下载或确认导入时，不能把这些交互记为端到端通过。
- 用户随后回复“已验收”。按此前给出的验收顺序，记录为飞书端已验证：自然语言搜索候选、换一批、上一批、只搜 QQ、取消、导入预览、进度。用户没有提供逐条回复文本或截图，因此只记录总体通过，不补写具体候选数量、来源或预览数字。
- 本次验收明确要求先不要发送 `确认导入` 或 `确认新增`；因此真实音乐复制、复制中断恢复、安全卸载，以及有冲突时的 `待处理` / `冲突详情` / `标记同曲` / `跳过冲突` / `确认新增` 仍不能记为飞书真机通过。
- 本轮未真实下载、复制、删除或卸载音乐，未修改存储绑定，未 commit/push。飞书的新分页、来源切换、冲突处理和阶段反馈均未做端到端验收。

## 搜索、导入反馈、冲突处理优化（本地完成，待部署）

- 用户要求优化先前提出的三处交互，并要求继续实施；当前未明确批准本轮部署/重启。线上仍为上一轮已核实双盘版本。
- 搜索：新 search_ui.py 展示来源、标题中的版本线索及源站标注格式/大小。最多缓存20条，各来源轮流排列，来源不同的同曲可比较；每页3条，1/2/3只选当前页。支持换一批/上一批/只搜QQ（网易云/酷我/酷狗）/重新搜索，关键词历史及候选按 open_id 隔离，候选10分钟过期。歌曲前缀仍第一条立即下载。空结果不会断言源站没收录。
- 导入：扫描→等待确认→复制→校验→安全卸载，进度含当前文件、字节/数量及用时；复制中断保留并报告已完成音频数，卸载失败提示仅重试弹出、不重复复制。旧单盘入口也不再忽略 umount 失败。
- 冲突：待处理分页、稳定编号、冲突详情、标记同曲/跳过冲突/确认新增。决定仅修改当前用户的内存计划，不改标签或文件、不续期；确认新增仍需确认导入，不能绕过同名/父路径/计划内歌曲重复/空间/设备/快照检查。同曲/跳过不创建永久别名规则。未处理项不复制，其它已确定项可继续导入。
- 独立审查发现并修复：目标父路径已是文件但仍允许加入计划；下载器直接返回旧缓存路径绕过原回退分支的新文件校验。补强后，预览/人工新增/执行前均检查父路径和大小写冲突；下载返回路径与回退发现共享“本次新/变更、非空、音频扩展名、在工作目录内且无符号链接”检查，排除规范化路径别名绕过。
- 全量 `.venv/bin/python -m pytest -q`：**114 passed**，1 个 SDK datetime 弃用警告；本轮六模块编译通过。全部新增写操作测试仅用临时文件，未使用真实音乐。
- 文档已更新 README、ARCHITECTURE、DEVELOPMENT、DEPLOYMENT 和 docs/plans/2026-10-09-interaction-upgrade.md。新版本没有 SSH 上传、飞书发消息、下载、写卡、删除、重启、Git commit/push。功能未记为真机通过。
- 本轮待部署六文件：search_ui.py、download_core.py、library_sync.py、commands.py、feishu_bot.py、export_to_player.py。哈希清单位于本机 `/private/tmp/musicpi-interaction-manifest.json`。保留 storage.json、feishu.env、systemd 单元和所有音乐；新 search_ui 模块不可漏传。
- 获得明确批准后备份、上传候选、派上导入检查，替换并单次重启。重启后先验收搜索翻页/来源、待处理详情和计划级决定；实际下载/导入由用户明确触发。

## 第四轮部署：更换下载盘并启用双盘（2026-10-09）

- 用户在批准双盘部署、一次重启及挂载生成预览后，更换了下载保存盘。只读重新识别：唯一新下载盘 **SX7 64G，58.6 GB，exFAT，UUID C20E-4B34**；播放器 SD 仍为 **IRIVER，57.6 GB，vfat，UUID 027C-1AF3**。旧 S 盘 FD9C-1C1A 已不再用于配置。
- 派上核实双盘模块/配置此前尚未安装，旧服务 PID 1110，启动于 2026-10-09 20:44:25 CST。2026-10-07 的部署操作停在备份阶段，未上传或替换。
- 本次备份目录 `/home/shawpi/musicDownload-master/deploy-backups/20261009-222233/`；manifest 记录 library_sync.py、storage_roles.py、storage.json 原先缺失，其余四个原文件已备份。候选和 SHA-256 清单位于 candidate/。
- 本地重跑 **85 passed**，1 个 SDK 弃用警告；派上候选六模块哈希、语法、导入通过，无第二条 WebSocket。配置改为 source_uuid=C20E-4B34，target_uuid=027C-1AF3。
- **真实挂载已通过：** SX7 挂载 `/home/shawpi/mnt/music-library`，IRIVER 挂载 `/media/iriver`；仅创建挂载目录并将空源挂载点底层设为 0555，未格式化、改 fstab/sudoers/systemd。
- **真实预览已通过：** 源 U 盘音频 0 首、SD 音频 6 首、新增 0、重复 0、冲突 0、SD 已有重复 0、SD 缺标签 0、所需空间 0。结果保存在备份目录 preview-summary.json；这是独立候选进程的检查，不是正在运行 bot 中可直接确认的计划。
- 两盘保持挂载；尚未执行真实歌曲复制/删除。原树莓派本机 inbox 未迁移，新 U 盘仍无音频。实际写入、重复导入、卸载和播放器播放仍未验收。
- 六个模块和 storage.json 已逐项原子替换进运行目录并核对清单，入口 feishu_bot.py 最后替换。清单：本机 `/private/tmp/musicpi-dual-storage-manifest.json`；实际配置 `/private/tmp/musicpi-storage.json`（本机临时文件）和派上项目 storage.json。
- 单次 `sudo -n systemctl restart music-feishu.service` 因需要密码未执行成功。复核仍 active/running、PID 1110、20:44:25 启动、NRestarts=0。此为用户手工重启前的状态；后续成功重启证据见下一条。
- 用户随后完成重启。只读核实新 PID **1522**，启动于 **2026-10-09 22:27:04 CST**，active/running、ExecMainStatus=0、NRestarts=0；六模块及 storage.json 七项哈希全部匹配本次候选。
- 当前进程日志摘要 2 条，连接成功信号 1 条，traceback 0、error/failed 信号 0。SX7 C20E-4B34 仍挂载 /home/shawpi/mnt/music-library，IRIVER 027C-1AF3 仍挂载 /media/iriver。新版进程已生效；此次只读核查未再次重启或复制音乐。
- 下一步用户在飞书发“存储”“导入预览”验收。新 U 盘当前无音频；旧本机 inbox 未迁移。真实下载至新 U 盘、复制/重复导入、卸载和播放器播放仍待各自现场验证。
- 未改 feishu.env、服务单元，未执行真实下载/音乐复制/删除，未 commit/push。SD 仍已挂载，未给可拔卡保证。

## 双 USB 曲库实现记录（旧盘识别为历史，最新部署见上节）

### 用户确认与设备只读识别

- 用户要求固定 U 盘保存下载，插入播放器 SD 后整体增量导入。去重选择：按歌名＋歌手，保留 SD 已有版本、不覆盖。
- 用户明确确认下载盘为 **7.5 GB、卷标 S、UUID FD9C-1C1A**；目标播放器 SD 为 **57.6 GB、卷标 IRIVER、UUID 027C-1AF3**。只读识别时路径分别 /dev/sde1 和 /dev/sdd1，均 vfat、未挂载；设备名不是绑定依据。
- 拟配置下载盘挂载 /home/shawpi/mnt/music-library，新下载写入 inbox/；目标沿用 /media/iriver，复制到 MUSIC/ 并保留源相对路径。导入扫描整个源 U 盘和整个目标 SD，旧树莓派本机 inbox 不自动迁移。
- 实际配置已准备在本机 `/private/tmp/musicpi-storage.json`，未上传/启用。模板 storage.example.json；真实 storage.json 已加入 gitignore。

### 实现

- 新 library_sync.py、storage_roles.py；修改 commands.py、feishu_bot.py、system_status.py、download_core.py。新增“存储”“导入预览”“确认导入”“弹出SD”；双盘模式旧“导入”改为预览，普通“确认”仍只确认下载。
- 临时配置加载失败、缺源盘或设备不符不回退系统目录。所有角色按 UUID 唯一绑定、要求两个物理 USB 设备、拒绝 mmcblk0 和不安全挂载路径。下载盘保持挂载，目标 SD 在确认复制成功并同步/卸载成功后才提示可以拔卡。
- 元数据标准化处理宽窄/大小写/空格和合唱歌手逗号/顿号/分号顺序；不猜跨语言别名或合并 Live/Remix。完全相同内容使用 SHA-256 跳过。既有 SD 重复只报告不删除；缺标签/同路径冲突暂停不覆盖。若 SD 有缺标签音频，无法排除重复的新增项也暂停。
- 预览按用户保存，10 分钟过期，音频/歌词完整快照变化需重做。复制采用 .part + fsync + SHA-256 + Linux renameat2 不覆盖发布；失败保留已复制完整文件。内容完全相同的 SD 音频可补齐缺失歌词。
- 独立代码审查发现并已修复下载过程中设备丢失、目标缺标签静默忽略、歌词失败后无法重试三个问题。下载/导入期间 pin 挂载目录 fd、复验 UUID 和设备身份；新源挂载点未挂载时为 0555。特权强制/懒卸载不在正常运行保证范围。

### 验证与限制

- 本地全量 **85 passed**，1 个 SDK datetime 弃用警告；核心模块编译及所改文件 diff 检查通过。测试只用临时文件与虚构设备。
- 审查员复查认为三项已修复，无新增已确认重要缺陷。
- SSH 曾短暂解析失败，首次重试遇到自动审批超时（未执行）；随后重试已恢复。没有因此修改网络或服务配置。
- 派上独立临时目录实测 Linux renameat2 不覆盖已有文件、复制哈希校验、重复导入通过，使用人工测试字节。**没有做真实 FAT/exFAT 写入、拔盘、卸载或播放器播放验证。**
- 只读检查：/media/iriver 已存在，用户不可直接写；/home/shawpi/mnt 尚不存在。sudo -n -l 对 /usr/bin/mount、/usr/bin/umount 查询返回 0；实际新挂载命令仍待现场验证。未修改 sudoers/fstab/systemd。
- 此段为实现阶段记录；后续 2026-10-09 已上传、挂载并生成真实预览，重启等待终端密码，详见第四轮部署结果。始终未迁移/复制/删除真实音乐。

### 待批准部署

- 部署六文件 library_sync.py、storage_roles.py、commands.py、feishu_bot.py、system_status.py、download_core.py，加绑定配置 storage.json；保留 feishu.env。最新本地哈希清单在 `/private/tmp/musicpi-dual-storage-manifest.json`。
- 先备份、隔离候选导入检查；需要用户明确批准部署和再重启一次，并允许挂载已确认两盘生成真实预览。生成预览不复制音乐；实际复制由用户在飞书发送“确认导入”触发。
- 部署后依次验收“存储”“导入预览”；确认结果后由用户选择是否确认导入。若旧曲只在本机 inbox，另行询问是否复制到下载 U 盘，不能自动迁移/清空。

## 第三轮部署：系统状态指令（2026-10-07 17:23 起）

- 用户已明确批准部署并再次重启一次，不需重复申请本次许可。
- 备份目录：派上 `/home/shawpi/musicDownload-master/deploy-backups/20261007-172301/`，含旧 commands.py、feishu_bot.py、manifest.json（记录 system_status.py 原先缺失），候选保存在 candidate/。
- 本地重跑 51 passed。派上三文件哈希、编译、导入通过；直接调用候选 bot 的 system_status 分支返回真实指标，模拟 running 任务状态保持不变，没有启动第二条长连接。
- 已按 system_status.py → commands.py → feishu_bot.py 顺序原子替换并验证：system_status.py `b54c6ecc2c406db39b4b04001b5772bdd51abdb5d765d51a5f28aae6ece832ba`；commands.py `e8807ff89483cdff23e18a0a91fa31880ebec6b26e74eb99bb0a63710aec4334`；feishu_bot.py `77cbe9eb6dfe3cca8515e991914a0f2d81d3b1c5c663e8f10ca79f24085853f9`。
- `sudo -n systemctl restart music-feishu.service` 返回需要密码，未执行成功；仍 active/running，PID 13771，启动于 17:06:44 CST，NRestarts=0。
- 用户随后完成重启。只读核实新 PID 14256，启动时间 2026-10-07 17:25:59 CST，active/running，ExecMainStatus=0，NRestarts=0；三个文件哈希与本轮部署一致。当前进程日志摘要 2 条，连接成功信号 1 条，traceback 0、error/failed 信号 0。
- 新版进程已启动，下一步由用户在飞书发“系统状态”验收；尚不能将飞书新指令输出记为已验证。助手没有追加重启。
- 未改密钥、systemd 配置、音乐，未 commit/push。

## 系统状态实现与验证记录（已部署并于 17:25:59 重启）

- 用户明确要求通过飞书查看树莓派常用运行参数。新增固定指令“系统状态”，别名“树莓派状态／运行状态／硬件状态”；保留“状态／进度”原来的任务进度含义。
- 新模块 system_status.py；接入 commands.py、feishu_bot.py 及帮助。显示开机时长、CPU 短时使用率与 1/5/15 分钟负载、核数、温度、内存可用/占用、Swap、根及 inbox 所在文件系统空间、当前/历史欠压降频标志。每项异常降级为不可用；固定 vcgencmd 参数、2 秒超时，无 sudo、无任意命令、不读密钥、不操作块设备。
- 本地全量 **51 passed**，1 个 SDK datetime 弃用警告；新增核心模块编译通过。覆盖命令别名、旧状态兼容、下载运行中查询、CPU guest 排除、MemAvailable、无 Swap、历史欠压、缺失接口。
- 2026-10-07 17:19:47 将采集器源代码通过 SSH stdin 在派上内存执行，无运行文件上传/修改。实际输出：开机 1 天 1 小时 33 分钟，CPU 0.0%（短采样）、负载 0.00/0.11/0.12（4 核）、温度 50.1°C，内存 0.46/3.70 GiB（12.5%）、可用 3.24 GiB，Swap 0/4 GiB，文件系统可用 20.16/28.70 GiB；当前供电/降频正常，历史无记录。为当时快照，非持续监控。
- 尚未验证飞书新指令。用户已批准并已上传三个文件；用户已完成本次重启，新进程及连接信号已核实，详见第三轮部署记录。
- 原有下载/删除输入修复已部署；本次未真实下载、删除音乐或重启。未提交/推送 Git。

## 第二轮部署结果（2026-10-07 17:01 起）

### 用户反馈：目标曲真实下载成功

用户提供飞书完成回复：`已下载 そばにいるね - 青山テルマ, SoulJa`，文件 `そばにいるね-青山テルマ, SoulJa-そばにいるね-555142.flac`，186.34 MB，5121 kbps，FLAC / 192000 Hz，5:04，目录 `/home/shawpi/Music/inbox`。据此确认修复后目标歌曲真实下载及详情回复链路成功；未独立检查音频内容或真实采样质量。反馈未展示候选及确认操作，不单独认定确认/取消流程已经验收；未验证该文件导入 SD 或播放器播放。助手未额外下载、删除或重启。


- 用户明确批准将搜索和删除输入两项修复一起部署并重启一次；不需要再征求本次部署许可。
- 备份目录：派上 `/home/shawpi/musicDownload-master/deploy-backups/20261007-170126/`。保存原 download_core.py、export_to_player.py、manifest.json；candidate/ 保存候选版本。
- 本地重新测试 **45 passed**，1 个 SDK 弃用警告。派上候选文件 SHA-256、编译、导入通过；用真实 SongInfo 配合模拟搜索验证结果不丢失；“那首”和复制列表大小的删除测试仅操作独立临时目录的测试文件。
- 两文件已原子替换到运行目录并核对哈希：download_core.py 为 `216d6b54af09f82aeb1ca24488c1dd8a26cf438453256d6746a0fa36cb1a0478`；export_to_player.py 为 `6c5d1f6167c1ef09229a27f0ecdd40260fd6d664065dbc6829ac352115378512`。
- 重启尝试 `sudo -n systemctl restart music-feishu.service` 因 `sudo: a password is required` 未成功执行。随后服务 active/running，PID 11977，启动时间 2026-10-07 00:13:47 CST，NRestarts=0。
- 用户随后在自己终端完成重启。只读核实新 PID **13771**、启动时间 **2026-10-07 17:06:44 CST**、active/running、ExecMainStatus=0、NRestarts=0；两文件哈希与本次修复一致，LLM 仍 disabled/unset。
- 新进程日志摘要 2 条，连接成功信号 1 条，traceback 0、error/failed 信号 0；没有输出原始连接日志。确认新版已启动，但飞书候选选择、真下载和删除口语输入仍须用户现场验证。
- 新 PID/启动时间、连接信号已核实。下一步请用户发送 `帮我下载 留在我身边 青山黛玛` 验收候选。不要额外重启，不替用户执行真实下载或删除。
- 未改 feishu.env、systemd 配置、inbox/SD 音乐或 Git 提交。

## 多源搜索诊断记录（追加修复已部署并于 17:06:44 重启）

- 只读核实派上 DEFAULT_SOURCES 已同时启用网易云、QQ、酷我、酷狗；GUI musicdownload.py 支持更多源勾选，但飞书入口目前没有选源指令。
- **已确定的代码缺陷：** musicdl 2.14.0 的搜索返回 SongInfo dataclass，不继承 dict。部署版 search_candidates 的 isinstance(item, dict) 检查会丢弃这些正常结果。不能把空候选直接归因于平台没收录歌曲。
- 派上真实 SongInfo 类型 + 模拟 search 返回值复现：部署版候选为空；仅在内存改成检查 get 协议后保留结果和原对象。未请求源站、下载、改运行文件或重启。
- 本地 download_core.py 已改为接收 get-capable SongInfo/字典，保持原对象供 musicdl.download 使用（其依赖 .source）；没有把 SongInfo 转成 dict。
- 新增 tests/test_download_core.py，先观察两项失败再修复。全量 **45 passed**，1 个 SDK datetime 弃用警告；编译通过。随后已完成下述真机多源只搜索验证，新版机器人确认流程仍未部署验收。
- 新 download_core 本地 SHA-256：`216d6b54af09f82aeb1ca24488c1dd8a26cf438453256d6746a0fa36cb1a0478`；派上仍为首轮部署的 `3347e961d49f6a2fd7b607784af3b94ed5548de3cd0897da11a2b8e894a192c6`。
- 用户随后提供截图实例：`帮我下载 そばにいるね青山黛玛`、`下载 留在我身边 青山黛玛`，线上均返回没搜到。
- **真机源站搜索已验证（不下载）：** 在派上独立临时目录调用现有四源搜索；`そばにいるね青山黛玛` 耗时 39.1 秒，`留在我身边 青山黛玛` 耗时 33.6 秒。两个关键词下，网易云、QQ、酷我、酷狗均各返回 5 条，且每源结果中均有目标曲。5 是当前每源上限，不代表总收录数或所有条目都精确匹配。
- 实际结果为 SongInfo；网易云目标标题 `そばにいるね`、歌手 `青山テルマ,SoulJa`；QQ 目标标题 `そばにいるね (留在我身边)`、歌手 `青山黛玛, SoulJa`。结合已复现的类型过滤，已能解释该实例为何被 bot 报为空。
- 本次没有调用 download、写入 inbox/SD、改运行代码或重启。搜索成功不能当作音频下载和播放通过。
- 当前每源搜索上限 5，候选按源顺序截取最多 3 条、同歌名/歌手去重；这会限制可见版本，但本轮未擅自改变排序或加入选源界面。
- 后续批准与第二轮部署结果见上节；两个修复已一起上传，用户完成本次重启，新进程已核实。

## 删除输入诊断记录（追加修复已部署并于 17:06:44 重启）

### 第二张截图：固定删除指令真机验证

- 用户在飞书自行发送 `删除本地 轻熟女`，机器人回复“已从本地删除 1 首”，并列出对应的 KugouMusicClient 下 MP3 路径。依据用户截图，固定关键词删除的飞书真机操作已验证；本轮未再 SSH 检查文件系统。
- 同一截图中复制整行（包含 `332.7 KB`）仍匹配失败，与追加修复尚未部署一致。
- 截图不构成部署/重启授权，也不授权助手删除其它文件。此次没有上传、重启或执行删除。
- 等待用户决定是否部署追加修复；自然语言下载候选及取消验收仍待用户反馈。


- 用户截图确认飞书“盘”能列出本地 5 首音频，并提示未检测到 USB 卡。因此“盘”的本地列表飞书链路已实际验证，卡内列表仍未验证。
- 截图中的“删掉本地那首轻熟女”失败：删除关键词包含“那首”；粘贴整行时还包含末尾 `332.7 KB`。两种输入均在临时文件中复现，不代表已获准替用户删除真实音乐。
- 本地 `export_to_player.py` 追加修复：先匹配原始关键词；无匹配才剥离“那首/这首”；识别列表圆点与音频扩展名后的大小字段。复制的列表项按完整相对路径精确匹配，避免同时命中其它目录同名项。空关键词和装饰后的“全部/所有/*”不升级为批量删除。
- `tests/test_local_library.py` 新增 11 个用例。全量 **42 passed**，1 个 SDK datetime 弃用警告；export 编译通过。仅删除临时目录里的测试文件，未碰实际 inbox/SD。
- 新 export 本地 SHA-256：`6c5d1f6167c1ef09229a27f0ecdd40260fd6d664065dbc6829ac352115378512`。派上仍是首轮部署的 `8c283350873801ddccb9943971fbf3546f5e6e7849f497d9a3a8ad4a99f8e5d7`；下表为首轮部署基线，不代表追加修复已同步。
- 这次未上传、重启或删除实际音乐。追加修复待用户明确同意部署并再重启一次。旧版临时可用 `删除本地 轻熟女`；由用户按意图在飞书执行，不由助手代发。
- 自然语言搜索候选/取消/确认仍没有用户端到端证据，不能因本截图记为通过。

## 最新部署结果（2026-10-07）

- 用户已明确同意备份、部署五个核心文件并重启一次，无须再次请求部署许可。
- 原文件备份：树莓派 `/home/shawpi/musicDownload-master/deploy-backups/20261007-000725/`，含三份原代码和 manifest.json；manifest 记录 commands.py、nl_intent.py 原先缺失。候选文件在该目录的 candidate/。
- 本地重新执行测试：31 passed（SDK 弃用警告 1 个）。
- 候选五文件已在派上核对 SHA-256、内存编译并用项目 .venv 成功导入；未启动第二条飞书长连接。
- 五文件已替换进 `/home/shawpi/musicDownload-master/`，再次核对全部哈希与下表本地列一致。因此下表“树莓派”列仅记录**部署前备份版本**，不再是当前磁盘版本。
- `sudo -n systemctl restart music-feishu.service` 返回 `sudo: a password is required`，重启未成功执行。随后确认服务仍 active/running，PID 11418，启动时间仍为 2026-10-06 21:22:57 CST，NRestarts=0。
- 用户已在自己终端执行重启；只读核实新 PID **11977**，启动时间 **2026-10-07 00:13:47 CST**，active/running，ExecMainStatus=0，NRestarts=0。五文件哈希仍与本地一致，运行进程 LLM 仍为 disabled/unset。
- 当前进程最近日志摘要：2 条记录，长连接成功信号 1 条，traceback 0、error/failed 信号 0。仅输出计数，未输出原始连接 URL 或密钥；这不是飞书命令端到端通过的证明。
- 新 PID/启动时间与连接信号已确认；下一步由用户在飞书验证帮助、盘、候选及取消。不要额外重启，也不要修改 systemd 或密钥。
- 未执行下载、导入、删除或飞书发消息；SD 与自然语言端到端验收仍待完成。

## Git 与工作区

- 本地：`/Users/shaolc/musicDownload/musicDownload-master`，分支 `main`，HEAD 为 `d28c4b09f881c35c8a358e74ef967741f178e0a4`。
- 远程：`git@github.com:Blissamys/raspberry-pi-feishu-music.git`。本轮未 fetch、commit 或 push，未重新核实远端 main 或仓库可见性。
- 原有未提交修改：AGENTS、README、commands、download_core、feishu_bot、feishu.env.example、DEPLOYMENT、DEVELOPMENT、STATUS；未跟踪的 ARCHITECTURE、HANDOFF、LOCAL_LLM、nl_intent 和 NL 测试仍保留。
- 本轮额外修改 `export_to_player.py`，修复 bot/NL 边界，增加 `tests/test_bot_flow.py`、`tests/test_storage_safety.py`，扩充 NL 测试。所有改动仍未提交。
- `feishu.env` 未修改、未提交；只定向解析 LLM 开关，未输出密钥。

## 树莓派部署前状态（2026-10-06 SSH 核实；最新进程见上节）

地址 `shawpi@musicpi.local`，项目 `/home/shawpi/musicDownload-master`。沙箱内名称解析失败；沙箱外能连接。用户配置公钥后已可 BatchMode 登录，不再需要 IP。

| 项目 | 本轮证据 |
|------|----------|
| 服务 | `music-feishu.service` 为 active/running，PID 11418 |
| 启动时间 | 2026-10-06 21:22:57 CST；本轮未重启 |
| 工作目录 | `/home/shawpi/musicDownload-master` |
| 文件修改时间 | bot/export 为 19:45:33，download_core 为 17:56:58，均早于服务启动 |
| 依赖 | lark-oapi 1.7.3、musicdl 2.14.0、tinytag 2.3.2 |
| Ollama | `/usr/local/bin/ollama` 存在，`/api/tags` 返回 `{"models":[]}`，没有已安装模型 |
| LLM 开关 | 运行进程及 feishu.env 定向检查均为 disabled/unset，未改配置 |
| 曲库 | 只读列表看到本地 5 首音频；未检测到 USB FAT/exFAT 曲库分区 |

### 首轮部署五文件基线（SHA-256，派上列为部署前备份版本）

本地列为首轮修复/部署版本（不含上述截图后的追加修复）；派上列为 2026-10-06 审计所得旧版本。2026-10-07 部署后磁盘五文件已与本地列相同；服务已于 00:13:47 重启。

| 文件 | 本地 | 树莓派 |
|------|------|--------|
| `feishu_bot.py` | `33717f7f2f7f040657a6cff8dcdb5a700bc005b5b0df95dcea540cebaf13e533` | `7caea982ce215e9abaff48babcdf04af5e96e2f5271aeec10fac1054e679e0ac` |
| `commands.py` | `97c4168a0a405972791811cf0b06c4cf653868f4523604021d0ca50e01d19a51` | `缺失` |
| `nl_intent.py` | `e3150af0db0229c029b9832945cf08cd72d2b0c48766a3539ebca9338e86a31a` | `缺失` |
| `download_core.py` | `3347e961d49f6a2fd7b607784af3b94ed5548de3cd0897da11a2b8e894a192c6` | `80a74104591fb6a7c07c65bb70f33121a4f18189c9b58e6af648c5145fc6ff91` |
| `export_to_player.py` | `8c283350873801ddccb9943971fbf3546f5e6e7849f497d9a3a8ad4a99f8e5d7` | `f2231f4b6323226ed9169b79c78a5df9d2b0fabf7664e03312034853563384cc` |

具体差异：

- 派上 bot 内嵌固定指令解析/白名单，缺少自然语言候选确认；`commands.py`、`nl_intent.py` 均不存在。
- 派上 bot 已有下载完成主动回复详情，不能再记为本地独有。
- 派上 download_core 已有平铺函数，但没有拆开的 `search_candidates` / `download_song_info`。inbox 保留旧子目录，不能据此证明新下载仍不平铺。
- 派上 export 已有 `FSTAB_LABEL = "IRIVER"` 和 pkl 过滤。与接手时本地版本的差异主要是本地删除函数支持传入测试 inbox；与本轮修复后版本另有 mmcblk0 拒绝检查差异。
- 派上三个原文件只读副本存于本机 `/private/tmp/musicpi-audit-20261006/`，是临时比对材料，不能作为长期回滚备份。

## 2026-10-06 本地修复与验证

按失败测试 → 修复 → 全量测试顺序执行：

1. 搜索、下载、导入在同一锁内检查并占用任务状态。搜索不能将另一下载状态覆盖为 idle。
2. 忙碌时确认保留候选；取消搜索后迟到结果不恢复候选；新搜索失败清除旧候选。
3. 存储筛选及挂载入口按设备名/路径拒绝 `mmcblk0` 及其分区（仅虚构设备数据测试，未操作系统盘）。
4. 收紧 NL 写操作为明确指令句，避免“不要删除本地全部”“怎么导入”等被子串匹配误执行；补齐“把歌拷到SD”。这些边界测试以 **LLM 关闭**为前提，不代表模型开启时已安全验收。
5. 保留 `歌曲…` 立即下载、普通自然语言先候选确认、白名单外不派发任务。

| 检查 | 结果与边界 |
|------|------------|
| 项目 `.venv/bin/python -m pytest -q` | **31 passed**；1 个 SDK 内部 datetime 弃用警告 |
| 五个核心模块 py_compile | 通过 |
| 本地 bot 导入 | 补装与派上相同的 lark-oapi 1.7.3 后可导入；没有启动长连接 |
| bot 确认/取消/忙碌/白名单 | 本地测试通过，外部搜索下载与回复均为 mock |
| 导入过滤 | 在临时目录运行真实 rsync，音频/lrc 复制，pkl 和 `.musicdl_temp` 未复制；未访问播放器 |
| 真机“盘”函数 | 只读调用，阻断一切挂载/写入，lsblk 排除 MMC major 179；列出本地 5 首，无 FSTAB_LABEL 错误；无 USB 卡，未验收卡内列表 |
| 飞书新 NL / 真下载 / SD 导入 / 删除 | **本轮未执行，未通过真机验收** |

2026-10-06 审计/修复阶段未上传或重启。2026-10-07 已获准上传五个文件；首次 sudo 被密码阻塞后，用户在终端完成重启并已核实。始终未改 systemd 配置、执行真实下载/导入/删除、发送飞书消息或 commit/push。

## 已有现场验证（历史记录，本轮未重复）

- 树莓派 Lite/SSH、飞书长连接私聊、固定 `歌曲…` 下载曾可用。
- “晴天” FLAC 曾导入 USB 读卡器中的 SD，艾利和可播放；当时设备为 `/dev/sdd1`，不能复用设备名作当前事实。
- 曾因任意私聊当歌名误下载；派上当前代码已有固定前缀限制。
- `删除本地 轻熟女` 已由 2026-10-07 用户截图确认成功（见上节）；平铺真实下载、新 NL 确认、Ollama 推理仍未验收。

## 当前选择与下一步

1. **先用关键词确认，暂缓 Ollama 模型。** Ollama 安装已完成但没有模型；保留 LLM 关闭，不拉模型、不改 Ollama 服务。以后启用需单独验证模型误判、延迟和否定句，尤其不能让模型直接误执行删除/导入。
2. **五文件部署和用户单次重启已完成。** 新进程及连接信号已核实；不得覆盖 feishu.env、服务单元、inbox/SD。
3. 备份、拷贝、哈希、派上编译/导入和重启后状态检查均已完成。进入飞书验收；如失败先查因，不擅自追加重启。
4. 飞书现场验收：`帮助` 显示 NL；`盘`；`帮我下载晴天` 出候选且未自动下载；`取消` 后确认不下载。实际“确认”下载、`歌曲…` 真下载和 SD 导入需现场执行并记录；**删除本地仍不执行，除非用户明确同意删除目标**。
5. 插入播放器卡后再验证 USB 曲库列表/导入；保持 pkl 过滤，不操作 mmcblk0。
6. Git 提交推送仍需用户明确要求。

## 仍需注意

- 重复飞书事件尚无去重；候选无持久化/过期时间。
- `盘` 与删除本地没有纳入上述下载/导入/搜索任务锁，不能把此次修复描述为所有操作都串行。
- 下载/挂载/卸载的真实成功情况尚需验收，不能仅以函数返回或单元测试通过推断播放器安全可拔。
- 现有 feishu.env.example 文件末尾多空行会触发全仓 `git diff --check`；此为接手前已有格式问题，未借机修改配置模板。
