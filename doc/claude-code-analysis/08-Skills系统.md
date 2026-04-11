# 08 - Skills 系统

## 概述

Skills 系统将标准化工作流程封装为可复用的"技能包"，通过 `SKILL.md` 文件定义。Skills 显著提升了 AI 执行特定任务的能力：任务完成速度提升约 **40%**，操作错误率降低 **35%**，上下文占用降低 **40%-60%**。

## Skill 分类

| 类型 | 作用域 | 安装路径 | 说明 |
|------|--------|----------|------|
| **Personal Skills** | 所有项目 | `~/.claude/skills/` | 个人自定义，全局可用 |
| **Project Skills** | 当前项目 | `.claude/skills/` | 项目特定，团队共享 |
| **Plugin Skills** | 插件安装 | `~/.claude/plugins/` | 通过插件市场安装 |

## SKILL.md 定义结构

每个 Skill 通过 `SKILL.md` 文件定义元数据，包含以下核心部分：

```markdown
# Python Development Skill

## Summary
帮助开发者高效编写 Python 代码，遵循 PEP 8 规范，包含类型提示和单元测试。

## Triggers
- "写一个 Python 函数"
- "优化这段 Python 代码"
- "生成 Python 类"

## Tools
- Read: 读取现有代码
- WebSearch: 搜索 Python 官方文档
- Write: 创建新文件
- Edit: 修改现有文件
- Bash: 执行 `pip install` 命令
- NotebookEdit: 编辑 Jupyter 笔记本

## Memory
- CLAUDE.md: 获取项目技术栈信息
- .CLAUSE.md: 了解 Python 版本和编码规范

## Prompt
"你是一个 Python 专家，严格遵守 PEP 8 规范，为代码添加类型提示，
每完成一个功能就生成对应的单元测试。"
```

### 各部分说明

| 部分 | 作用 | 是否必须 |
|------|------|----------|
| **Summary** | 技能的简要描述，用于触发匹配 | 是 |
| **Triggers** | 触发关键词列表，匹配用户指令 | 是 |
| **Tools** | 该技能需要使用的工具列表 | 是 |
| **Memory** | 该技能需要读取的记忆文件 | 否 |
| **Prompt** | 执行该技能时注入的系统提示词 | 是 |

## Skill 元数据结构

```typescript
interface SkillMetadata {
  name: string;                              // 技能名称
  description: string;                       // 技能描述
  triggers: string[];                        // 触发关键词
  tools: string[];                           // 所需工具
  memory: string[];                          // 所需记忆文件
  prompt: string;                            // 注入的系统提示词
  version: string;                           // 版本号
  type: 'personal' | 'project' | 'plugin';  // 技能类型
  dependencies: string[];                    // 依赖项
  configurationSchema?: z.ZodType;           // 可选配置 Schema
}
```

## Skill 触发逻辑

基于元数据中的 `name` 和 `description` 字段，由模型自动匹配用户任务：

```typescript
class SkillTrigger {
  async matchSkill(userInput: string): Promise<string | null> {
    // 1. 将用户指令与所有 Skill 的 triggers 进行匹配
    // 2. 使用提示词工程计算相似度
    // 3. 返回最匹配的 Skill 名称
    // 4. 不匹配则返回 null（使用默认行为）
  }
}
```

**触发机制特点：**
- 模型自动匹配，无需用户显式调用
- 支持模糊匹配（语义相似即可触发）
- 多个 Skill 匹配时选择相似度最高的

## Skill 执行流程

```
用户输入指令
  ↓
SkillTrigger.matchSkill()              # 匹配最合适的 Skill
  ↓
┌─ 无匹配 → 使用默认行为
│
└─ 有匹配 → 加载 Skill 元数据
              ↓
         SkillRegistry.loadSkill()     # 加载技能
              ↓
         注册工具、命令、提示词、钩子、MCP 服务
              ↓
         创建 SkillExecutionEnvironment # 环境隔离
              ↓
         执行工具调用链
              ↓
         进度跟踪（TaskBoard）
              ↓
         完成后清理环境
```

### 详细步骤

