# Claude Code Harness 指南

## 什么是 Harness？

> **Agentic Harness（代理线束）**：将语言模型转变为能干的编程代理的工具、上下文管理和执行环境。*Claude Code 就是 Harness，Claude 是其中的模型。*

核心区分：Harness 是**确定性基础设施**，Claude（模型）无法自行选择运行 Hook、绕过权限或加载 Memory。这些都是在模型控制之外、由 Harness 执行的操作。

---

## Harness 的七大子系统

### 1. 代理循环（Agentic Loop）

Think → Act → Observe → Repeat 循环：

```
收集上下文（读文件、搜索代码）
  → 执行动作（编辑、运行命令、调用工具）
    → 验证结果（检查输出、运行测试）
      → 重复直到任务完成或用户介入
```

Harness 管理迭代过程，Claude 在每一步提供推理。

### 2. 内置工具

| 工具 | 用途 |
|------|------|
| Read | 读取文件内容 |
| Edit | 对文件进行精确编辑 |
| Write | 创建或覆盖文件 |
| Bash | 执行 Shell 命令 |
| Glob | 按模式查找文件 |
| Grep | 搜索文件内容 |
| WebFetch | 获取网页内容 |
| WebSearch | 搜索互联网 |
| Agent | 委派给子代理 |
| AskUserQuestion | 向用户提问 |

### 3. 权限控制（Permission Gating）

每个工具调用都经过 Deny → Ask → Allow 评估：

- **Deny**：直接阻止
- **Ask**：提示用户确认（默认行为）
- **Allow**：无需询问直接执行

权限配置在 `settings.json` 的 `permissions` 键下，`allow` 和 `deny` 数组支持 glob 模式：

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(python *)"
    ],
    "deny": [
      "Bash(rm -rf *)"
    ]
  }
}
```

### 4. Hook 机制

Hook 是在固定生命周期节点触发的确定性处理器，由 **Harness（而非模型）** 控制执行时机。

**生命周期事件：**

| 事件 | 触发时机 |
|------|---------|
| `SessionStart` | 会话开始时 |
| `PreToolUse` | 工具执行前 |
| `PostToolUse` | 工具执行后 |
| `Stop` | Claude 完成回复时 |
| `SubagentStop` | 子代理完成时 |

**Hook 类型：**

| 类型 | 说明 |
|------|------|
| Command Hook | 运行 Shell 命令 |
| HTTP Hook | 发送 HTTP 请求 |
| MCP Tool Hook | 调用 MCP 服务器工具 |
| Prompt Hook | 向提示注入文本 |
| Agent Hook | 委派给子代理 |

**配置示例：**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "npx eslint --fix $FILE_PATH"
          }
        ]
      }
    ]
  }
}
```

### 5. Memory 加载

会话启动时，Harness 自动加载：

- `CLAUDE.md` 文件（项目根目录、父目录、`~/.claude/CLAUDE.md`）
- Auto-Memory（`~/.claude/projects/<path>/memory/`）
- Settings 中的 Rules

### 6. 上下文管理

- **Compaction**：自动压缩旧对话，保持在上下文窗口限制内
- **MCP Tool Search**：按需发现 MCP 服务器工具，无需预先加载所有描述
- **Session 持久化**：对话可跨重启恢复

### 7. Settings 层级

设置按以下优先级合并（从高到低）：

1. **Managed Settings**（企业策略，用户不可修改）
2. **命令行标志**
3. **本地项目设置**（`.claude/settings.local.json`）
4. **共享项目设置**（`.claude/settings.json`）
5. **用户设置**（`~/.claude/settings.json`）

数组类型（如 `permissions.allow`）跨作用域**合并**而非替换。

---

## 本项目当前配置参考

### 现有配置文件

`.claude/settings.local.json`：

```json
{
  "permissions": {
    "allow": [
      "Bash(npx vite:*)",
      "Bash(npm run *)",
      "Bash(python -c ' *)",
      "Bash(python *)"
    ]
  }
}
```

### 推荐补充配置

根据本项目特点（Tauri + Vue 3 + FastAPI），可以在 `.claude/settings.json` 中添加共享配置：

```json
{
  "permissions": {
    "allow": [
      "Bash(python *)",
      "Bash(npm run *)",
      "Bash(npx *)",
      "Bash(cd synthetix-vue && *)",
      "Bash(alembic *)",
      "Bash(pytest *)",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git log *)"
    ]
  }
}
```

### 可能的 Hook 用例

**编辑后自动 lint：**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "cd synthetix-vue && npx eslint --fix \"$FILE_PATH\""
          }
        ]
      }
    ]
  }
}
```

**会话开始时检查环境：**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "python -c \"import sys; print(sys.version)\""
      }
    ]
  }
}
```

---

## 与本项目 Agent 架构的对比

本项目的 `react_agent.py` 实现了一个类似 Harness 的架构：

| Claude Code Harness | 本项目 ReAct Agent |
|---------------------|-------------------|
| Agentic Loop（TAOR） | TAOR 循环（Think → Act → Observe → Repeat） |
| 内置工具（Read/Edit/Bash） | `tool_registry.py` 注册的 74+ 工具 |
| 权限控制（Allow/Deny/Ask） | 工具权限（`read_only` / `modify` / `destructive`） |
| Hook 机制（生命周期钩子） | `before_execute` / `after_execute` Hook |
| Settings 层级 | `config/default.json` + `config/settings.json` |
| Memory（CLAUDE.md） | `project_memory.py`（项目偏好记忆） |
| MCP 协议 | `mcp_client.py`（外部 MCP Server 连接） |
| 子代理（Agent） | `multi_agent.py`（Planner → Executor → Reviewer） |

可以看到，本项目在 Agent 层面几乎复刻了 Claude Code Harness 的核心设计模式。
