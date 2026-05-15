# 三方接入 core-nexus-ai 指南

> 本文档面向需要调用 core-nexus-ai 推理服务的第三方开发者。

---

## 1. 快速开始

| 项目 | 值 |
|------|-----|
| 服务地址 | `http://{host}:9666`（默认 `http://127.0.0.1:9666`） |
| API 文档 | `http://{host}:9666/docs`（Swagger UI） |
| 认证方式 | API Key，Header 携带 `X-API-Key: <key>` |
| 模型选择 | **无需指定 model**，系统自动使用该任务类型的默认模型 |

### 30 秒上手

```bash
# LLM 文本生成
curl -X POST http://localhost:9666/llm \
  -H "X-API-Key: cn-你的key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好"}'

# 响应: {"request_id":"uuid","task_type":"LLM","model":"deepseek-chat","output":{"text":"你好！..."},"usage":{"input_tokens":10,"output_tokens":50}}
```

---

## 2. 认证

### 认证开关

认证由服务端环境变量 `LLM_HUB_AUTH_ENABLED` 控制。**未启用时所有请求无需认证**。

### 请求方式

所有请求在 HTTP Header 中携带 API Key：

```
X-API-Key: cn-a1b2c3d4e5f6789012345678901234567890ab
```

> API Key 格式: `cn-` 前缀 + 48 位十六进制字符，共 51 字符。联系管理员获取。

**认证方式区分：**

| Header | 用途 | 说明 |
|--------|------|------|
| `X-API-Key: <key>` | **第三方调用（推荐）** | 用于所有推理端点，API Key 无角色区分，统一为推理权限 |
| `Authorization: Bearer <jwt>` | 管理后台专用 | Web 登录后自动使用，第三方请勿使用此方式 |

> **注意：** 第三方接入请统一使用 `X-API-Key`，不要使用 `Authorization`。

### WebSocket 认证

WebSocket 无法设置自定义 Header，需要通过 URL query 参数传递 token：

```
ws://host:port/asr/stream?token=cn-你的key
ws://host:port/digital-human/stream?token=cn-你的key
```

支持传入 API Key（`cn-` 前缀）或 JWT token。

### 无需认证的端点

`GET /health`、`GET /metrics`、`GET /`

### 认证错误

| 状态码 | 含义 | 典型原因 |
|--------|------|---------|
| 401 | 未认证 | 未提供 Key / Key 无效 / Key 已禁用 / Key 已过期 |
| 403 | 权限不足 | API Key 不能访问管理接口 |

---

## 3. 通用响应格式

### 成功响应（推理接口）

```json
{
  "request_id": "uuid-string",
  "task_type": "LLM",
  "model": "deepseek-chat",
  "output": { ... },
  "usage": { "input_tokens": 100, "output_tokens": 200 }
}
```

### 错误响应

所有异常统一返回：

```json
{"error": "错误描述", "code": "ERROR_CODE", "status_code": 400}
```

| status_code | 含义 | 典型场景 |
|-------------|------|---------|
| 400 | 请求参数错误 | 缺少必填字段、参数类型错误 |
| 404 | 模型未找到 | 指定了不存在的模型名 |
| 500 | 服务端内部错误 | 模型推理异常 |
| 502 | 上游服务错误 | API 供应商返回异常 |
| 504 | 请求超时 | 推理耗时超过限制 |

---

## 4. 接口一览

### 推理端点

| 端点 | 方法 | 功能 | 流式支持 |
|------|------|------|---------|
| `/llm` | POST | 文本生成 | ✅ `/llm/stream` (SSE) |
| `/tts` | POST | 文本转语音 | ✅ `/tts/stream` (SSE) |
| `/asr` | POST | 语音识别 | ✅ `/asr/stream` (WebSocket) |
| `/text-to-image` | POST | 文本生成图像 | - |
| `/image-to-image` | POST | 图像编辑 | - |
| `/video-gen` | POST | 视频生成（文本/图片/音频输入） | - |
| `/text-to-music` | POST | 文本生成音乐 | - |
| `/music-to-music` | POST | 音乐编辑 | - |
| `/agent` | POST | AI 智能体 | ✅ `/agent/stream` (SSE) |
| `/other` | POST | 其他工具 | - |
| `/digital-human` | POST | 数字人视频生成 | ✅ `/digital-human/async`（异步任务） |
| `/digital-human` | WebSocket | 数字人实时流式生成 | ✅ `WS /digital-human/stream` |
| `/multimodal` | POST | 多模态推理（文本+图像+音频+视频） | ✅ `/multimodal/stream` (SSE) |
| `/multimodal/audio` | POST | 多模态音频输出（强制返回音频） | - |
| `/api/models` | GET | 查询可用模型 | - |

### `/v1` 前缀兼容

所有推理端点支持 `/v1` 前缀（如 `/v1/llm`），用于 OpenAI SDK 兼容。

**注意：** `/v1` 前缀需要服务端设置环境变量 `LLM_HUB_API_PREFIX=/v1`。**默认不启用**。启用后，同时支持带前缀和不带前缀两种路径（即 `/llm` 和 `/v1/llm` 都可访问）。`/v1` 前缀仅适用于推理端点，不影响管理接口、健康检查等。

---

## 5. LLM 文本生成

### 请求

```
POST /llm
POST /llm/stream    （流式，SSE）
```

**请求体：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 二选一 | 单轮对话文本 |
| `messages` | array | 二选一 | 多轮对话，格式 `[{"role":"user","content":"..."}]` |
| `model` | string | 否 | 指定模型，不填用默认 |
| `generation` | object | 否 | 生成参数 |
| `provider_options` | object | 否 | 供应商特有参数，直接透传 |
| `enable_thinking` | bool | 否 | 启用深度思考模式（支持 Claude、DeepSeek-R1 等推理模型） |
| `enable_search` | bool | 否 | 启用联网搜索（需服务端配置搜索服务，所有 LLM 模型通用） |

**generation 支持的参数：** `temperature`（0-2）、`max_tokens`（≥1）、`top_p`、`frequency_penalty`、`presence_penalty`、`seed` 等。

**示例：**

```json
// 单轮
{"prompt": "解释量子计算", "generation": {"temperature": 0.7, "max_tokens": 1000}}

// 多轮
{"messages": [
  {"role": "user", "content": "你好"},
  {"role": "assistant", "content": "你好！"},
  {"role": "user", "content": "介绍一下你自己"}
]}

// 启用深度思考
{"prompt": "求解 x^2 + 3x - 4 = 0", "enable_thinking": true}

// 启用联网搜索（所有 LLM 模型通用，需服务端配置搜索服务）
{"prompt": "今天的新闻", "enable_search": true}
```

### 响应

```json
{
  "request_id": "uuid",
  "task_type": "LLM",
  "model": "deepseek-chat",
  "output": {"text": "生成的文本内容..."},
  "usage": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}
}
```

**联网搜索响应**（`enable_search: true` 时，`output` 中包含搜索引用）：

