# AI 对话剪辑功能总结

## 一、整体架构

采用 **"笨引擎 + 聪明模型"** 架构，运行时不包含业务逻辑，所有智能决策由 LLM 完成。核心是 **ReAct Agent** 的 TAOR 循环（Think → Act → Observe → Repeat），用户通过自然语言对话即可完成复杂视频剪辑任务。

```
用户输入 → LLM 思考 → 调用工具 → 观察结果 → 继续思考 → 最终回复
```

## 二、Agent 处理模式

### 1. 标准模式（同步）
- 完整请求/响应，最多 5 轮 TAOR 循环防止无限循环
- 适合简单指令

### 2. 流式模式（SSE）
- Server-Sent Events 实时推送，事件类型：
  - `session` — 会话 ID 分配
  - `thinking` — AI 思考过程（第 1-5 轮）
  - `tool_start` — 工具开始执行（含权限级别）
  - `tool_result` — 工具执行结果预览
  - `reply` — 增量文本生成
  - `done` — 处理完成
  - `error` — 错误发生

### 3. 深度研究模式（多阶段）
- 分三个阶段处理复杂任务：
  1. **分析素材** — AI 分析所有可用视频素材
  2. **规划方案** — 生成完整剪辑方案
  3. **执行操作** — 按方案逐步执行
- 每阶段独立运行 TAOR 循环，阶段间传递上下文

### 4. 快/慢模型路由
- `select_model()` 根据消息长度、工具调用检测、迭代轮次自动选择模型
- 第 0 轮 + 短文本 + 无工具调用 → 快速模型
- 后续轮次或复杂任务 → 主模型

## 三、工具体系（73 个工具）

### 3.1 基础视频操作
| 工具 | 说明 |
|------|------|
| `cut_video` | 按时间范围剪切视频片段，结果自动入库为新素材 |
| `merge_videos` | 合并多个视频（支持转场效果） |
| `split_video` | 按时间间隔分割视频 |
| `add_subtitle` | 添加硬字幕/软字幕 |
| `change_speed` | 调整播放速度（0.5x - 10x） |
| `compress_video` | H.265 压缩 |
| `convert_to_gif` | 视频转 GIF |
| `convert_format` | 格式转换 |
| `reverse_video` | 视频倒放 |
| `scene_detect` | 场景变化检测 |
| `slow_motion` | 慢动作（带插帧） |

### 3.2 音频处理
| 工具 | 说明 |
|------|------|
| `add_audio` | 添加配音/背景音乐 |
| `extract_audio` | 提取音频轨道 |
| `mix_audio_to_video` | 混合配音与 BGM |
| `separate_vocal` | 人声分离 |
| `normalize_audio` | 响度标准化 |
| `equalize_audio` | EQ 均衡器调节 |
| `fade_audio` | 音频淡入/淡出 |
| `add_echo` | 回声/混响效果 |
| `denoise_audio` | 降噪 |
| `pitch_shift` | 变调（-12 到 +12 半音） |
| `reverse_audio` | 音频反转 |

### 3.3 AI 能力
| 工具 | 说明 |
|------|------|
| `smart_clip` | AI 智能剪辑 |
| `analyze_video` | 视频基础分析（元数据） |
| `analyze_video_vl` | AI 深度内容理解（Qwen-VL 视觉语言模型） |
| `transcribe_video` | 语音识别 & 字幕提取 |
| `generate_tts` | 文字转语音 |
| `generate_music` | AI 音乐生成 |
| `translate_text` | 文本翻译 |
| `detect_language` | 语言检测 |
| `optimize_prompt` | AI 提示词优化 |

### 3.4 素材管理
| 工具 | 说明 |
|------|------|
| `list_videos` | 列出项目视频素材（支持按项目筛选） |
| `list_audios` | 列出音频素材 |
| `get_video_description` | 查询视频描述（无描述时提示 AI 分析） |
| `get_video_detail` | 视频详细技术信息 |
| `search_material` | 搜索/下载素材（Pexels/Pixabay） |
| `search_files` | 本地文件搜索 |
| `download_video` | 从 URL 下载视频 |
| `random_video` | 随机选择素材 |
| `set_cover` | 设置视频封面 |
| `update_description` | 更新视频描述 |
| `delete_material` | 删除素材 |

