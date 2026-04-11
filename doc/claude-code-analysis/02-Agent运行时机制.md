# 02 - Agent 运行时机制

## 概述

Claude Code 的 Agent 运行时是其区别于传统 AI 工具的核心。通过 **TAOR 循环**和 **Ralph Loop** 的协同工作，实现了 AI 的自主持续执行能力。核心设计哲学是"**笨引擎 + 聪明模型**" — 运行时代码不含业务逻辑，所有智能决策由模型完成。

## TAOR 循环

TAOR（Think → Act → Observe → Repeat）是 Claude Code 的核心推理模式。

### 核心循环实现

```typescript
async function* query(
  messages: Message[],
  systemPrompt: string,
  context: Context,
  canUseTool: CanUseToolFn,
  toolUseContext: ToolUseContext
): AsyncGenerator {
  // 1. 构建完整提示词
  const fullPrompt = this.formatSystemPrompt(systemPrompt, context);

  // 2. 调用 Claude API
  const result = await this.queryWithBinaryFeedback(fullPrompt);

  // 3. 解析响应中的工具调用
  const toolUseMessages = assistantMessage.message.content.filter(
    _ => _.type === 'tool_use'
  );

  // 4. 执行工具调用（并行/串行策略）
  if (toolUseMessages.length > 0) {
    if (allToolsAreReadOnly) {
      for await (const message of runToolsConcurrently(toolUseMessages)) {
        yield message;
      }
    } else {
      for await (const message of runToolsSerially(toolUseMessages)) {
        yield message;
      }
    }
  }

  // 5. 递归：将工具结果加入上下文，继续循环
  yield* await this.query(newMessages, systemPrompt, updatedContext, canUseTool, toolUseContext);
}
```

### QueryEngine 驱动层

```typescript
class QueryEngine {
  async runAgentLoop(userInput: string): Promise<string> {
    let context = this.buildContext(userInput);
    while (true) {
      const systemPrompt = this.buildEffectiveSystemPrompt();
      const response = await this.callClaudeAPI(systemPrompt, context);
      const { text, toolCalls } = this.parseResponse(response);

      if (toolCalls.length === 0) return text; // 无工具调用则结束

      const toolResults = await this.executeToolCalls(toolCalls);
      context = this.appendToolResults(context, toolResults);
    }
  }
}
```

### 设计要点

| 特性 | 说明 |
|------|------|
| 循环本身是"笨"的 | 只负责**状态管理**和**执行编排**，不含业务逻辑 |
| 递归结构 | 工具结果加入上下文后递归调用自身，直到模型不再发出工具调用 |
| 并行/串行分治 | 只读工具并行执行（`runToolsConcurrently`），高危工具串行执行（`runToolsSerially`） |
| 随模型增强 | 模型能力提升后，同一个运行时自动变强，无需改代码 |

### 推测执行（Speculation）

在用户输入前，根据当前上下文预判可能的操作路径，提前生成建议。这使得响应速度更快，用户体验更流畅。

## Ralph Loop：自主持续运行框架

将 AI 从一次性工具转变为能自我纠正的自主代理。

### 核心机制

```
用户下达任务 → AI 开始执行 → AI 试图停止？
    ↓ 否                         ↓ 是
  继续执行              Stop Hook 拦截 → 检查完成承诺
                              ↓ 未满足                    ↓ 已满足
                        重新输入原始提示             任务完成，退出
                        + 当前状态 + 错误信息
                              ↓
                        AI 查看错误 → 重新尝试
```

**三大核心组件：**

1. **停止钩子（Stop Hook）**：拦截模型尝试退出的行为，检查是否满足完成承诺
2. **重新输入机制**：任务未完成时，自动将原始提示和当前状态重新输入模型
3. **自主调试循环**：AI 必须查看自己的错误，看到任务未完成，并重新尝试

### 启动方式

通过 `/ralph-loop` 命令启动，支持 `--completion-promise` 设置完成标准：

```bash
/ralph-loop --completion-promise "所有测试通过且无 lint 错误"
```

### 解决的问题

Ralph Loop 有效解决了 **"AI 懒惰"问题** — 即模型在完成部分任务后就过早停止。通过控制权反转，将 AI 从被动响应转变为主动解决问题的模式。

## 五层优先级系统提示词