```json
{
  "request_id": "uuid",
  "task_type": "LLM",
  "model": "deepseek-chat",
  "output": {
    "text": "根据搜索结果，...",
    "search_results": [
      {"title": "文章标题", "url": "https://...", "snippet": "摘要..."},
      {"title": "...", "url": "https://...", "snippet": "..."}
    ]
  },
  "usage": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}
}
```

> `search_results` 仅在搜索实际触发时返回。如果 LLM 判断不需要搜索（如常识问题），则不会包含此字段。

### 流式响应（SSE）

请求体与 `/llm` 相同，响应为 Server-Sent Events 流：

```
data: {"text": "生成的"}

data: {"text": "内容片段"}

data: [DONE]
```

客户端逐行读取 `data: ` 前缀后的 JSON，`[DONE]` 表示结束。

---

## 6. KV Cache / Prompt Caching

KV Cache 是**前缀匹配缓存**机制：服务端缓存已计算过的 token，下次请求只要前面部分完全一致，就可以复用缓存、跳过重复计算。对于支持缓存的模型（DeepSeek、OpenAI、GLM、Claude、阿里云千问等），可通过 `provider_options` 启用。

### 6.1 使用方式

#### 方式一：自动缓存（推荐）

设置 `use_kv_cache: true`，框架自动处理缓存标记注入：

```json
{
  "model": "qwen-max",
  "messages": [
    {"role": "system", "content": "你是一个专业的AI助手..."},
    {"role": "user", "content": "你好"}
  ],
  "provider_options": {"use_kv_cache": true}
}
```

#### 方式二：session_id（多轮对话）

通过 `session_id` 维持会话上下文，适合需要记住之前对话的场景：

```json
// 第一次请求 - 响应中返回 session_id
{
  "model": "qwen-max",
  "messages": [{"role": "user", "content": "我叫张三，今年25岁"}],
  "provider_options": {"use_kv_cache": true}
}
// 响应: {"output": {"text": "...", "session_id": "abc123..."}}

// 第二次请求 - 使用相同 session_id，模型记住上下文
{
  "model": "qwen-max",
  "messages": [{"role": "user", "content": "我今年多大？"}],
  "provider_options": {"session_id": "abc123..."}
}
// 响应: 模型能回答出 "25岁"
```

### 6.2 缓存命中信息

响应 `usage` 中包含缓存统计：

```json
{
  "usage": {
    "input_tokens": 100,
    "output_tokens": 50,
    "cached_tokens": 80
  }
}
```

`cached_tokens` 表示缓存命中的 token 数，命中越多，速度越快、费用越低。

### 6.3 支持缓存的模型

| 模型/供应商 | 缓存机制 | 说明 |
|------------|---------|------|
| DeepSeek | 自动前缀缓存 | 无需额外参数 |
| OpenAI GPT | 自动前缀缓存 | >1024 token 自动缓存 |
| GLM | 自动前缀缓存 | OpenAI 兼容 |
| Claude | Prompt Caching | 框架自动注入 `cache_control` |
| 阿里云千问 | DashScope cache_control | 通过 `use_kv_cache` 触发 |
| Qwen-Max/Plus/Turbo | session_id | 通过 `use_kv_cache` 触发 |

### 6.4 完整示例（Python）

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:9666",
    headers={"X-API-Key": "cn-your-api-key"},
    timeout=300
)

session_id = None

for user_input in ["你好", "继续刚才的话题", "还有补充吗？"]:
    payload = {
        "model": "qwen-max",
        "messages": [
            {"role": "system", "content": "你是一个专业的AI助手..."},
            {"role": "user", "content": user_input},
        ],
        "provider_options": {"use_kv_cache": True}
    }
    if session_id:
        payload["provider_options"]["session_id"] = session_id

    resp = client.post("/llm", json=payload)
    data = resp.json()

    session_id = data.get("output", {}).get("session_id")
    cached = data.get("usage", {}).get("cached_tokens", 0)
    print(f"回复: {data['output']['text']}")
    print(f"缓存命中: {cached} tokens")

client.close()
```

### 6.5 注意事项

| 操作 | 是否影响缓存 | 说明 |
|------|------------|------|
| 追加新的对话轮次 | 不影响 | 前缀不变，只是后面多了内容 |
| 修改 system prompt | **影响** | 前缀从头开始就不同了 |
| 精简/摘要历史记录 | **影响** | 前缀内容变了 |
| 只改最后一轮的问题 | 不影响 | 改的是标记点之后的内容 |

### 6.6 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 未返回 session_id | 模型不支持 KV Cache | 检查模型是否在支持列表中 |
| cached_tokens 始终为 0 | 未设置 use_kv_cache | 确认 provider_options 中有该字段 |
| 上下文未保持 | session_id 未传递 | 检查每次请求都传入了相同的 session_id |

---

## 7. TTS 文本转语音

```
POST /tts
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | **是** | 要合成的文本 |
| `model` | string | 否 | 指定模型 |
| `speaker` | string | 否 | 音色名称 |
| `ref_audio` | string | 否 | 参考音频（语音克隆，base64/Data URL/文件路径/URL） |
| `ref_text` | string | 否 | 参考音频对应的文本（配合 `ref_audio` 使用） |
| `instruct` | string | 否 | 自然语言指令描述（用于 VoiceDesign 模型） |
| `language` | string | 否 | 语言（Chinese/English/Auto） |
| `generation` | object | 否 | speed、pitch 等参数 |

### 7.1 Qwen3-TTS-Flash Realtime（低延迟流式）

模型名：`qwen3-tts-flash-realtime`

基于 DashScope WebSocket Realtime API 的低延迟 TTS，适用于实时对话、语音助手等场景。

**特有参数（通过 `generation` 传递）：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `voice` | string | `Cherry` | 音色 |
| `format` | string | `mp3` | 音频格式：`mp3`、`wav`、`pcm`、`opus` |
| `sample_rate` | int | `24000` | 采样率：8000、16000、24000、48000 |

**系统音色列表：**

Cherry（甜美女声）、Serena（温柔女声）、Chelsie（活泼女声）、Ethan（沉稳男声）、Momo（可爱女声）、Vivian（知性女声）、Moon（温暖男声）、Maia（优雅女声）、Kai（阳光男声）、Jade（清亮女声）、Marc（成熟男声）、Cora（活力女声）、Dylan（年轻男声）、Eric（磁性男声）、Ryan（清新男声）、Aiden（少年男声）、Ono_Anna（日语女声）、Sohee（韩语女声）、Uncle_Fu（浑厚男声）

**示例：**

```json
{
  "text": "你好世界",
  "model": "qwen3-tts-flash-realtime",
  "speaker": "Serena",
  "generation": {
    "format": "mp3",
    "sample_rate": 24000
  }
}
```

### 响应格式（双格式）

TTS 端点根据 `Accept` 请求头返回不同格式：

**格式一：JSON 响应** — 请求头包含 `Accept: application/json`

```json
{
  "request_id": "uuid",
  "task_type": "TTS",
  "model": "edge-tts",
  "output": {
    "audio": "data:audio/wav;base64,UklGRi...",
    "format": "wav"
  },
  "usage": {}
}
```