### 3.5 FFmpeg 滤镜效果
| 工具 | 说明 |
|------|------|
| `adjust_brightness` | 亮度/对比度/饱和度 |
| `blur_video` | 高斯模糊 |
| `sharpen_video` | 锐化 |
| `rotate_video` | 旋转（90°/180°/270°） |
| `flip_video` | 水平/垂直翻转 |
| `crop_video` | 裁剪区域 |
| `fade_video` | 视频淡入/淡出 |
| `picture_in_picture` | 画中画叠加 |
| `add_watermark` | 图片水印 |
| `add_text_overlay` | 文字叠加 |
| `stabilize_video` | 视频稳定 |
| `color_adjust` | 高级调色 |

### 3.6 系统工具
| 工具 | 说明 |
|------|------|
| `get_current_time` | 当前日期时间 |
| `list_directory` | 目录列表 |
| `get_system_info` | GPU/磁盘/系统信息 |
| `open_folder` | 打开文件夹 |
| `task_status` | 后台任务状态查询 |
| `time_convert` | 时间格式转换 |
| `srt_to_ass` | 字幕格式转换 |
| `suggest_music` | 音乐推荐 |
| `batch_compress` | 批量压缩 |
| `extract_frames` | 提取关键帧 |
| `help` | 帮助信息 |

### 3.7 多 Agent 协作工具
| 工具 | 说明 |
|------|------|
| `plan_clip` | 触发 Planner Agent 规划剪辑方案 |
| `review_result` | 触发 Reviewer Agent 审查结果 |

### 3.8 知识库工具
| 工具 | 说明 |
|------|------|
| `knowledge_search` | BM25 知识库检索（项目级 RAG） |
| `knowledge_add` | 添加文档到知识库 |

### 3.9 浏览器自动化工具（CDP）
| 工具 | 说明 |
|------|------|
| `browser_navigate` | 导航到 URL |
| `browser_screenshot` | 网页截图 |
| `browser_get_content` | 提取页面内容 |
| `browser_get_links` | 提取所有链接 |
| `browser_execute_js` | 执行 JavaScript |

## 四、工具权限与安全

| 权限级别 | 行为 |
|----------|------|
| `read_only` | 自动执行，无需确认 |
| `modify` | 需要用户确认后执行 |
| `destructive` | 必须用户确认才能执行 |

- 所有参数通过 **Pydantic 模型校验**，失败抛异常不静默返回
- LLM 修正后的参数会重新校验
- FFmpeg 字符串参数经 `sanitize_ffmpeg_string()` 清洗防注入

## 五、多 Agent 协作

### 流水线架构
```
Planner（规划） → Executor（执行） → Reviewer（审查）
```

### Planner Agent
- 视频剪辑方案规划专家
- 输出：方案概览（目标、风格、时长）+ 分镜列表 + 音频方案
- 不调用工具，仅规划

### Executor Agent
- 视频剪辑执行专家
- 拥有完整工具访问权限
- 按分镜逐步执行，失败时尝试替代方案
- 每个工具链最多 3 次迭代

### Reviewer Agent
- 视频质量审查专家
- 审查维度：技术质量、内容连贯性、音画同步、整体美感
- 不调用工具，仅审查

## 六、技能系统

通过 Markdown 文件定义复合技能，Agent 自动加载并注入到系统提示词中。

### 已内置技能

#### auto_highlight — 自动高光集锦
- 自动分析视频 → 提取精彩片段 → 合并为高光集锦
- 流程：列出素材 → AI 分析识别亮点 → 剪切 5-15s 片段 → 合并 → 保持 30-60s 总时长

#### smart_short_video — 智能短视频
- 从素材生成 30 秒短视频
- 流程：列出素材 → AI 分析内容 → 规划 30s 剪辑 → 剪切合并 → 添加字幕和 BGM

## 七、扩展/插件系统

- 扩展放在 `src/extensions/` 目录，包含 `manifest.json` + Python 模块
- 支持动态工具注册和系统提示词注入
- 应用启动时自动加载，API 支持热重载

### 已内置扩展

#### subtitle_style — 字幕风格预设
- 提供综艺、新闻、电影、社交、默认 5 种字幕风格预设

## 八、MCP 外部工具集成

通过 MCP（Model Context Protocol）协议动态接入外部工具服务器：
- HTTP/JSON 工具发现和调用
- 工具命名格式：`server_name.tool_name`
- 通过 `/api/mcp` API 动态注册/移除服务器
- MCP 工具自动注入到 Agent 系统提示词

## 九、会话管理

