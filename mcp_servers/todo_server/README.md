# To-do MCP Server

本地 SQLite 后端的 To-do List MCP 服务器，向 LLM 暴露增删改查工具。

## 暴露的工具

| 工具 | 说明 |
| --- | --- |
| `add_todo(title, notes?, due_at?)` | 新增一项；`due_at` 接受 ISO 8601 时间戳或 unix epoch |
| `list_todos(status='pending', limit=20)` | 列出待办；status 可为 `pending` / `completed` / `all` |
| `complete_todo(todo_id)` | 把一项标记为已完成 |
| `update_todo(todo_id, ...)` | 部分字段更新 |
| `delete_todo(todo_id)` | 永久删除 |
| `stats()` | 汇总统计 + 列出当前已逾期项（用于桌宠主动催办） |

## 数据存储

默认写入 `data/todos.db`（项目根下）。可通过环境变量 `TODO_DB_PATH` 覆盖：

```jsonc
// mcp_servers.json
"todo": {
  "command": "python",
  "args": ["-m", "mcp_servers.todo_server.server"],
  "cwd": "..",
  "env": { "TODO_DB_PATH": "../data/todos.db" }
}
```

注意 `cwd` 是 `..`，因为 OLV 启动 MCP 子进程时 cwd 默认是 `Open-LLM-VTuber/` 目录。设为 `..` 让 Python 能找到 `mcp_servers` 包。

## 单独调试

```powershell
cd d:\Coding\Python\AICompanion
python -m mcp_servers.todo_server.server
```

进程会通过 stdio 等待 MCP 协议消息。要交互测试，建议用 `mcp dev` CLI 工具：

```powershell
uvx mcp dev mcp_servers/todo_server/server.py
```