`output.audio` 为 Data URL 格式，可直接在 `<audio>` 标签使用。

**格式二：音频二进制流** — 请求头包含 `Accept: audio/*` 或不指定 `Accept`

直接返回音频二进制数据，响应头包含：

```
Content-Type: audio/wav
Content-Length: 123456
Content-Disposition: attachment; filename=speech.wav
```

> **建议：** 需要直接播放或保存音频文件时，使用音频二进制流格式（不设置 `Accept: application/json`）；需要在 JSON 中获取音频数据时，显式设置 `Accept: application/json`。

**curl 示例：**

```bash
# 直接保存为音频文件
curl -X POST http://localhost:9666/tts \
  -H "X-API-Key: cn-你的key" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界"}' \
  --output speech.wav

# 获取 JSON 格式（含 base64 音频）
curl -X POST http://localhost:9666/tts \
  -H "X-API-Key: cn-你的key" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界"}'
```

### 7.2 TTS 流式合成（SSE）

```
POST /tts/stream
```

请求体与 `POST /tts` 相同。响应为 SSE 流，逐块返回音频数据，客户端可边接收边播放。

**SSE 事件格式：**

```
data: {"audio": "base64音频片段", "format": "mp3"}

data: {"audio": "base64音频片段", "format": "mp3"}

data: {"audio": null, "format": "mp3", "usage": {"input_tokens": 4, "output_tokens": 8}}

data: {"request_id": "uuid", "task_type": "TTS", "model": "qwen3-tts-flash-realtime", "output": {}, "usage": {}, "done": true}
```

> **注意：** 流式接口需要模型本身支持流式输出（如 `qwen3-tts-flash-realtime`），其他模型会退化为一次性返回。

**curl 示例：**

```bash
curl -N -X POST http://localhost:9666/tts/stream \
  -H "X-API-Key: cn-你的key" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界", "model": "qwen3-tts-flash-realtime", "speaker": "Cherry"}'
```

**JavaScript 示例（边接收边播放）：**

```javascript
async function ttsStream(text, voice = 'Cherry') {
  const resp = await fetch(`${API_BASE}/tts/stream`, {
    method: 'POST',
    headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model: 'qwen3-tts-flash-realtime', speaker: voice }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  const audioChunks = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      const data = JSON.parse(line.slice(6));
      if (data.done) break;
      if (data.audio) {
        const binary = atob(data.audio);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        audioChunks.push(bytes);
      }
    }
  }

  const blob = new Blob(audioChunks, { type: 'audio/mpeg' });
  new Audio(URL.createObjectURL(blob)).play();
}
```

---

## 8. ASR 语音识别

### 8.1 一次性识别

```
POST /asr
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `audio` | string | **是** | - | 音频数据（base64 / Data URL / 文件路径 / HTTP URL） |
| `model` | string | 否 | 默认模型 | 指定模型 |
| `language` | string | 否 | 自动检测 | 语言代码（zh/en/ja 等） |
| `return_segments` | bool | 否 | `false` | 返回带时间戳的句级分段 |
| `word_timestamps` | bool | 否 | `false` | 返回词级时间戳（仅 Faster-Whisper） |
| `generation` | object | 否 | `{}` | 生成参数 |

**支持的音频格式：** WAV（推荐）、MP3、FLAC、OGG、M4A

#### 基础响应

```json
{
  "request_id": "uuid",
  "task_type": "ASR",
  "model": "faster-whisper-large-v3",
  "output": {"text": "识别文本", "language": "zh"},
  "usage": {"input_tokens": 0, "output_tokens": 50}
}
```

#### 带时间戳的响应（`return_segments: true`）

```json
{
  "output": {
    "text": "今天天气真不错，我们出去玩吧。",
    "language": "zh",
    "duration": 3.5,
    "segments": [
      {"start": 0.0, "end": 1.8, "text": "今天天气真不错，"},
      {"start": 2.0, "end": 3.5, "text": "我们出去玩吧。"}
    ]
  }
}
```

#### 带词级时间戳（`return_segments: true` + `word_timestamps: true`）

```json
{
  "output": {
    "text": "今天天气真不错",
    "segments": [
      {
        "start": 0.0,
        "end": 1.8,
        "text": "今天天气真不错",
        "words": [
          {"start": 0.0, "end": 0.4, "word": "今天", "probability": 0.98},
          {"start": 0.4, "end": 0.8, "word": "天气", "probability": 0.97}
        ]
      }
    ]
  }
}
```

#### 各适配器时间戳支持

| 适配器 | 句级时间戳 | 词级时间戳 |
|--------|-----------|-----------|
| Faster-Whisper（本地） | ✅ | ✅ |
| OpenAI Whisper | ✅ | - |
| Google STT | ✅ | ✅ |
| DashScope | ✅ | - |
| Qwen-ASR / DeepSeek ASR | - | - |

#### 生成 SRT 字幕

设置 `return_segments: true` 获取带时间戳的 segments，客户端自行转换为 SRT 格式。

**SRT 格式规范：**

```
序号（从 1 开始）
开始时间 --> 结束时间（格式 HH:MM:SS,mmm）
字幕文本
（空行分隔）
```

**Python 转换示例：**

```python
def to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg["start"])
        end = format_srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}")
    return "\n\n".join(lines)

def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# 调用
resp = client.post("/asr", json={
    "audio": "data:audio/wav;base64,UklGRi...",
    "return_segments": True
})
segments = resp.json()["output"]["segments"]
srt_text = to_srt(segments)
print(srt_text)
```

**输出示例：**

```
1
00:00:00,000 --> 00:00:01,800
今天天气真不错，

2
00:00:02,000 --> 00:00:03,500
我们出去玩吧。
```

### 8.2 实时流式识别（WebSocket）

```
WS ws://host:port/asr/stream?token=cn-你的key
```

> **认证：** WebSocket 通过 URL query 参数 `token` 传递 API Key，未认证连接将被关闭（关闭码 4001）。

**协议流程：** 连接（携带 token） → 发送 config 帧 → 持续发送 audio 帧 → 发送 stop 帧

**客户端 → 服务端：**

```jsonc
// 1. config 帧（首帧，必填）
{"type": "config", "format": "wav", "sample_rate": 16000, "language": "zh"}

// 2. audio 帧（持续发送）
{"type": "audio", "data": "<base64编码的音频片段>"}

// 3. stop 帧
{"type": "stop"}
```

**服务端 → 客户端：**

```jsonc
{"type": "started", "request_id": "uuid"}                                         // 连接成功
{"type": "result", "text": "识别文本", "is_final": true, "sentence": {"text": "...", "begin_time": 0, "end_time": 1000}}  // 逐句结果
{"type": "completed", "text": "完整识别文本"}                                        // 识别完成
{"type": "error", "message": "错误描述"}                                            // 错误
```

**Python 示例：**

```python
import asyncio, json, base64, websockets

API_KEY = "cn-你的key"