### 会话状态
| 状态 | 说明 |
|------|------|
| IDLE | 等待输入 |
| COLLECTING | 收集信息 |
| CONFIRMING | 等待确认 |
| EXECUTING | 执行操作 |
| COMPLETED | 任务完成 |
| ERROR | 错误状态 |

### DialogState 关键字段
- `project_id` — 关联项目
- `last_video_list` — 缓存视频列表（支持"第一个"等序数解析）
- `last_referenced_video_id` — 上次引用的视频
- `history` — 最近 20 条消息历史
- `slots` — 已收集的参数槽位

### 持久化
- 内存缓存活跃会话（1 小时 TTL）
- SQLite 数据库持久化
- 内存 + DB 双写

## 十、项目偏好记忆

### 自动偏好提取
从对话中自动识别用户偏好：
- 风格关键词：动感、温馨、简约、复古、科技等
- 字幕颜色：白色、黄色
- BGM 音量：小声/轻、大声/重
- 通用偏好："我喜欢/我偏好/以后都..."

### 存储
- 文件持久化：`src/db/memories/project_{id}.json`
- 自动注入到后续对话的系统提示词中
- 保留最近 50 条备注

## 十一、知识库（RAG）

- 基于 **BM25 算法**的轻量 RAG 实现
- 支持中文分词
- 项目级隔离存储
- 文档结构：内容 + 来源 + 标签

## 十二、API 接口

