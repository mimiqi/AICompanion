# M6 调试与打磨 Checklist

OLV 桌宠模式的核心特性 (透明窗口 / 拖拽 / 点击穿透 / 系统托盘 / 右键菜单) **已由上游内置**，本阶段只需做配置调优 + 待机降帧补丁 + 启动顺序编排。

## 1. 启动顺序

使用编排脚本：

```powershell
# 完整启动 (含 SoVITS)
.\scripts\start-all.ps1 -SovitsPath "D:\path\to\GPT-SoVITS-v2"

# 不需要邮件守护时
.\scripts\start-all.ps1 -SkipMailDaemon

# 全部停止
.\scripts\stop-all.ps1
```

依赖关系：

```
GPT-SoVITS API (:9880)  -->  OLV Server (:12393)  -->  Electron Client
                                 ^
                                 | (WebSocket trigger)
                          Mail Daemon (background)
```

OLV MCP 子进程 (`time` / `todo` / `mail`) 由 OLV 主进程 fork 启动，无需手动管理。

## 2. 桌宠透明窗口验收

启动 Electron 客户端后：

- [ ] 默认窗口模式下 sidebar 可见、Live2D 模型居中
- [ ] 右键菜单可切换到 **Pet Mode**
- [ ] Pet Mode 下窗口背景透明、可拖拽、可设置点击穿透
- [ ] 系统托盘图标可双击呼出窗口
- [ ] 模式切换不丢失对话历史 / WebSocket 连接

> Windows 下若透明窗口背景显示为黑色，通常是显卡驱动 / DWM 兼容问题。在 Electron 启动时加 `--disable-gpu` 排查；正式方案是更新显卡驱动或在主进程窗口配置中尝试 `transparent: true, backgroundColor: '#00000000'`。

## 3. 待机模式降帧（前端补丁）

OLV 默认始终满帧渲染 Live2D。空闲时降帧能显著降低 GPU 负载。补丁思路：

在 `frontend_overlay/upstream/src/renderer/src/components/canvas/live2d.tsx` 的 PIXI ticker 初始化处，根据 AiState 调整：

```ts
import { useAiState } from '@/context/ai-state-context';

const { aiState } = useAiState();

useEffect(() => {
  if (!app) return;
  const target = aiState === 'idle' ? 15 : 60;
  app.ticker.maxFPS = target;
}, [aiState, app]);
```

待机判定：连续 `aiState === 'idle'` 持续 30 秒后降到 15 fps；任何 `'thinking' | 'speaking' | 'listening'` 状态恢复到 60 fps。

## 4. GPT-SoVITS 调优

| 参数 | 建议 | 说明 |
| --- | --- | --- |
| `streaming_mode` | `'true'` | 启用流式音频输出，能进一步降低首句延迟 |
| `text_split_method` | `'cut5'` | 中文场景默认；英文可改 `'cut0'` |
| `batch_size` | `'1'` | 桌宠场景单句即可 |
| `ref_audio_path` | 3-5 秒高质量参考音频 | 太长反而拖慢推理 |

## 5. 性能基线

在 RTX 3060 + Ryzen 5600X 实测的目标：

| 阶段 | 目标延迟 |
| --- | --- |
| ASR (Whisper turbo) | < 800 ms |
| LLM 首 token (Ollama qwen2.5) | < 600 ms |
| GPT-SoVITS 首句音频 | < 1.5 s |
| 端到端首响应 | < 3 s |

无 GPU 时把 ASR 切到 `sherpa_onnx_asr (sense_voice)`、LLM 改用云端 API、TTS 暂时退回 `edge_tts` 即可继续使用。

## 6. 验收用例

- [ ] 用语音说"今天提醒我下午三点写周报"，AI 调用 `add_todo` 工具并语音确认
- [ ] 打开侧边栏 Todo 面板，看到刚才创建的待办
- [ ] 在面板中勾选完成，AI 下一轮对话能感知到"已完成"
- [ ] 给监听邮箱发一封新邮件，30-90 秒后 AI 主动语音播报
- [ ] 切换到 Pet Mode，重新触发以上流程，状态保持
- [ ] 重启 OLV，长期记忆 (ChromaDB) 能召回上一次对话内容