async def asr_stream(audio_path):
    async with websockets.connect(f"ws://127.0.0.1:9666/asr/stream?token={API_KEY}") as ws:
        await ws.send(json.dumps({"type": "config", "format": "wav", "sample_rate": 16000}))
        msg = json.loads(await ws.recv())
        print("Started:", msg["request_id"])

        with open(audio_path, "rb") as f:
            while chunk := f.read(6400):
                await ws.send(json.dumps({"type": "audio", "data": base64.b64encode(chunk).decode()}))

        await ws.send(json.dumps({"type": "stop"}))
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "result":
                print(f"  {'[FINAL]' if data['is_final'] else '[PARTIAL]'} {data['text']}")
            elif data["type"] == "completed":
                print(f"Done: {data['text']}"); break

asyncio.run(asr_stream("audio.wav"))
```

---

## 9. 文本生成图像

```
POST /text-to-image
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | **是** | 图像描述 |
| `negative_prompt` | string | 否 | 反向提示词 |
| `model` | string | 否 | 指定模型，不填用默认 |
| `generation` | object | 否 | width、height、steps、seed 等 |

**generation 常用参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `width` | int | 图像宽度 |
| `height` | int | 图像高度 |
| `seed` | int | 随机种子（-1 为随机） |

**示例：**

```json
{
  "prompt": "一只橘色的小猫趴在窗台上，阳光洒落",
  "negative_prompt": "模糊, 变形",
  "generation": {"width": 1024, "height": 1024}
}
```

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "TEXT_TO_IMAGE",
  "model": "wan2.7-image-pro",
  "output": {"image": "data:image/png;base64,..."},
  "usage": {}
}
```

`output.image` 为 Data URL 格式，可直接用于 `<img>` 标签的 `src`。

---

## 10. 图像编辑

```
POST /image-to-image
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | **是** | 编辑指令 |
| `image` | string | **是** | 原图（base64/Data URL/HTTP URL） |
| `mask` | string | 否 | 蒙版（base64/Data URL），白色区域为编辑区 |
| `model` | string | 否 | 指定模型，不填用默认 |
| `generation` | object | 否 | 生成参数 |

**示例（指令式编辑）：**

```json
{
  "prompt": "把背景换成海边",
  "image": "data:image/jpeg;base64,/9j/..."
}
```

**示例（蒙版重绘）：**

```json
{
  "prompt": "把天空变成星空",
  "image": "data:image/jpeg;base64,/9j/...",
  "mask": "data:image/png;base64,iVBOR..."
}
```

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "IMAGE_TO_IMAGE",
  "model": "flux-kontext",
  "output": {"image": "data:image/png;base64,..."},
  "usage": {}
}
```

`output.image` 为 Data URL 格式，可直接用于 `<img>` 标签的 `src`。

---

## 11. 文本生成音乐

```
POST /text-to-music
```

### 11.1 基础参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | **是** | 音乐描述/风格标签 |
| `mode` | string | 否 | 生成模式，见下方模式说明，默认 `generate` |
| `lyrics` | string | 否 | 歌词（支持结构标签），不传则生成纯音乐 |
| `duration` | float | 否 | 时长（秒），默认 30，最大 240 |
| `model` | string | 否 | 指定模型，不填使用默认模型 |
| `generation` | object | 否 | 生成参数，见下方 generation 参数表 |
| `provider_options` | object | 否 | 供应商特有参数，直接透传 |

**歌词结构标签：** 使用 `[verse]`（主歌）、`[chorus]`（副歌）、`[bridge]`（桥段）等标记段落结构。不传 `lyrics` 时生成纯音乐（无人声）。

### 11.2 生成模式

| mode | 名称 | 说明 | 需要输入音频 |
|------|------|------|------------|
| `generate` | 基础生成 | 根据描述和歌词生成完整音乐 | 否 |
| `retake` | 变奏 | 基于相同 prompt 生成不同变体 | 否 |
| `repaint` | 局部重绘 | 对音频指定时间段重新生成 | **是** |
| `edit` | 歌词编辑 | 替换歌词并重新生成 | **是** |
| `extend` | 扩展 | 在音频前后扩展时长 | **是** |
| `cover` | 翻唱 | 基于参考音频翻唱 | **是** |

**模式与模型兼容性：**

| mode | ACE-Step 1.5 | ACE-Step XL Turbo | SoulX-Singer |
|------|:---:|:---:|:---:|
| `generate` | ✅ | ✅ | - |
| `retake` | ✅ | ✅ | - |
| `repaint` | ✅ | ✅ | - |
| `edit` | ✅ | - | - |
| `extend` | ✅ | - | - |
| `cover` | - | ✅ | ✅ |

### 11.3 generation 参数

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `steps` | int | 60（XL Turbo: 8） | 10-100 | 推理步数，越多质量越高但越慢 |
| `guidance_scale` | float | 15.0（XL Turbo: 固定 1.0） | 1-30 | CFG 引导强度，越大越贴合 prompt |
| `seed` | int | -1（随机） | -1 ~ 2147483647 | 随机种子，固定种子可复现 |
| `guidance_interval` | float | 0.5 | 0-1 | 引导区间（仅 ACE-Step 1.5） |
| `omega_scale` | float | 10.0 | - | omega 缩放（仅 ACE-Step 1.5） |
| `cpu_offload` | bool | false | - | CPU 卸载，显存不足时开启 |
| `torch_compile` | bool | false | - | 编译优化，首次较慢但后续加速 |

### 11.4 模式特有参数

| 参数 | 类型 | 适用模式 | 说明 |
|------|------|---------|------|
| `audio` | string | repaint / edit / extend / cover | 输入音频（base64 / Data URL / 文件路径 / URL） |
| `variance` | float | retake | 变奏程度，0-1，默认 0.5，越大差异越大 |
| `start_time` | float | repaint | 重绘起始时间（秒），默认 0 |
| `end_time` | float | repaint | 重绘结束时间（秒），默认 10 |
| `extend_left` | float | extend | 左侧扩展时长（秒） |
| `extend_right` | float | extend | 右侧扩展时长（秒） |

### 11.5 完整调用示例

**基础生成（带歌词）：**

```json
{
  "prompt": "温暖的流行歌曲，钢琴伴奏，轻柔的女声",
  "duration": 30,
  "lyrics": "[verse]\n星空下的夜晚\n微风轻轻吹过\n[chorus]\n我想要飞翔\n飞到那遥远的地方",
  "generation": {
    "steps": 60,
    "guidance_scale": 15.0,
    "seed": 42
  }
}
```

**纯音乐生成（不传 lyrics）：**

```json
{
  "prompt": "轻柔的钢琴独奏，古典风格，缓慢节奏，带有忧伤感",
  "duration": 60
}
```

**变奏生成（retake）：** 基于相同描述生成不同版本，`variance` 控制差异程度。

```json
{
  "prompt": "温暖的流行歌曲，钢琴伴奏",
  "mode": "retake",
  "duration": 30,
  "lyrics": "[verse]\n星空下的夜晚\n[chorus]\n我想要飞翔",
  "variance": 0.7,
  "generation": {"seed": 42}
}
```

**局部重绘（repaint）：** 对音频中指定时间段重新生成，其余部分保持不变。

```json
{
  "prompt": "加入更多吉他元素",
  "mode": "repaint",
  "duration": 30,
  "audio": "data:audio/wav;base64,UklGRi...",
  "start_time": 5.0,
  "end_time": 15.0
}
```

**歌词编辑（edit）：** 上传音频并替换歌词，保持原曲风格重新生成。

```json
{
  "prompt": "保持原曲风格",
  "mode": "edit",
  "duration": 30,
  "audio": "data:audio/wav;base64,UklGRi...",
  "lyrics": "[verse]\n新的歌词内容\n替换原有歌词\n[chorus]\n副歌部分也改了"
}
```

**音乐扩展（extend）：** 在现有音频前后追加内容。`extend_left` 向前扩展，`extend_right` 向后扩展。

```json
{
  "prompt": "延续前面的旋律风格",
  "mode": "extend",
  "duration": 30,
  "audio": "data:audio/wav;base64,UklGRi...",
  "extend_left": 10.0,
  "extend_right": 15.0
}
```

**翻唱（cover）：** 基于参考音频进行翻唱（仅 ACE-Step XL Turbo 支持）。

```json
{
  "prompt": "用爵士风格翻唱",
  "mode": "cover",
  "duration": 30,
  "audio": "data:audio/wav;base64,UklGRi...",
  "lyrics": "[verse]\n原来的歌词\n[chorus]\n副歌部分"
}
```

### 11.6 响应格式

```json
{
  "request_id": "uuid",
  "task_type": "TEXT_TO_MUSIC",
  "model": "ACE-Step/Ace-Step1.5",
  "output": {
    "audio": "data:audio/wav;base64,UklGRi..."
  },
  "usage": {"input_tokens": 0, "output_tokens": 0}
}
```

`output.audio` 为 Data URL 格式，可直接用于 `<audio>` 标签播放。

### 11.7 Python 完整示例

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:9666",
    headers={"X-API-Key": "cn-your-key"},
    timeout=600  # 音乐生成耗时较长，建议设置较大超时
)

# 基础生成
resp = client.post("/text-to-music", json={
    "prompt": "温暖的流行歌曲，钢琴伴奏",
    "duration": 30,
    "lyrics": "[verse]\n星空下的夜晚\n[chorus]\n我想要飞翔",
    "generation": {"steps": 60, "seed": 42}
})
audio_data = resp.json()["output"]["audio"]  # data:audio/wav;base64,...

# 纯音乐
resp = client.post("/text-to-music", json={
    "prompt": "轻柔的钢琴独奏，古典风格",
    "duration": 60
})

# 变奏
resp = client.post("/text-to-music", json={
    "prompt": "温暖的流行歌曲，钢琴伴奏",
    "mode": "retake",
    "variance": 0.7,
    "generation": {"seed": 42}
})

# 保存音频文件
import base64
header, b64 = audio_data.split(",", 1)
with open("music.wav", "wb") as f:
    f.write(base64.b64decode(b64))

client.close()
```