### REST API
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agent/chat` | POST | 标准对话 |
| `/api/agent/chat/stream` | POST | SSE 流式对话 |
| `/api/agent/deep-research` | POST | 深度研究模式 |
| `/api/agent/execute` | POST | 直接执行工具 |
| `/api/agent/analyze/{video_id}` | POST | 视频分析 |
| `/api/agent/tools` | GET | 列出所有工具 |
| `/api/agent/sessions` | GET | 列出活跃会话 |
| `/api/agent/session/{id}` | DELETE | 删除会话 |
| `/api/mcp/servers` | GET/POST | MCP 服务器管理 |
| `/api/mcp/call` | POST | 调用 MCP 工具 |

### WebSocket 通道
| 通道 | 用途 |
|------|------|
| `/ws` | Agent 对话（双向流式） |
| `/ws/render` | 渲染进度推送 |
| `/ws/system` | 系统通知 |

## 十三、前端交互

### ChatSidebar 聊天侧边栏
- 消息历史展示（含时间戳）
- 流式消息实时显示
- 工具调用可视化（运行中/成功/失败状态）
- 危险操作确认面板
- 消息操作：复制、重试、删除
- 消息搜索/过滤
- 快捷上下文操作
- 右键菜单

### 快捷操作（根据项目状态动态展示）
- 无素材时 → 下载素材
- 有素材时 → 分析素材 / 生成方案 / 渲染视频 / 智能剪辑

### 自动刷新逻辑
- 素材工具 → 刷新素材库
- 音频工具 → 切换到音频标签
- 分析工具 → 切换到预览
- 智能剪辑 → 切换到方案标签

## 十四、系统提示词注入链

Agent 每次对话时按顺序拼接以下上下文：
1. 基础系统提示词（角色 + 工具描述 + 规则）
2. 项目偏好记忆
3. 技能描述
4. 扩展提示词
5. MCP 外部工具描述

## 十五、关键设计约定

- **工具链式调用**：`cut_video` 结果自动注册为新素材，支持剪切 → 分析等链式操作
- **序数解析**：`last_video_list` 缓存支持"第一个"、"第二个"等自然语言引用
- **project_id 自动注入**：工具执行时自动补充当前项目 ID
- **LLM 参数修正**：工具参数校验失败时，LLM 可自动修正并重新校验
- **最大 5 轮循环**：防止单次对话无限循环
- **END_CALL 拼接**：避免 XML 闭合标签被误解析

---

## 十六、代码验证结果（2026-04-23）

以下是对本文档所有声明功能的代码级验证结果。

### 16.1 工具数量

| 声明 | 实际 | 状态 |
|------|------|------|
| 94+ 工具 | **73 个** `@registry.register` | ~~已修正为 73 个~~ |

所有 73 个工具的函数体均有完整实现，无空壳/stub。

### 16.2 各模块验证详情

#### ReAct Agent（react_agent.py）✅ 正确
- `process_message()` — TAOR 循环逻辑完整，最多 5 轮
- `process_message_stream()` — SSE 事件正确 yield（session/thinking/tool_start/tool_result/reply/done/error）
- `process_deep_research()` — 三阶段（分析素材→规划方案→执行操作），每阶段独立 TAOR
- `_build_messages()` — 5 层注入链（系统提示词→项目偏好→技能→扩展→MCP）均实现
- `_parse_tool_calls()` — 正则解析 `<tool_call name="...">...</tool_call}>`
- `_execute_tool()` — 正确执行 before_execute hook → validate → execute → after_execute hook
- `select_model()` — 在 llm_adapter 中实现，快/慢模型路由
- END_CALL 拼接避免 XML 误解析 ✅

#### 会话管理（session_manager.py）✅ 正确
- 6 种状态（IDLE/COLLECTING/CONFIRMING/EXECUTING/COMPLETED/ERROR）完整定义
- DialogState 包含所有声明字段（project_id, last_video_list, last_referenced_video_id, history, slots 等）
- 内存 + DB 双写持久化实现完整
- 过期会话清理逻辑正常

#### 多 Agent 协作（multi_agent.py）⚠️ 有问题
- Planner → Executor → Reviewer 流水线结构正确
- **问题 1**：Executor Agent 的 TAOR 循环中，`for` 循环内每个工具调用后有 `break`（第 117 行），意味着每轮只执行一个工具，无法一次调用多个工具
- **问题 2**：超时回退 `'response' in dir()` 不太可靠，应使用局部变量检查
- **问题 3**：Executor 没有使用 `select_model()`，固定调用 `generate_response_async` 无 model_name 参数
- **问题 4**：Planner 和 Reviewer 不调用工具，但 Executor 的工具调用使用独立的正则解析而非复用 `react_agent._parse_tool_calls()`，存在重复代码
- **问题 5**：Executor 工具执行时跳过了 Pydantic 参数校验和 before/after hook

#### 技能系统（skill_loader.py + skills/）✅ 正确
- Markdown 解析逻辑完整（标题→名称、描述→第一段、所需工具→正则匹配、## 后→prompt）
- `get_skills_prompt_section()` 正确生成注入段落
- 两个技能文件 `auto_highlight.md`、`smart_short_video.md` 均存在且格式正确

#### 扩展系统（extension_loader.py）✅ 正确
- manifest.json 加载、Python 模块导入、工具注册逻辑完整
- `get_extensions_prompt_section()` 正确生成注入段落
- `toggle_extension()` 支持启用/禁用
- subtitle_style 扩展存在，结构正确

#### MCP 客户端（mcp_client.py）✅ 正确
- HTTP/JSON 工具发现（`/tools` 端点）和调用（`/tools/{name}` 端点）
- 工具命名格式 `server_name.tool_name` 正确
- `get_tools_description()` 正确生成注入段落
- 错误处理完善（超时 10s 发现 / 60s 调用）
- **注意**：MCP 工具不会被 `_execute_tool()` 路由到 mcp_client，Agent 需要单独的调用路径。目前 `react_agent._execute_tool()` 只在 tool_registry 中查找，**MCP 工具无法通过主 Agent 的 TAOR 循环调用**

#### 知识库（knowledge_base.py）✅ 正确
- BM25 算法实现完整（IDF、TF、文档长度归一化）
- 中文分词使用 `[\u4e00-\u9fff]` 单字符匹配 + 英文数字分词
- 文件持久化到 `src/db/knowledge/project_{id}.json`
- 项目级隔离
- `knowledge_search` 和 `knowledge_add` 工具在 tool_registry 中注册

#### 项目偏好记忆（project_memory.py）✅ 正确
- 文件持久化到 `src/db/memories/project_{id}.json`
- 偏好提取使用规则匹配（不调用 LLM），覆盖：风格、字幕颜色、BGM 音量、通用偏好
- `get_preferences_summary()` 正确生成注入段落
- 保留最近 50 条备注
- **注意**：`_MEMORY_DIR` 路径为 `src/db/memories/`，使用了 `parent.parent.parent / "src" / "db" / "memories"` 的相对路径，可能因启动目录不同而指向错误位置

#### API 接口 ✅ 全部实现
- 所有 REST 端点（/api/agent/chat、chat/stream、deep-research、execute、analyze/{id}、tools、sessions、session/{id}）均已实现
- 3 个 WebSocket 通道（/ws、/ws/render、/ws/system）均已实现
- MCP API（/api/mcp/servers、call、tools）均已实现
- SSE 格式正确（`data: {json}\n\n`）

#### 前端 ChatSidebar.vue ⚠️ 有 BUG
- **BUG：`sendMessage()` 函数（第 205-214 行）存在重复消息问题**
  - 第 210 行先 `store.messages.push({role:'user', content: text})`
  - 第 211 行再调用 `store.processChatMessageStream('')` 传入**空字符串**
  - 而 `processChatMessageStream` 内部第 259 行会再次 `push({role:'user', content: input})`
  - **结果**：每次发消息会 push 两条用户消息（一条有内容，一条空字符串），后端收到空消息
- **死代码**：`origSend`、`realSendMessage`、`sendMessageFinal` 三个函数定义了但未被使用（看起来是修复尝试但未生效）
- 模板绑定的 `@click="sendMessage"` 和 `@keydown.enter.exact.prevent="sendMessage"` 调用的是有 BUG 的版本
- 流式消息展示、工具卡片可视化、确认面板逻辑本身正确

#### 前端 store（project.js）✅ 基本正确
- SSE 事件处理完整（session/thinking/tool_start/tool_result/reply/done/error）
- 确认/取消流程正确（confirmAction/cancelAction）
- 自动刷新逻辑正确（_handleToolResult）
- 聊天历史持久化正确
- **注意**：`processChatMessageStream` 被传入空字符串时会向 API 发送空消息

### 16.3 问题汇总

#### 严重（影响功能正确执行）

| # | 问题 | 位置 | 影响 | 状态 |
|---|------|------|------|------|
| 1 | ~~前端 sendMessage 重复消息~~ | ChatSidebar.vue:205-214 | 每次发送产生两条用户消息 + 后端收到空字符串 | ✅ 已修复 |
| 2 | ~~MCP 工具无法通过主 Agent 调用~~ | react_agent.py `_execute_tool()` | MCP 工具描述注入了提示词，但执行时只在 tool_registry 中查找 | ✅ 已修复 |

#### 中等（影响部分功能质量）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 3 | **多 Agent Executor 每轮只执行一个工具** | multi_agent.py:117 `break` | Executor 无法并行调用多个工具，效率受限 |
| 4 | **多 Agent Executor 跳过参数校验和 Hook** | multi_agent.py:111 | 工具执行绕过 Pydantic 校验和 before/after hook，可能导致参数不合法 |
| 5 | **工具数量声明不准确** | 文档 | 声明 94+ 实际 73 个 |

#### 轻微（不影响核心功能）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 6 | 死代码（origSend/realSendMessage/sendMessageFinal） | ChatSidebar.vue:217-233 | 代码可读性 |
| 7 | 多 Agent 未复用 ReAct Agent 的工具解析逻辑 | multi_agent.py:91-94 | 代码重复 |
| 8 | 项目偏好存储路径使用多层 parent 相对定位 | project_memory.py:15 | 可能因启动目录不同导致路径错误 |
| 9 | WebSocket 基础设施存在但前端未使用 | ws_api.py | /ws 和 /ws/system 前端未接入 |
| 10 | /api/tools/logs 端点返回空数据 | tool_api.py | 日志功能未实现 |

### 16.4 结论

**大部分功能可以正确执行**，核心的 TAOR 循环、流式对话、73 个工具、会话管理、技能/扩展系统、知识库、偏好记忆均实现完整。

**需要修复才能正确执行的功能**：
1. ~~**前端发送消息**~~ — ✅ 已修复：sendMessage 改为直接调用 processChatMessageStream(text)，删除死代码
2. ~~**MCP 外部工具调用**~~ — ✅ 已修复：_execute_tool() 增加 MCP 路由，MCP 工具未在 registry 中时自动路由到 mcp_client
3. ~~**多 Agent Executor**~~ — ✅ 已修复：移除 break 支持多工具执行，增加 Pydantic 校验和 Hook
4. ~~**工具数量**~~ — ✅ 已修正：文档已更新为 73 个

**仍存在的轻微问题**（不影响核心功能）：
- 多 Agent 未复用 ReAct Agent 的工具解析逻辑（代码重复）
- 项目偏好存储路径使用多层 parent 相对定位（可能因启动目录不同导致路径错误）
- WebSocket 基础设施存在但前端未使用（/ws 和 /ws/system）
- /api/tools/logs 端点返回空数据（功能未实现）
