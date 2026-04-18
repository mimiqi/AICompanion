# Frontend Overlay

OLV 的前端是独立的 React + Electron 工程（仓库：[Open-LLM-VTuber-Web](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web)）。本目录管理我们对它的二次开发。

## 目录结构

```
frontend_overlay/
├── upstream/              # 从 Open-LLM-VTuber-Web 的 main 分支克隆，不要直接修改
└── companion/             # 我们的覆盖文件
    ├── hooks/
    │   └── use-companion-api.ts
    └── components/
        ├── todo-panel.tsx
        └── mail-panel.tsx
```

## 集成步骤

### 1. 拷贝覆盖文件到 upstream

```powershell
cd d:\Coding\Python\AICompanion\frontend_overlay
cp companion/hooks/use-companion-api.ts upstream/src/renderer/src/hooks/
cp companion/components/todo-panel.tsx upstream/src/renderer/src/components/sidebar/
cp companion/components/mail-panel.tsx upstream/src/renderer/src/components/sidebar/
```

### 2. 接入 Sidebar 头部按钮

编辑 `upstream/src/renderer/src/components/sidebar/sidebar.tsx`：

```tsx
import { FiCheckSquare, FiMail } from 'react-icons/fi';
import TodoPanel from './todo-panel';
import MailPanel from './mail-panel';
```

在 `HeaderButtons` 组件里追加两个按钮，配合 useState 控制当前显示的 panel；或者把它们渲染到 `BottomTab` 旁边。最小改动示例：把这两个 panel 直接 mount 到 `SidebarContent` 的 ChatHistoryPanel 之后。

### 3. 在桌宠模式右键菜单中加入开关

编辑 `upstream/src/main/menu-manager.ts`，找到 `tray` 或 `pet contextMenu` 的构造，追加：

```ts
{ label: 'Show Todo', click: () => mainWindow.webContents.send('toggle-todo') },
{ label: 'Show Mail', click: () => mainWindow.webContents.send('toggle-mail') },
```

并在 `App.tsx` 监听 `ipcRenderer.on('toggle-todo' / 'toggle-mail', ...)` 切换显示。

### 4. 构建并部署

```powershell
cd upstream
npm install
npm run build:web                     # 构建 web 版（用于 OLV 直接 serve）
# 把构建产物覆盖到 OLV frontend 目录
cp -r out/renderer/* ../../Open-LLM-VTuber/frontend/

# 或构建 Electron 桌面应用
npm run build:win
```

构建完成后，OLV 服务器从 `Open-LLM-VTuber/frontend/` 提供静态文件，访问 `http://localhost:12393` 即可看到新面板。

## REST 端点（已在后端就绪）

UI 通过这些端点直接读写本地数据，不经过 LLM：

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/api/companion/health` | 检查 todo/mail 后端是否就绪 |
| GET | `/api/companion/todos?status=pending` | 列出待办 |
| POST | `/api/companion/todos` | 新增 |
| PATCH | `/api/companion/todos/{id}` | 更新 |
| DELETE | `/api/companion/todos/{id}` | 删除 |
| GET | `/api/companion/mail/recent?unread_only=true` | 列出最近邮件 |
| GET | `/api/companion/mail/{uid}` | 获取邮件正文 |

后端实现：[Open-LLM-VTuber/src/open_llm_vtuber/companion_panels.py](../Open-LLM-VTuber/src/open_llm_vtuber/companion_panels.py)

## 同步上游

OLV-Web 持续更新，同步：

```powershell
cd frontend_overlay/upstream
git pull origin main
```

如发生冲突，重新做"拷贝覆盖文件 + 编辑 sidebar.tsx"两步即可。