---

## 12. 音乐编辑

```
POST /music-to-music
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio` | string | **是** | 原始音频（base64/Data URL/文件路径/URL） |
| `prompt` | string | 否 | 编辑指令 |
| `style` | string | 否 | 目标风格 |
| `model` | string | 否 | 指定模型 |
| `generation` | object | 否 | edit_strength 等参数 |

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "MUSIC_TO_MUSIC",
  "model": "default",
  "output": {"audio": "data:audio/wav;base64,..."},
  "usage": {}
}
```

`output.audio` 为 Data URL 格式，可直接用于 `<audio>` 标签播放。

---

## 13. 视频生成

```
POST /video-gen
```

统一端点，支持文本、图片、音频输入生成视频。系统根据模型能力和输入内容自动匹配生成模式。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 至少一种 | 文本描述 |
| `image` | string | 至少一种 | 图片输入（base64/Data URL/HTTP URL） |
| `audio` | string | 至少一种 | 音频输入 |
| `negative_prompt` | string | 否 | 反向提示词 |
| `model` | string | 否 | 指定模型，不填用默认 |
| `generation` | object | 否 | 生成参数（见下方） |

> 至少提供 `prompt`、`image`、`audio` 其中之一。不同模型支持的输入组合不同，超出模型能力时会返回参数校验错误。

**generation 常用参数：**

| 参数 | 类型 | 说明 | 适用模型 |
|------|------|------|---------|
| `num_frames` | int | 帧数 | 本地模型 |
| `fps` | int | 帧率，默认 16 | 本地模型 |
| `width` | int | 视频宽度 | 本地模型 |
| `height` | int | 视频高度 | 本地模型 |
| `seed` | int | 随机种子（-1 为随机） | 通用 |
| `resolution` | string | 分辨率（`720P` / `1080P`） | HappyHorse |
| `duration` | int | 时长（秒，3-15） | HappyHorse |
| `watermark` | bool | 是否添加水印 | HappyHorse |

**示例（文本生成视频）：**

```json
{
  "prompt": "一只小猫在草地上奔跑",
  "generation": {"num_frames": 81, "fps": 16}
}
```

**示例（图片生成视频）：**

```json
{
  "image": "data:image/jpeg;base64,/9j/...",
  "prompt": "人物转头微笑",
  "generation": {"num_frames": 81, "fps": 16, "seed": 42}
}
```

**示例（HappyHorse API 模型）：**

```json
{
  "prompt": "一只小猫在草地上奔跑",
  "model": "happyhorse-1.0-t2v",
  "generation": {"resolution": "1080P", "duration": 5}
}
```

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "VIDEO_GEN",
  "model": "happyhorse-1.0-t2v",
  "output": {"video": "data:video/mp4;base64,..."},
  "usage": {}
}
```

`output.video` 为 Data URL 格式，可直接用于 `<video>` 标签播放。本地模型带图片输入时可能返回异步任务 `{"job_id": "uuid"}`，通过 `GET /api/admin/jobs/{job_id}` 查询进度。

> **注意：** 视频生成耗时较长（API 模型通常 1-5 分钟，本地模型更久），建议设置较大的请求超时。

---

## 14. AI 智能体（Agent）

```
POST /agent
POST /agent/stream    （流式，SSE）
```

Agent 以 ReAct 循环运行：LLM 自动调用工具 → 观察结果 → 做出决策，直到给出最终回答。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `messages` | array | **是** | 对话历史，格式 `[{"role":"user","content":"..."}]`，不可为空 |
| `model` | string | 否 | 指定 LLM 模型 |
| `tools` | array | 否 | 自定义工具（OpenAI function-calling 格式） |
| `mcp_servers` | array | 否 | MCP 服务器列表，如 `[{"url": "http://...", "transport": "http"}]` |
| `max_iterations` | int | 否 | 最大循环次数，默认 10 |
| `generation` | object | 否 | LLM 生成参数 |
| `provider_options` | object | 否 | 供应商特有参数 |

