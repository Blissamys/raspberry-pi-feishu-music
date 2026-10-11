# 给下一个 AI 的交接

## 项目是什么

树莓派上的飞书私聊机器人：用 `musicdl` 将音乐下载到 UUID 绑定的专用 U 盘，通过预览、按歌名＋歌手去重、确认复制和安全卸载，将新增歌曲导入艾利和 SD。入口 `feishu_bot.py`，飞书 **WebSocket 长连接**，不是 HTTP 回调。

## 当前目标

当前功能版本已归档，进入稳定维护阶段。后续只有在用户提出明确需求时再升级；不要主动扩展范围。必须保留 `歌曲…` 立即下载、自然语言候选确认、多源分页、双盘 UUID 绑定、导入预览及不覆盖 SD 既有歌曲的行为。

详细进度、Git 差异、派上是否同步：**只看** [STATUS.md](STATUS.md)。

## 先读这些文档

1. [../AGENTS.md](../AGENTS.md) — 约束
2. [STATUS.md](STATUS.md) — 状态（主源）
3. 按需：[ARCHITECTURE.md](ARCHITECTURE.md)、[DEPLOYMENT.md](DEPLOYMENT.md)、[DEVELOPMENT.md](DEVELOPMENT.md)、[LOCAL_LLM.md](LOCAL_LLM.md)
4. 总览：[../README.md](../README.md)

## 需要访问的代码与环境

- 代码：仓库内 `feishu_bot.py`、`commands.py`、`nl_intent.py`、`search_ui.py`、`download_core.py`、`storage_roles.py`、`library_sync.py`、`export_to_player.py`、`system_status.py`、`tests/`
- 配置模板：`feishu.env.example`、`storage.example.json`、`music-feishu.service`
- 运行环境（只读核对，未经允许不要重启）：树莓派 `shawpi@musicpi`，`~/musicDownload-master`，`feishu.env`，systemd `music-feishu.service`
- 线上真实配置：`feishu.env`、`storage.json`，均不得提交或在回复中打印

## 最重要的待办与约束

- 先确认用户提出了新的升级需求，再核对 `main`、工作区、GitHub 和树莓派运行文件；不要把归档状态当作无需核查。
- 部署必须包含新增模块；遗漏 `nl_intent.py`、`search_ui.py`、`storage_roles.py`、`library_sync.py` 或 `system_status.py` 会导致启动或功能失败。
- 不要提交密钥；不要 force push；不要擅自删 inbox/SD 音乐；不要操作系统盘。
- 当前 Ollama 无模型，`LLM_ENABLED` 默认关闭；关键词路径不依赖 Ollama。
- 文档不能替代读代码；未验证项继续核实。

## 可复制到新对话的接手提示词

```
请接手「树莓派飞书遥控下载音乐」项目。先阅读 AGENTS.md、docs/HANDOFF.md、docs/STATUS.md，再核对仓库里的实际代码（尤其 feishu_bot.py、commands.py、nl_intent.py、download_core.py、export_to_player.py），不要假设文档完全正确。

约束：不要提交 feishu.env 或打印密钥；不要 git push --force；未经我明确同意不要重启或修改树莓派 systemd、不要删除 inbox/SD 上的音乐；识别存储时不要碰 mmcblk0。保留「歌曲…」立即下载；闲聊不得默认当歌名；导入不要把 pkl 拷到播放器。

项目当前已归档。只有在我提出明确升级需求时才继续开发。开始前根据 docs/STATUS.md 核对 GitHub、本地代码和树莓派运行文件；未在真机验证的不要写成已通过。保留双盘 UUID 安全校验、预览后确认、去重不覆盖和安全卸载规则。
```
