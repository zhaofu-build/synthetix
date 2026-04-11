# 09 - 插件与 Hook 系统

## 概述

插件与 Hook 系统是 Claude Code 的两层扩展机制。**Plugin 系统**提供工具级扩展，通过声明式注册将第三方工具接入系统；**Hook 系统**提供拦截级扩展，在工具执行前后注入自定义逻辑。两者结合，形成了从"能力扩展"到"行为控制"的完整扩展体系。

## Plugin 系统

### 声明式注册

通过 `plugin.json` 声明插件元数据：

```json
{
  "name": "python-development",
  "version": "1.2.0",
  "description": "Python 开发专用插件，提供代码生成、审查和优化功能",
  "author": "wshobson",
  "marketplace": "claude-code-workflows",
  "tools": [
    "write-python-function",
    "refactor-python-code",
    "generate-unit-test"
  ],
  "memory": ["CLAUDE.md", "pep8.md"],
  "dependencies": {
    "python": ">=3.8",
    "pip": ">=20.0"
  },
  "permissions": {
    "required": ["read", "write", "bash"],
    "optional": ["git", "websearch"]
  }
}
```

### 插件元数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 插件唯一标识 |
| `version` | string | 语义化版本号 |
| `description` | string | 插件功能描述 |
| `tools` | string[] | 插件提供的工具列表 |
| `memory` | string[] | 插件需要的记忆文件 |
| `dependencies` | object | 系统环境依赖 |
| `permissions.required` | string[] | 必须的权限 |
| `permissions.optional` | string[] | 可选的权限 |

### 插件注册流程

```
1. 创建 plugin.json
   ↓
2. /plugin marketplaces add <组织名>/<仓库名>   # 添加插件市场
   ↓
3. /plugin install <插件名>                       # 安装插件
   ↓
4. 插件下载到 ~/.claude/plugins/
   ↓
5. 系统解析 plugin.json → 注册工具到全局工具池
```

### 插件加载

```typescript
class PluginLoader {
  async loadPlugins(): Promise<void> {
    // 1. 扫描插件目录
    const pluginPaths = await fs.readdir('~/.claude/plugins/');
    const validPlugins = pluginPaths.filter(
      async (path) => await this.validatePlugin(path)
    );

    // 2. 加载有效插件
    for (const path of validPlugins) {
      try {
        // a. 解析插件配置
        const config = await fs.readJSON(`~/.claude/plugins/${path}/plugin.json`);
        // b. 验证插件签名
        await this.validateSignature(config);
        // c. 检查依赖项
        await this.checkDependencies(config);
        // d. 加载插件代码
        const pluginCode = require(`~/.claude/plugins/${path}/index.js`);
        // e. 注册插件工具到全局工具池
        this.registerPluginTools(config, pluginCode);
      } catch (error) {
        console.error(`插件加载失败: ${path} - ${error.message}`);
      }
    }
  }
}
```

### 安全机制

| 机制 | 实现 | 目的 |
|------|------|------|
| **签名验证** | 从 Anthropic 服务器获取公钥验证 | 确保插件来源可信 |
| **依赖检查** | 加载前验证系统环境 | 防止运行时错误 |
| **版本兼容性** | 检查 `requiredClaudeVersion` | 防止 API 不兼容 |
| **沙箱隔离** | 独立 Node.js 环境 | 防止与主进程冲突 |

### 签名验证实现

```typescript
async function validateSignature(pluginConfig: PluginConfig): Promise<boolean> {
  const signature = pluginConfig.signature;
  const publicKey = await this.fetchPublicKey();    // 从 Anthropic 服务器获取
  return await crypto.verify(signature, publicKey);  // RSA 签名验证
}
```

### 依赖检查实现

```typescript
async function checkDependencies(pluginConfig: PluginConfig): Promise<boolean> {
  // 1. 检查 Claude Code 版本兼容性
  if (pluginConfig.requiredClaudeVersion > claudeVersion) {
    throw new Error('Claude Code 版本过低');
  }

  // 2. 检查系统依赖项（如 Python 版本、Node.js 版本等）
  const missingDependencies = await this.getMissingDependencies(pluginConfig);
  if (missingDependencies.length > 0) {
    throw new Error(`缺少依赖项: ${missingDependencies.join(', ')}`);
  }

  return true;
}
```

### 插件管理

通过 `settings.json` 管理插件的启用和配置：

```json
{
  "plugins": {
    "enabled": ["python-development", "java-team"],
    "disabled": ["javascript-dev"],
    "config": {
      "python-development": {
        "autoConfirmEdits": true,
        "defaultModel": "opus"
      }
    }
  }
}
```

### 插件调用与通信

插件工具的调用遵循 Claude Code 的标准工具调用协议，同时支持与内置工具协同：

```typescript
class PluginCommunication {
  async callTool(toolName: string, params: any): Promise<any> {
    // 1. 获取插件信息
    const plugin = await this.getPlugin(toolName);

    // 2. 构建调用请求
    const request = {
      tool: toolName,
      params,
      memory: await this.memorySystem.getRelevantMemory()
    };

    // 3. 通过 MCP 协议发送请求
    const response = await mcpClient.callTool(request);

    // 4. 处理响应
    return await this.processResponse(response);
  }
}
```