**内置工具（无需定义，自动可用）：**

| 工具 | 说明 |
|------|------|
| `get_current_time` | 获取当前 UTC 时间 |
| `calculate` | 计算数学表达式 |
| `code_execution` | 执行 Python 代码 |
| `http_request` | 发送 HTTP 请求 |

**示例（使用内置工具）：**

```json
{
  "messages": [{"role": "user", "content": "现在几点了？"}],
  "max_iterations": 5
}
```

**示例（自定义工具）：**

```json
{
  "messages": [{"role": "user", "content": "查询北京天气"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "查询城市天气",
      "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
      }
    }
  }],
  "max_iterations": 5
}
```

**示例（MCP 服务器）：**

```json
{
  "messages": [{"role": "user", "content": "帮我查一下数据库里的用户数"}],
  "mcp_servers": [{"url": "http://localhost:3000/mcp", "transport": "http"}],
  "max_iterations": 10
}
```

**同步响应：**

```json
{
  "request_id": "uuid",
  "task_type": "AGENT",
  "model": "deepseek-chat",
  "output": {"text": "现在是 2025-05-09 14:30:00 UTC"},
  "usage": {"input_tokens": 150, "output_tokens": 30}
}
```

### 流式响应（SSE）

请求 `POST /agent/stream`，响应为 SSE 事件流：

```
data: {"type": "agent_thinking", "content": "用户想知道时间，我需要调用工具..."}

data: {"type": "tool_call", "name": "get_current_time", "arguments": "{}"}

data: {"type": "tool_result", "name": "get_current_time", "content": "2025-05-09 14:30:00 UTC"}

data: {"type": "agent_response", "content": "现在是 2025-05-09 14:30:00 UTC"}

data: {"type": "agent_done"}
```

---

## 15. 其他工具（Other）

```
POST /other
```

通用工具端点，用于非标准任务类型（人声分离、音频处理等）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 否 | 指定工具/模型（如 `demucs`） |
| `inputs` | object | 否 | 通用输入（音频/图片/文本等） |
| `generation` | object | 否 | 生成参数 |
| `provider_options` | object | 否 | 供应商特有参数 |

### 15.1 人声分离（Demucs）

```json
{
  "model": "demucs",
  "inputs": {
    "audio": "data:audio/wav;base64,UklGRi..."
  }
}
```

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "OTHER",
  "model": "htdemucs",
  "output": {
    "stems": {
      "vocals": {"audio": "data:audio/wav;base64,..."},
      "drums": {"audio": "data:audio/wav;base64,..."},
      "bass": {"audio": "data:audio/wav;base64,..."},
      "other": {"audio": "data:audio/wav;base64,..."}
    }
  },
  "usage": {}
}
```

### 15.2 高质量人声分离（UVR5）

```json
{
  "model": "uvr5",
  "inputs": {
    "audio": "data:audio/wav;base64,UklGRi..."
  }
}
```

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "OTHER",
  "model": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
  "output": {
    "stems": {
      "Vocals": {"audio": "data:audio/wav;base64,..."},
      "Instrumental": {"audio": "data:audio/wav;base64,..."}
    }
  },
  "usage": {}
}
```

---

## 16. 数字人视频生成

### 16.1 同步生成

```
POST /digital-human
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 与 audio 二选一 | 要说的文本 |
| `audio` | string | 与 audio 二选一 | 音频（base64/Data URL） |
| `avatar_id` | string | 否 | 虚拟形象 ID |
| `image` | string | 否 | 自定义头像（base64/Data URL），建议分辨率 ≥ 512x512 |
| `video` | string | 否 | 视频（base64/Data URL），用于逐帧唇形同步 |
| `model` | string | 否 | 指定模型 |
| `generation` | object | 否 | video_width、video_height、fps、face_enhancement 等 |

**响应：**

```json
{
  "request_id": "uuid",
  "task_type": "DIGITAL_HUMAN",
  "model": "sadtalker",
  "output": {
    "video": "data:video/mp4;base64,...",
    "format": "mp4",
    "duration": 5.2,
    "width": 512,
    "height": 512
  }
}
```

### 16.2 异步生成

适用于长视频或批量生成场景。

```
POST /digital-human/async
```

请求体与同步接口相同。

**响应：**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted"
}
```

使用 `GET /api/admin/jobs/{job_id}` 查询任务状态。

### 16.3 实时流式生成（WebSocket）

```
WS ws://host:port/digital-human/stream?token=cn-你的key
```

> **认证：** WebSocket 通过 URL query 参数 `token` 传递 API Key，未认证连接将被关闭（关闭码 4001）。

**协议流程：** 连接（携带 token） → 发送 config 帧（含图片/视频）→ 持续发送 audio 帧（PCM int16, 16kHz）→ 发送 stop 帧

**客户端 → 服务端：**

```jsonc
// 1. config 帧（首帧，必填）
// image 和 video 二选一，video 优先
{"type": "config", "image": "data:image/jpeg;base64,...", "fps": 25, "model": "wav2lip", "pads": [0, 10, 0, 0]}

// 2. audio 帧（持续发送，PCM int16 16kHz）
{"type": "audio", "data": "<base64编码的PCM音频片段>"}

// 3. stop 帧
{"type": "stop"}
```

**服务端 → 客户端：**

```jsonc
{"type": "started", "request_id": "uuid"}             // 连接成功
// 二进制帧 = JPEG 视频帧（逐帧发送）
{"type": "completed", "frames_sent": 150}             // 生成完成
{"type": "error", "message": "错误描述"}               // 错误
```

> **注意：** 与 ASR WebSocket 不同，数字人流的视频帧以**二进制帧**（而非 JSON 文本帧）发送，客户端需用 `websocket.recv()` 接收并判断帧类型。

---

## 17. 多模态（MULTIMODAL）

支持文本、图像、音频、视频的组合输入，可返回文本或音频。

### 17.1 同步推理

```
POST /multimodal
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 与 messages 二选一 | 文本输入 |
| `messages` | array | 与 prompt 二选一 | 完整多模态对话 |
| `image` | string | 否 | 单张图片（base64/URL） |
| `images` | array | 否 | 多张图片 |
| `audio` | string | 否 | 单个音频（base64/URL） |
| `audios` | array | 否 | 多个音频 |
| `video` | string | 否 | 视频文件（base64/URL） |
| `video_frames` | array | 否 | 视频帧（图片列表形式，每项为 base64/URL） |
| `modalities` | array | 否 | 输出模态：`["text"]`（默认）或 `["text","audio"]` |
| `voice` | string | 否 | 输出音色（Chelsie / Ethan / Tina 等） |
| `audio_format` | string | 否 | 输出音频格式：`wav`（默认）/ `mp3` |
| `enable_thinking` | bool | 否 | 思考模式（默认 `false`，部分模型支持） |
| `enable_search` | bool | 否 | 联网搜索（默认 `false`，需服务端配置搜索服务） |
| `model` | string | 否 | 指定模型 |
| `generation` | object | 否 | 生成参数 |
| `provider_options` | object | 否 | 供应商特有参数 |

**纯文本对话示例：**

```json
{"prompt": "你好，请介绍一下你自己"}
```

**图像理解示例：**

```json
{
  "prompt": "描述这张图片的内容",
  "image": "data:image/jpeg;base64,..."
}
```

**多模态对话示例：**

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "这两张图片有什么区别？"},
        {"type": "image_url", "image_url": {"url": "https://example.com/img1.jpg"}},
        {"type": "image_url", "image_url": {"url": "https://example.com/img2.jpg"}}
      ]
    }
  ]
}
```

