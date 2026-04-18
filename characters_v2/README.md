# 角色卡 V2 (Character Card V2)

本目录存放符合 [SillyTavern Character Card V2 规范](https://github.com/malfoyslastname/character-card-spec-v2) 的 JSON 文件。

## 加载方式

`Open-LLM-VTuber/conf.yaml` 中：

```yaml
character_config:
  agent_config:
    agent_settings:
      companion_agent:
        character_card_path: '../characters_v2/default.json'
```

切换角色只需把路径指向本目录下其他 `*.json`，无需重启 OLV 后端（重新连接 WebSocket 即可）。

## V2 规范字段

| 字段 | 说明 |
| --- | --- |
| `name` | 角色名（会替换 `{{char}}` 占位符） |
| `description` | 外貌、背景、人设描述 |
| `personality` | 性格特征 |
| `scenario` | 当前场景设定 |
| `first_mes` | 角色的开场白 |
| `mes_example` | 多轮示例对话（用 `<START>` 分隔多组） |
| `system_prompt` | 自定义 system 头（覆盖默认） |
| `post_history_instructions` | 追加在历史后的指令 |
| `alternate_greetings` | 可选的替代开场白列表 |

占位符 `{{user}}` 会自动替换为 `character_config.human_name`，`{{char}}` 替换为 `name`。

## 从 SillyTavern 导入

直接把 SillyTavern 导出的 `.json` 卡片拷贝到本目录即可。`.png` 嵌入式卡片需要先用工具解码出 JSON。