**通信协议：** 基于 MCP（Model Context Protocol）实现，采用 JSON-RPC 2.0 格式。

### 插件市场

支持多源获取插件：

| 来源 | 说明 |
|------|------|
| GitHub | `组织名/仓库名` 格式 |
| GitLab | 支持 GitLab 托管的插件 |
| 本地目录 | 开发调试用 |
| 远程 JSON | CDN 分发 |

```typescript
class PluginMarketplaceManager {
  async addMarketplace(marketplace: string): Promise<void> {
    const parsed = this.parseMarketplaceURL(marketplace);
    await this.updateConfig(parsed);
    await this.refreshMarketplaceList();
  }

  async installPlugin(fromMarketplace: string): Promise<void> {
    const pluginInfo = await this.fetchPluginInfo(fromMarketplace);
    await this.downloadPlugin(pluginInfo);
    await this.pluginLoader.loadPlugin(pluginInfo);
  }
}
```

## Hook 系统

### Hook 类型

| 类型 | 执行时机 | 典型用途 |
|------|----------|----------|
| **before** | 目标操作执行前 | 参数校验、权限增强、操作拦截 |
| **after** | 目标操作执行后 | 结果处理、日志记录、通知触发 |
| **around** | 包围目标操作 | 计时、事务管理、异常恢复 |
| **error** | 目标操作出错时 | 错误恢复、降级处理、告警 |

### 执行阶段

| 阶段 | 触发时机 | 可拦截对象 |
|------|----------|------------|
| `prompt` | 提示词生成时 | 系统提示词内容 |
| `response` | 响应处理时 | 模型输出内容 |
| `tooluse` | 工具调用时 | 工具调用参数 |
| `toolresult` | 工具结果返回时 | 工具执行结果 |
| `contextupdate` | 上下文更新时 | 上下文内容 |

### Hook 拦截器

```typescript
class HookInterceptor {
  async interceptToolUse(toolCall: ToolCall): Promise<ToolCall> {
    // 获取该工具在此阶段的所有 Hook
    const hooks = getHooks('tooluse', toolCall.name);

    // 按 priority 排序执行
    for (const hook of hooks.sort((a, b) => a.priority - b.priority)) {
      const result = await hook.execute(toolCall);

      if (result.type === 'blocked') {
        // 阻止操作
        throw new Error(`被 Hook "${hook.name}" 阻止: ${result.reason}`);
      }
      if (result.type === 'modified') {
        // 修改参数
        toolCall = result.toolCall;
      }
      // result.type === 'passed' → 放行，继续下一个 Hook
    }
    return toolCall;
  }
}
```

### Hook 返回类型

| 返回类型 | 效果 | 使用场景 |
|----------|------|----------|
| `blocked` | 阻止操作，抛出错误 | 安全拦截、策略执行 |
| `modified` | 修改参数后继续执行 | 参数标准化、注入额外信息 |
| `passed` | 放行，继续下一个 Hook | 日志记录、审计 |

### Hook 注册流程

```
1. 在 settings.json 中定义 Hook
   ↓
2. HookManager 注册到对应阶段
   ↓
3. 拦截器在相应时机自动调用
   ↓
4. Hook 可阻止、修改或放行操作
```

### settings.json 中的 Hook 配置

```json
{
  "hooks": {
    "before:Bash": [
      {
        "name": "block-dangerous-commands",
        "priority": 1,
        "handler": "deny-rmrf.js"
      }
    ],
    "after:Edit": [
      {
        "name": "auto-format",
        "priority": 10,
        "handler": "prettier-format.js"
      }
    ],
    "tooluse:Write": [
      {
        "name": "log-file-changes",
        "priority": 100,
        "handler": "file-change-logger.js"
      }
    ]
  }
}
```

### Hook 执行安全

- **优先级排序**：`priority` 数值越小越先执行
- **短路执行**：一旦某个 Hook 返回 `blocked`，后续 Hook 不再执行
- **沙箱运行**：危险 Hook 在独立沙箱中执行
- **错误隔离**：单个 Hook 执行失败不影响其他 Hook 和主流程

## Plugin 与 Hook 的关系

```
Plugin（能力扩展）              Hook（行为控制）
├── 新增工具                    ├── 拦截工具调用
├── 新增命令                    ├── 修改执行参数
├── 新增记忆                    ├── 拦截执行结果
└── 新增 MCP 服务               └── 审计与日志
```

| 对比项 | Plugin | Hook |
|--------|--------|------|
| 核心功能 | 添加新能力 | 拦截/修改现有行为 |
| 定义方式 | `plugin.json` + 代码 | `settings.json` 配置 |
| 触发方式 | 工具调用时 | 操作执行前后 |
| 安全要求 | 签名验证 + 沙箱 | 沙箱执行 |
| 适用场景 | 添加新的开发工具 | 自定义安全策略、日志 |

> **延伸阅读：**
> - 工具系统的接口定义详见 [03-工具系统](03-工具系统.md)
> - MCP 通信协议详见 [04-MCP协议](04-MCP协议.md)
> - Skills 系统的工作流封装详见 [08-Skills系统](08-Skills系统.md)
> - 权限与安全详见 [06-权限与安全系统](06-权限与安全系统.md)