**语音对话示例：**

```json
{
  "prompt": "讲一个简短的故事",
  "modalities": ["text", "audio"],
  "voice": "Chelsie"
}
```

**纯文本输出响应：**

```json
{
  "request_id": "uuid",
  "task_type": "MULTIMODAL",
  "model": "qwen-omni",
  "output": {"text": "生成的文本内容..."}
}
```

**文本+音频输出响应：**

```json
{
  "request_id": "uuid",
  "task_type": "MULTIMODAL",
  "model": "qwen-omni",
  "output": {
    "text": "你好！很高兴认识你...",
    "audio": "data:audio/wav;base64,UklGRiQ...",
    "audio_format": "wav"
  }
}
```

### 17.2 流式推理（SSE）

```
POST /multimodal/stream
```

请求体与 `/multimodal` 相同。响应为 SSE 流：

```
data: {"text": "生成的文本片段"}

data: {"audio": "base64编码的音频片段", "audio_format": "wav"}

data: [DONE]
```

### 17.3 音频输出

```
POST /multimodal/audio
```

强制返回音频格式的响应。请求体与 `/multimodal` 相同，但自动启用音频输出模态。

响应格式与 TTS 一致，根据 `Accept` 头返回不同格式：

- `Accept: application/json` → 返回 JSON（含 base64 音频）
- `Accept: audio/*` 或不指定 → 返回音频二进制流

---

## 18. 查询可用模型

```
GET /api/models
GET /api/models?task_type=LLM    （按类型过滤）
```

**响应：**

```json
{
  "models": [
    {
      "name": "core-nexus-ai",
      "task_type": "LLM",
      "provider_name": "core-nexus-ai",
      "capabilities": {},
      "default_generation": {}
    },
    {
      "name": "deepseek-chat",
      "task_type": "LLM",
      "provider_name": "deepseek",
      "capabilities": {
        "stream": true,
        "max_tokens": 8192,
        "input_tags": ["文"],
        "output_tags": ["文"]
      },
      "default_generation": {}
    }
  ]
}
```

> **注意：** 响应格式为 `{"models": [...]}`，列表第一项 `name: "core-nexus-ai"` 是系统自动生成的虚拟默认条目，代表该 task_type 的默认模型。后续为实际的 API 模型。

### 模型能力标签

每个模型的 `capabilities` 中包含 `input_tags` 和 `output_tags` 两个字段，标识该模型支持的输入输出类型：

**标签含义：**

| 标签 | 含义 | 示例场景 |
|------|------|---------|
| `文` | 文本 | LLM 对话输入/输出、文生图提示词、TTS 文本输入 |
| `图` | 图片 | 图像理解输入、图生图/图生视频输入、文生图输出 |
| `音` | 音频 | 语音识别输入、语音克隆参考音频、TTS/音乐输出 |
| `视频` | 视频 | 视频理解输入、视频生成输出 |

**按任务类型的典型输入输出：**

| 任务类型 | input_tags | output_tags | 说明 |
|----------|-----------|-------------|------|
| LLM | `["文"]` | `["文"]` | 文本对话 |
| TTS | `["文"]` 或 `["文","音"]` | `["音"]` | 文本转语音，部分支持参考音频克隆 |
| ASR | `["音"]` | `["文"]` | 语音转文本 |
| TEXT_TO_IMAGE | `["文"]` | `["图"]` | 文本生成图像 |
| IMAGE_TO_IMAGE | `["图","文"]` | `["图"]` | 图像+指令编辑 |
| VIDEO_GEN | `["文"]` / `["图","文"]` | `["视频"]` | 视频生成（文本/图片/音频输入） |
| TEXT_TO_MUSIC | `["文"]` | `["音"]` | 文本生成音乐 |
| DIGITAL_HUMAN | `["文","图"]` 或 `["文","音","图"]` | `["视频"]` | 数字人视频 |
| MULTIMODAL (视觉) | `["文","图"]` | `["文"]` | 图像理解 |
| MULTIMODAL (全能) | `["文","图","音"]` | `["文","音"]` | 全模态对话+语音 |

---

## 19. 完整调用示例

### Python (httpx)