1. **元数据匹配**：系统根据用户指令与 Skill 描述的相似度自动选择最合适的 Skill
2. **环境创建**：创建独立的执行环境，包含专用环境变量和临时目录
3. **工具调用链**：Skill 通过标准 API 调用内置工具或 MCP 服务
4. **进度跟踪**：执行进度通过 `TaskBoard` 实时更新，主 Agent 可监控和干预
5. **环境清理**：执行完成后自动清理临时文件和环境变量

## Skill 与工具的绑定

Skill 执行时调用内置工具或 MCP 服务完成具体操作：

```typescript
async function executePythonSkill(task: Task) {
  // 1. 读取项目配置
  const config = await readTool.execute({ path: 'CLAUDE.md' });

  // 2. 分析需求
  const requirements = analyzeRequirements(task.description);

  // 3. 搜索官方文档
  const documentation = await webSearchTool.execute({
    query: `Python 官方文档 ${requirements.keywords}`,
    maxResults: 3
  });

  // 4. 使用 Skill 提示词生成代码
  const code = await generateCodeWithPrompt({
    prompt: skillPrompt,
    documentation,
    requirements
  });

  // 5. 根据项目规范格式化代码
  const formattedCode = formatCodeWithSkillConfig(code, config);

  // 6. 写入文件
  const result = await writeTool.execute({
    path: requirements.targetFile,
    content: formattedCode
  });

  return result;
}
```

## 执行环境隔离

```typescript
class SkillExecutionEnvironment {
  // 创建临时目录
  tempDir: string;

  // 设置 Skill 专用环境变量
  env: Record<string, string>;

  // 限制权限（仅允许 Skill 声明的工具）
  permissions: PermissionSet;

  // 完成后清理
  async cleanup(): Promise<void> {
    await fs.rm(this.tempDir, { recursive: true });
    this.env = {};
  }
}
```

**隔离策略：**
- 每次执行创建独立的临时目录
- 环境变量隔离，不污染全局状态
- 权限限制为 Skill 声明的工具子集
- 执行完成后自动清理所有临时资源

## Skill 注册

```typescript
class SkillRegistry {
  private skills: Map<string, SkillMetadata>;

  registerSkill(skill: SkillMetadata): void {
    this.skills.set(skill.name, skill);
  }

  async loadSkill(skillName: string): Promise<void> {
    // 1. 检查依赖项
    const skill = this.skills.get(skillName);
    await this.checkDependencies(skill);

    // 2. 加载 Skill 代码
    const skillCode = await this.loadSkillCode(skill);

    // 3. 注册到系统
    // - 注册工具到工具池
    // - 注册命令到命令系统
    // - 注册提示词到提示词引擎
    // - 注册钩子到钩子系统
    // - 注册 MCP 服务到 MCP 管理器

    // 4. 更新可用工具列表
    this.toolManager.refreshAvailableTools();
  }
}
```

## 效果数据

| 指标 | 提升幅度 | 说明 |
|------|----------|------|
| 任务完成速度 | **+40%** | 标准化流程减少决策开销 |
| 操作错误率 | **-35%** | Skill 定义的最佳实践自动应用 |
| 上下文占用 | **-40% ~ -60%** | Skill 提示词更精炼，减少冗余 token |
| 一致性 | 显著提升 | 同类任务始终遵循相同流程 |

## Skill 与 Plugin 的关系

| 对比项 | Skill | Plugin |
|--------|-------|--------|
| 定义方式 | `SKILL.md` | `plugin.json` |
| 触发方式 | 模型自动匹配 | 手动安装启用 |
| 扩展粒度 | 工作流级（提示词 + 工具组合） | 工具级（新工具注册） |
| 安装方式 | 放入 skills 目录 | 通过市场安装 |
| 安全要求 | 较低（使用已有工具） | 较高（签名验证 + 沙箱） |

> **延伸阅读：**
> - 插件系统详见 [09-插件与Hook系统](09-插件与Hook系统.md)
> - 工具系统详见 [03-工具系统](03-工具系统.md)
> - Skill 的提示词注入到五层系统提示词的 Agent 层，详见 [02-Agent运行时机制](02-Agent运行时机制.md)
