# AI Companion - 智能桌面伴侣

基于 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) v1.2.1 构建的桌面智能伴侣。

## 项目目标

具备深度定制人设、高保真克隆音色、能通过 Function Calling 执行 To-do / 邮件等日常任务的桌面级智能体。

## 顶层目录结构

```
AICompanion/
├── Open-LLM-VTuber/         # OLV 主体（git fork，跟踪 upstream）
│   ├── conf.yaml            # 用户配置（gitignored）
│   ├── mcp_servers.json     # MCP 服务器注册表（gitignored）
│   └── src/open_llm_vtuber/
│       └── agent/
│           ├── agents/companion_agent.py   # ★ 自研 Agent
│           ├── persona/character_card_v2.py # ★ V2 角色卡解析器
│           └── memory/chroma_store.py       # ★ ChromaDB 记忆适配器
├── mcp_servers/             # 独立 MCP 服务器子项目
│   ├── todo_server/         # To-do List MCP（SQLite 后端）
│   └── mail_server/         # 邮件 MCP（IMAP）+ 主动通知守护
├── characters_v2/           # 角色卡 V2 JSON 文件存放目录
├── data/                    # 运行时数据（SQLite, ChromaDB 持久化）
├── frontend_overlay/        # 前端 React 业务面板（覆盖到 OLV-Web 源码）
├── scripts/                 # 启动 / 同步上游 / 训练辅助脚本
└── docs/                    # 项目文档
```

## 环境要求

- **Python**: 3.10 ~ 3.12（OLV 限制；用户当前 3.13 需要 uv 切换）
- **Node.js**: 18+（用于 Electron + 前端构建）
- **uv**: 现代 Python 包管理器（OLV 推荐）
- **GPT-SoVITS-V2**: 独立部署，对外提供 v2 API
- **Ollama / OpenAI-Compatible LLM**: 默认走 Ollama，也可接入 OpenAI / Claude / DeepSeek 等

## 快速启动

### 1. 安装 uv（如未安装）

PowerShell:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装依赖

```powershell
cd Open-LLM-VTuber
uv sync                     # 同步 OLV 依赖
uv pip install chromadb     # 安装我们扩展所需的 ChromaDB
```

### 3. 准备配置文件（首次 clone 必做）

`conf.yaml` 和 `mcp_servers.json` 含有 API key 等敏感信息，已被 gitignore。
仓库提供 `.example` 模板，复制后再填入凭据：

```powershell
cd Open-LLM-VTuber
copy conf.example.yaml conf.yaml
copy mcp_servers.example.json mcp_servers.json

cd ..\mcp_servers\mail_server
copy mail_config.example.json mail_config.json   # 启用邮件功能时
```

### 4. 配置 conf.yaml

编辑 `Open-LLM-VTuber/conf.yaml`：
- 选择 LLM provider 并填入 API key
- 切换 `conversation_agent_choice: 'companion_agent'`
- 配置 `companion_agent.character_card_path` 指向 `characters_v2/your_character.json`
- 配置 GPT-SoVITS 的 `api_url`、`ref_audio_path`、`prompt_text`、`prompt_lang`

### 5. 启动外部服务

```powershell
# 终端 1：GPT-SoVITS-V2 API 服务（需先按 SoVITS 文档训练好模型）
cd <你的GPT-SoVITS路径>
python api_v2.py

# 终端 2：邮件守护（可选；启用主动播报需要）
cd mcp_servers/mail_server
python daemon.py

# 终端 3：OLV 主服务
cd Open-LLM-VTuber
uv run run_server.py
```

打开浏览器访问 `http://localhost:12393`，或运行 Electron 客户端获得桌宠模式。

## 自研模块说明

详见各子模块 README：
- [Open-LLM-VTuber/src/open_llm_vtuber/agent/agents/companion_agent.py](Open-LLM-VTuber/src/open_llm_vtuber/agent/agents/companion_agent.py)
- [mcp_servers/todo_server/README.md](mcp_servers/todo_server/README.md)
- [mcp_servers/mail_server/README.md](mcp_servers/mail_server/README.md)
- [frontend_overlay/README.md](frontend_overlay/README.md)
- [characters_v2/README.md](characters_v2/README.md)

## 与上游 OLV 同步

```powershell
cd Open-LLM-VTuber
git fetch upstream
git merge upstream/main
```

所有自研代码尽量限制在新增文件，仅 `agent_factory.py` / `config_manager/agent.py` / `mcp_servers.json` / `conf.yaml` 有微量修改。