```python
import httpx, json, base64

API_BASE = "http://localhost:9666"
API_KEY = "cn-你的key"

client = httpx.Client(
    base_url=API_BASE,
    headers={"X-API-Key": API_KEY},
    timeout=300,
)

# 1. LLM 文本生成
resp = client.post("/llm", json={"prompt": "你好"})
print(resp.json()["output"]["text"])

# 2. LLM 流式生成
with client.stream("POST", "/llm/stream", json={"prompt": "写一首诗"}) as resp:
    for line in resp.iter_lines():
        if line.startswith("data: ") and line != "data: [DONE]":
            chunk = json.loads(line[6:])
            print(chunk["text"], end="")

# 3. LLM 多轮对话 + KV Cache
resp = client.post("/llm", json={
    "messages": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你？"},
        {"role": "user", "content": "介绍一下你自己"}
    ],
    "provider_options": {"use_kv_cache": True}
})

# 4. LLM 启用深度思考
resp = client.post("/llm", json={
    "prompt": "求解 x^2 + 3x - 4 = 0",
    "enable_thinking": True
})

# 4.1 LLM 联网搜索
resp = client.post("/llm", json={
    "prompt": "今天的AI新闻有哪些",
    "enable_search": True
})
data = resp.json()
print(data["output"]["text"])
for ref in data["output"].get("search_results", []):
    print(f"  [{ref['title']}]({ref['url']})")

# 5. ASR 语音识别（带时间戳，可转 SRT 字幕）
def format_srt_time(seconds):
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def to_srt(segments):
    return "\n\n".join(
        f"{i}\n{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n{seg['text'].strip()}"
        for i, seg in enumerate(segments, 1)
    )

resp = client.post("/asr", json={
    "audio": "data:audio/wav;base64,UklGRi...",
    "return_segments": True
})
output = resp.json()["output"]
srt_text = to_srt(output["segments"])
with open("subtitle.srt", "w", encoding="utf-8") as f:
    f.write(srt_text)

# 6. TTS 语音合成（获取音频文件）
resp = client.post("/tts", json={"text": "你好世界"})  # 不设 Accept，返回音频二进制
with open("speech.wav", "wb") as f:
    f.write(resp.content)

# 7. TTS 语音合成（获取 JSON）
resp = client.post("/tts", json={"text": "你好世界"},
                   headers={"Accept": "application/json"})
audio_data = resp.json()["output"]["audio"]  # data:audio/wav;base64,...

# 7.1 Qwen3-TTS-Flash Realtime（低延迟流式 TTS）
resp = client.post("/tts", json={
    "text": "你好世界",
    "model": "qwen3-tts-flash-realtime",
    "speaker": "Serena",
    "generation": {"format": "mp3", "sample_rate": 24000}
})
with open("speech_realtime.mp3", "wb") as f:
    f.write(resp.content)

# 7.2 TTS 流式合成（SSE，边接收边保存）
audio_chunks = []
with client.stream("POST", "/tts/stream", json={
    "text": "你好世界",
    "model": "qwen3-tts-flash-realtime",
    "speaker": "Cherry",
}) as resp:
    for line in resp.iter_lines():
        if line.startswith("data: ") and not line.endswith("[DONE]"):
            data = json.loads(line[6:])
            if data.get("done"):
                break
            audio_b64 = data.get("audio")
            if audio_b64:
                audio_chunks.append(base64.b64decode(audio_b64))
with open("speech_stream.mp3", "wb") as f:
    f.write(b"".join(audio_chunks))

# 8. 多模态视觉理解（原 VL 已合并到多模态）
resp = client.post("/multimodal", json={
    "prompt": "描述这张图片",
    "image": "data:image/jpeg;base64,/9j/..."
})

# 9. 视频生成（文本输入）
resp = client.post("/video-gen", json={
    "prompt": "一只小猫在草地上奔跑",
    "generation": {"num_frames": 81, "fps": 16}
})
video_data = resp.json()["output"]["video"]  # data:video/mp4;base64,...

# 9.1 视频生成（图片输入）
resp = client.post("/video-gen", json={
    "image": "data:image/jpeg;base64,/9j/...",
    "prompt": "人物转头微笑",
    "generation": {"resolution": "1080P", "duration": 5}
})

# 10. AI Agent 智能体
resp = client.post("/agent", json={
    "messages": [{"role": "user", "content": "现在几点了？"}],
    "max_iterations": 5
})
print(resp.json()["output"]["text"])

# 11. 数字人视频生成（异步）
resp = client.post("/digital-human/async", json={
    "text": "大家好，欢迎观看本期视频",
    "avatar_id": "avatar_001"
})
job_id = resp.json()["job_id"]

# 12. 多模态语音对话
resp = client.post("/multimodal", json={
    "prompt": "讲一个简短的故事",
    "modalities": ["text", "audio"],
    "voice": "Chelsie"
})

client.close()
```

### JavaScript (fetch)

```javascript
const API_BASE = 'http://localhost:9666';
const API_KEY = 'cn-你的key';
const headers = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json',
};

// LLM 文本生成
async function chat(prompt) {
  const resp = await fetch(`${API_BASE}/llm`, {
    method: 'POST', headers,
    body: JSON.stringify({ prompt }),
  });
  return (await resp.json()).output.text;
}

// LLM 流式生成
async function chatStream(prompt) {
  const resp = await fetch(`${API_BASE}/llm/stream`, {
    method: 'POST', headers,
    body: JSON.stringify({ prompt }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ') && line !== 'data: [DONE]') {
        const chunk = JSON.parse(line.slice(6));
        process.stdout.write(chunk.text || '');
      }
    }
  }
}

// TTS 获取音频 Blob 并播放
async function tts(text) {
  const resp = await fetch(`${API_BASE}/tts`, {
    method: 'POST', headers,
    body: JSON.stringify({ text }),
  });
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  new Audio(url).play();
}

// TTS 获取 JSON（含 base64 音频）
async function ttsJson(text) {
  const resp = await fetch(`${API_BASE}/tts`, {
    method: 'POST',
    headers: { ...headers, 'Accept': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const data = await resp.json();
  return data.output.audio; // data:audio/wav;base64,...
}

// Qwen3-TTS-Flash Realtime（低延迟流式 TTS）
async function ttsRealtime(text, voice = 'Serena') {
  const resp = await fetch(`${API_BASE}/tts`, {
    method: 'POST', headers,
    body: JSON.stringify({
      text,
      model: 'qwen3-tts-flash-realtime',
      speaker: voice,
      generation: { format: 'mp3', sample_rate: 24000 },
    }),
  });
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  new Audio(url).play();
}

// 视频生成（统一端点，支持文本/图片/音频输入）
async function videoGen(prompt, image = null) {
  const body = { prompt, generation: { num_frames: 81, fps: 16 } };
  if (image) body.image = image;
  const resp = await fetch(`${API_BASE}/video-gen`, {
    method: 'POST', headers,
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  return data.output.video; // data:video/mp4;base64,...
}

// AI Agent 智能体
async function agent(messages) {
  const resp = await fetch(`${API_BASE}/agent`, {
    method: 'POST', headers,
    body: JSON.stringify({ messages, max_iterations: 5 }),
  });
  const data = await resp.json();
  return data.output.text;
}
```

### Java

```java
import java.net.http.*;
import java.net.URI;

HttpClient client = HttpClient.newHttpClient();
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://localhost:9666/llm"))
    .header("X-API-Key", "cn-你的key")
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString("{\"prompt\":\"你好\"}"))
    .build();
HttpResponse<String> resp = client.send(request, HttpResponse.BodyHandlers.ofString());
System.out.println(resp.body());
```

---

## 20. 媒体输入格式说明

所有接受媒体输入的接口（image、audio、video、ref_audio 等字段）统一支持以下 4 种格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| **Data URL** | `data:image/jpeg;base64,/9j/4AAQ...` | 最明确，推荐 |
| **纯 Base64** | `/9j/4AAQSkZJRgABAQAAAQ...` | 自动识别格式 |
| **HTTP URL** | `https://example.com/photo.jpg` | 自动下载 |
| **本地文件路径** | `D:/photos/test.jpg` | 服务端可访问的路径 |

> 纯 Base64 字符串会自动识别，无需手动添加 `data:...;base64,` 前缀。

---

## 21. 接入检查清单

- [ ] 从管理员获取 API Key（`cn-xxxx...`，无角色区分，统一为推理权限）
- [ ] 确认服务地址（默认 `http://host:9666`）
- [ ] 确认认证是否启用（未启用时无需 Key）
- [ ] HTTP 请求：在请求头添加 `X-API-Key: <key>`（三方专用，勿用 `Authorization`）
- [ ] WebSocket 请求：URL 添加 `?token=<key>` 参数（如 `ws://host/asr/stream?token=cn-xxx`）
- [ ] 处理 401（Key 失效）和 403（权限不足）错误
- [ ] 调用 `GET /api/models` 确认可用模型列表
- [ ] 不指定 model 即可使用默认模型，无需硬编码模型名
- [ ] 如需 `/v1` 前缀（OpenAI SDK 兼容），联系管理员确认已设置 `LLM_HUB_API_PREFIX=/v1`