系统提示词的构建是 Claude Code 实现复杂任务处理的关键机制，按优先级分五层动态合并：

```typescript
buildEffectiveSystemPrompt(): SystemPrompt {
  const layers = [
    this.getOverrideSystemPrompt(),      // 第 0 层：覆盖层（最高优先级）
    this.getCoordinatorSystemPrompt(),   // 第 1 层：协调器层
    this.getAgentSystemPrompt(),         // 第 2 层：Agent 层
    this.getCustomSystemPrompt(),        // 第 3 层：用户自定义层（CLAUDE.md）
    this.getDefaultSystemPrompt(),       // 第 4 层：默认层（最低优先级）
  ];
  return this.mergeSystemPromptLayers(layers);
}
```

### 各层详解

| 层级 | 名称 | 来源 | 作用 | 典型内容 |
|------|------|------|------|----------|
| 0 | 覆盖层 | 系统紧急指令 | 紧急修复和临时调整 | 功能开关、行为覆写 |
| 1 | 协调器层 | Agent Teams Controller | 任务拆分和子 Agent 编排 | 多 Agent 分工策略 |
| 2 | Agent 层 | Agent 定义 | 定义当前代理行为模式 | Agent 角色描述、能力声明 |
| 3 | 用户自定义层 | `CLAUDE.md` 文件 | 项目特定规则 | 编码规范、项目约定 |
| 4 | 默认层 | 系统内置 | 基础 AI 行为规范 | 工具使用指南、安全策略 |

**合并规则：** 高优先级层覆盖低优先级层的冲突部分，非冲突部分叠加。

**效果：** 同一用户在不同项目中获得不同的"AI 助手人格"，系统行为可预测、可控制、可定制。

## 保护机制

### 超时保护

- 工具执行超时：**120 秒**强制终止
- 防止长时间阻塞命令影响系统稳定性

### 输出截断

- 工具输出上限：**50,000 字节**
- 防止工具返回大量数据导致上下文溢出

### 循环检测

防止 Agent 陷入无效循环（详见 [06-权限与安全系统](06-权限与安全系统.md)）：

1. **工具调用重复检测**：连续 5 次相同工具 + 相同参数 → 判定循环
2. **内容重复检测**：50 字符滑动窗口哈希，短距离内重复 10 次 → 判定循环
3. **LLM 智能检测**：上下文 > 30 条时，调用模型判断是否循环

## Agent 统一抽象

所有 Agent 通过 `AgentBase` 抽象类实现统一入口：

```typescript
abstract class AgentBase {
  abstract mode: 'Opus' | 'Sonnet' | 'Haiku';
  abstract context: AgentContext;

  // 统一的运行入口
  abstract runAgentLoop(task: string): Promise<string>;

  // TAOR 循环
  protected async think(context: Context): Promise<Action> { ... }
  protected async act(action: Action): Promise<ActionResult> { ... }
  protected async observe(result: ActionResult): Promise<Context> { ... }
}
```

**好处：**
- 所有 Agent 共享相同的运行时基础设施（权限、日志、上下文管理）
- 新增 Agent 类型只需继承 `AgentBase` 并实现抽象方法
- 统一的错误处理和资源回收机制

## 运行时数据流

```
用户输入
  ↓
QueryEngine.buildContext()          # 构建初始上下文
  ↓
QueryEngine.buildEffectiveSystemPrompt()  # 组装五层提示词
  ↓
QueryEngine.callClaudeAPI()         # 调用 Claude API
  ↓
parseResponse()                     # 解析响应：文本 + 工具调用
  ↓
┌─ 无工具调用 → 返回文本结果
│
└─ 有工具调用 → executeToolCalls()
                  ↓
           ┌─ 只读工具 → runToolsConcurrently()  # 并行执行
           └─ 高危工具 → runToolsSerially()        # 串行执行
                  ↓
           appendToolResults()           # 结果注入上下文
                  ↓
           递归回到 callClaudeAPI()       # 继续循环
```

> **延伸阅读：**
> - 工具执行的并行/串行策略详见 [03-工具系统](03-工具系统.md)
> - 多 Agent 协作的运行时实现详见 [07-多智能体协作](07-多智能体协作.md)
> - 上下文管理与压缩详见 [05-记忆与上下文管理](05-记忆与上下文管理.md)
