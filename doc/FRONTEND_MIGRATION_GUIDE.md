# 前端 API 迁移指南

> 本文档详细说明后端 API 优化后的所有变更，供前端开发人员参考。

---

## 目录

1. [响应格式变更](#响应格式变更)
2. [路由变更对照表](#路由变更对照表)
3. [详细 API 变更说明](#详细-api-变更说明)
4. [迁移步骤](#迁移步骤)

---

## 响应格式变更

### 统一响应格式

所有 API 现在使用统一的响应格式：

#### 成功响应

```json
{
  "success": true,
  "data": { /* 实际数据 */ },
  "message": "操作成功",
  "code": 200,
  "timestamp": 1710123456
}
```

#### 错误响应

```json
{
  "success": false,
  "error": "ErrorType",
  "message": "错误描述",
  "code": 400,
  "timestamp": 1710123456
}
```

#### 分页响应

```json
{
  "success": true,
  "data": {
    "items": [ /* 数据列表 */ ],
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10
  },
  "message": "获取成功",
  "code": 200,
  "timestamp": 1710123456
}
```

### 前端适配方式

```javascript
// 之前的调用方式
const response = await fetch('/get_source_videos', { method: 'POST', body: data });
const videos = await response.json();  // 直接是数组

// 现在的调用方式
const response = await fetch('/api/videos', { method: 'GET' });
const result = await response.json();
if (result.success) {
    const videos = result.data;  // 数据在 data 字段中
} else {
    console.error(result.message);  // 错误信息在 message 字段
}
```

---

## 路由变更对照表

### 视频服务 (/api/videos)

| 原路由 | 新路由 | HTTP方法 | 变更说明 |
|--------|--------|----------|----------|
| POST /get_source_videos | GET /api/videos | GET | 改为 GET，使用查询参数 |
| POST /del_source_videos | DELETE /api/videos/{id} | DELETE | 改为 RESTful 风格 |
| POST /update_video_source | PATCH /api/videos/{id} | PATCH | 改为 RESTful 风格 |
| POST /upload_source_videos_stream | POST /api/videos | POST | 创建资源用 POST |
| GET /get_description | GET /api/videos/{id}/description | GET | 作为资源子路径 |
| POST /download_video | POST /api/videos/download | POST | 下载操作 |
| POST /process_video | POST /api/videos/process | POST | 处理操作 |
| POST /extract_frame | POST /api/videos/extract-frame | POST | 提取帧操作 |
| POST /get_audio | POST /api/videos/extract-audio | POST | 提取音频操作 |
| POST /add_audio_to_video | POST /api/videos/add-audio | POST | 添加音频操作 |
| POST /transcribe | POST /api/videos/transcribe | POST | 转录操作 |
| POST /video_add_subtitle | POST /api/videos/subtitle | POST | 添加字幕操作 |
| POST /start_compression | POST /api/videos/compress | POST | 压缩操作 |
| GET /get_random_video | GET /api/videos/random | GET | 获取随机视频 |

### 音频服务 (/api/audios)

| 原路由 | 新路由 | HTTP方法 | 变更说明 |
|--------|--------|----------|----------|
| POST /get_source_audio | GET /api/audios | GET | 改为 GET，使用查询参数 |
| POST /del_source_audio | DELETE /api/audios/{id} | DELETE | 改为 RESTful 风格 |
| POST /save_timbre | POST /api/audios | POST | 创建资源用 POST |
| POST /fish_voice | POST /api/audios/tts/fish-speech | POST | TTS 子资源 |
| POST /sovits_v4 | POST /api/audios/tts/sovits-v4 | POST | TTS 子资源 |
| POST /separate_audio | POST /api/audios/separate | POST | 分离操作 |
| POST /merge_audio | POST /api/audios/merge | POST | 合并操作 |
| GET /get_random_audio | GET /api/audios/random | GET | 获取随机音色 |

### 工具服务 (/api/tools)

| 原路由 | 新路由 | HTTP方法 | 变更说明 |
|--------|--------|----------|----------|
| POST /upload_file_stream | POST /api/tools/upload/video | POST | 上传视频 |
| POST /upload_all_file_stream | POST /api/tools/upload/file | POST | 上传通用文件 |
| GET /get_config | GET /api/tools/config | GET | 获取配置 |
| POST /save_config | PATCH /api/tools/config | PATCH | 更新配置 |
| GET /loadLog | GET /api/tools/logs | GET | 获取日志 |

### AI 服务 (/api/ai)

| 原路由 | 新路由 | HTTP方法 | 变更说明 |
|--------|--------|----------|----------|
| POST /llm_get_source | POST /api/ai/keywords | POST | 关键词获取 |
| POST /videos_transitions | POST /api/ai/video-transitions | POST | 视频转场 |
| GET /llm_conversation | GET /api/ai/optimize-prompt | GET | 优化提示词 |

---

## 详细 API 变更说明

### 1. 视频服务 API

#### 1.1 获取视频列表

```javascript
// 旧接口
POST /get_source_videos
Content-Type: application/json

{
    "current": 1,
    "size": 10,
    "video_type": null
}

// 新接口
GET /api/videos?page=1&page_size=10&video_type=1

// 响应格式变更
// 旧格式: 直接返回 { items: [], total: 0, ... }
// 新格式: { success: true, data: { items: [], total: 0, ... }, message: "..." }
```

#### 1.2 删除视频

```javascript
// 旧接口
POST /del_source_videos
Content-Type: application/json

{
    "id": 123
}

// 新接口
DELETE /api/videos/123

// 响应格式变更
// 旧格式: { success: true, data: { id: 123 }, message: "删除成功" }
// 新格式: { success: true, data: { id: 123 }, message: "删除成功", code: 200, timestamp: 123456 }
```

#### 1.3 上传视频

```javascript
// 旧接口
POST /upload_source_videos_stream
Content-Type: multipart/form-data

// 新接口
POST /api/videos
Content-Type: multipart/form-data

// 响应变更: 返回 201 状态码
```

#### 1.4 获取视频描述

```javascript
// 旧接口
GET /get_description?id=123

// 新接口
GET /api/videos/123/description

// 响应格式
{
    "success": true,
    "data": { "description": "视频描述内容" },
    "message": "获取描述成功"
}
```

### 2. 音频服务 API

#### 2.1 获取音色列表

```javascript
// 旧接口
POST /get_source_audio
Content-Type: application/json

{
    "current": 1,
    "size": 10
}

// 新接口
GET /api/audios?page=1&page_size=10
```

#### 2.2 保存音色

```javascript
// 旧接口
POST /save_timbre
Content-Type: multipart/form-data

// 新接口
POST /api/audios
Content-Type: multipart/form-data

// 表单字段保持不变
```

#### 2.3 Fish Speech TTS

```javascript
// 旧接口
POST /fish_voice
Content-Type: application/json

{
    "text": "要合成的文本",
    "audio_source_id": 1,
    "speed_factor": 1.0,
    ...
}

// 新接口
POST /api/audios/tts/fish-speech
Content-Type: application/json

// 请求体保持不变
```

### 3. 工具服务 API

#### 3.1 上传文件

```javascript
// 旧接口
POST /upload_file_stream
Content-Type: multipart/form-data

// 响应
{
    "webPath": "/static/uploads/xxx.mp4",
    "localPath": "D:/project/.../xxx.mp4",
    "duration": "00:01:30"
}

// 新接口
POST /api/tools/upload/video
Content-Type: multipart/form-data

// 响应
{
    "success": true,
    "data": {
        "webPath": "/static/uploads/xxx.mp4",
        "localPath": "D:/project/.../xxx.mp4",
        "duration": "00:01:30"
    },
    "message": "上传成功"
}
```

#### 3.2 获取/保存配置

```javascript
// 旧接口
GET /get_config
POST /save_config

// 新接口
GET /api/tools/config
PATCH /api/tools/config

// 响应格式统一
{
    "success": true,
    "data": { /* 配置数据 */ },
    "message": "获取配置成功"
}
```

### 4. AI 服务 API

#### 4.1 根据关键词获取素材

```javascript
// 旧接口
POST /llm_get_source
Content-Type: application/json

{
    "creative": "创意描述"
}

// 新接口
POST /api/ai/keywords
Content-Type: application/json

// 响应格式统一
{
    "success": true,
    "data": { /* 结果 */ },
    "message": "获取视频素材成功"
}
```

#### 4.2 优化提示词

```javascript
// 旧接口
GET /llm_conversation?keywords_prompt=xxx&prompt_type=1

// 响应 (直接返回字符串)
"优化后的提示词"

// 新接口
GET /api/ai/optimize-prompt?prompt=xxx&prompt_type=1

// 响应
{
    "success": true,
    "data": { "optimized_prompt": "优化后的提示词" },
    "message": "提示词优化成功"
}
```

---

## 迁移步骤

### Step 1: 更新 API 基础路径

```javascript
// 之前
const API_BASE = '';

// 现在
const API_BASE = '/api';
```

### Step 2: 更新请求工具函数

```javascript
// 推荐封装统一的请求函数
async function apiRequest(url, options = {}) {
    const response = await fetch(API_BASE + url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });

    const result = await response.json();

    if (!result.success) {
        throw new Error(result.message || '请求失败');
    }

    return result.data;
}

// 使用示例
const videos = await apiRequest('/videos?page=1&page_size=10');
```

### Step 3: 批量替换路由

| 搜索 | 替换为 |
|------|--------|
| `/get_source_videos` | `/api/videos` |
| `/del_source_videos` | `/api/videos/` + id |
| `/get_source_audio` | `/api/audios` |
| `/del_source_audio` | `/api/audios/` + id |
| `/save_timbre` | `/api/audios` |
| `/fish_voice` | `/api/audios/tts/fish-speech` |
| `/sovits_v4` | `/api/audios/tts/sovits-v4` |
| `/upload_file_stream` | `/api/tools/upload/video` |
| `/get_config` | `/api/tools/config` |
| `/save_config` | `/api/tools/config` |
| `/llm_get_source` | `/api/ai/keywords` |
| `/videos_transitions` | `/api/ai/video-transitions` |
| `/llm_conversation` | `/api/ai/optimize-prompt` |

### Step 4: 更新响应处理逻辑

```javascript
// 之前
const data = await response.json();

// 现在
const result = await response.json();
const data = result.data;
if (!result.success) {
    // 处理错误
    console.error(result.message);
}
```

### Step 5: 更新 HTTP 方法

1. **GET 请求**：将 POST 改为 GET，body 参数改为 query 参数
2. **DELETE 请求**：使用 DELETE 方法，ID 放在 URL 路径中
3. **PATCH 请求**：更新操作使用 PATCH 而非 POST

---

## 兼容性说明

### 保留的请求参数

以下请求参数名称保持不变：

- 分页: `page`, `page_size` (原 `current`, `size`)
- 视频: `video_type`, `video_url`, `video_input`, etc.
- 音频: `audio_name`, `prompt_text`, `seed`, `speed`, etc.
- TTS: `text`, `audio_source_id`, `speed_factor`, etc.

### 注意事项

1. **分页参数名称变更**:
   - `current` → `page`
   - `size` → `page_size`

2. **响应码变更**:
   - 创建资源返回 `201` 而非 `200`
   - 删除成功返回 `200`

3. **错误处理**:
   - 所有错误都有统一的格式
   - `error` 字段表示错误类型
   - `message` 字段包含可读的错误描述

---

## 联系支持

如有迁移问题，请联系后端开发团队。

**文档版本**: v1.0
**更新日期**: 2026-03-27
