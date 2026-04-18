# 邮件 MCP Server + 后台守护

包含两个独立的进程：

## 1. MCP Server（`server.py`）

向 LLM 暴露邮件查询工具。被 OLV MCP 注册表自动启动。

### 暴露的工具

| 工具 | 说明 |
| --- | --- |
| `fetch_recent_emails(unread_only=True, limit=10, include_body=False)` | 拉取最近邮件元信息 |
| `get_email_detail(uid)` | 获取某封邮件完整正文 |
| `get_unread_count()` | 当前未读邮件数 |
| `get_mail_account_info()` | 报告当前接入的邮箱 / 主机（不含密码） |

## 2. Daemon（`daemon.py`）

独立进程。轮询 IMAP，发现新邮件时通过 WebSocket 给 OLV 发 `ai-speak-signal`，触发桌宠主动开口播报"你有新邮件"。

### 启动顺序

```
1) 先启动 OLV: cd Open-LLM-VTuber && uv run run_server.py
2) 再启动 Daemon: cd ../ && python -m mcp_servers.mail_server.daemon
```

Daemon 失败会按指数退避重试，不会致命退出。

## 配置

复制示例并填入凭据：

```powershell
cd mcp_servers/mail_server
copy mail_config.example.json mail_config.json
notepad mail_config.json
```

| 字段 | 说明 |
| --- | --- |
| `imap_host` / `imap_port` / `use_ssl` | IMAP 服务器 |
| `username` / `password` | 登录凭据。**Gmail/Outlook 用 App Password，不用账号密码** |
| `mailbox` | 监听的邮箱文件夹，默认 `INBOX` |
| `poll_interval_seconds` | 轮询间隔；过短会被服务器限速 |
| `olv_websocket_url` | OLV 的 client-ws 端点；本地默认 `ws://127.0.0.1:12393/client-ws` |
| `state_path` | 已处理 UID 的持久化文件，避免重启后重复触发 |
| `proactive_enabled` | 关闭则只提供 MCP 工具，不主动播报 |
| `senders_whitelist` | 仅当发件人含这些子串才触发主动播报；空数组表示不过滤 |

## 安全

- `mail_config.json` 已被 gitignore（见根 `.gitignore`），不会被提交
- 强烈建议使用应用专用密码，不要使用主账户密码
- 如果不需要主动播报，把 `proactive_enabled` 设为 `false` 即可

## 单独调试 MCP Server

```powershell
cd d:\Coding\Python\AICompanion
python -m mcp_servers.mail_server.server
# 或
uvx mcp dev mcp_servers/mail_server/server.py
```
