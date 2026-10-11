# 可选：树莓派上的超小本地模型

4GB 物理内存无法加到 6GB。若启用 LLM，只用约 0.5B 级模型。更大模型列为计划外。

**状态与是否启用以 [STATUS.md](STATUS.md) 为准。** 本轮优先关键词确认流程，暂缓安装模型。以下安装/启用步骤是以后选择启用时的参考，执行前仍需用户同意；模型误判和否定句尚未验收。

软件行为（当前仓库代码，可能尚未部署到派上）：

- 固定指令仍走 `commands.py`（`歌曲` 立即下载）。
- 其它句子：`nl_intent.heuristic_intent`，若 `LLM_ENABLED=1` 再请求 `LLM_BASE_URL` 的 `/chat/completions`。
- 自然语言下载：`search_candidates` 后写入 `_pending`，用户确认才 `download_song_info`。
- 下完仍由 `feishu_bot` 主动回复 tinytag 详情。

## 安装步骤（环境：树莓派 SSH；未验证）

建议使用 `tmux`，避免开发机休眠断开安装。

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b
curl -s http://127.0.0.1:11434/api/tags
```

交换空间会磨损系统 SD，优先使用系统已有 zram。若仍 OOM 再考虑 U 盘 swap，不要把曲库卡当 swap。

在未入库的 `feishu.env` 中设置（不要把真实 Secret 写进文档）：

```
LLM_ENABLED=1
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:0.5b
```

然后重启 `music-feishu.service`（需用户同意）。`LLM_ENABLED=0` 时关键词 `帮我下载…` 仍可走确认流（代码已有，飞书未验证）。

同一飞书应用不要在两台机器同时长连接。不要同时跑 7B。
