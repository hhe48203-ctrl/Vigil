# Vigil

[English](README.md)

一个基于 Claude 的个人 Discord AI 助手。它通过 ReAct 循环进行推理，使用工具操作文件系统和终端，并通过语义搜索构建长期记忆。

灵感来自 [OpenClaw](https://github.com/OpenClaw) —— 这是一个 Python 重实现版本，目的是从头理解其核心架构。

---

## 功能特性

- **ReAct 推理循环** —— Claude 逐步思考，按需调用工具，再给出最终回复
- **语义记忆** —— 重要事件存入 ChromaDB；每次对话时通过向量搜索检索最相关的记忆
- **持久身份** —— `SOUL.md` 定义 Agent 的人格与规则；`USER.md` 存储 Agent 对你的了解；两者都会由 Agent 随时间更新
- **可扩展的 skill 系统** —— 内置工具（文件操作、终端、记忆）加上 `workspace/skills/` 中的用户自定义 tool 和 skill，启动时动态加载
- **危险命令审批** —— 终端命令匹配到高风险模式（如 `rm -rf`、`sudo`、`dd`）时，会暂停并通过 Discord 等待你明确确认后再执行
- **历史压缩** —— 对话历史过长时，自动将旧消息摘要压缩，保持在上下文限制内
- **心跳任务** —— 每 30 分钟根据 `HEARTBEAT.md` 自主执行一次检查，只有发现异常才会通知你
- **Discord 接口** —— 在指定的单个频道中收发消息

## 架构

```
main.py              — 并发启动 Discord、Gateway 和 Heartbeat
brain.py             — ReAct 循环：构建系统提示、调用 Claude API、分发工具
gateway.py           — Discord 与 Brain 之间的异步消息队列
heartbeat.py         — 定时自主任务执行器
approval_manager.py  — 危险命令审批中间件（请求 → Discord → 解决）
channels/            — Discord 机器人（收发消息、处理审批）
skills/
  loader.py          — 动态加载 tool（.py）和 skill（.md）
  builtin/           — 核心工具：file_ops、shell、memory_ops
memory/              — ChromaDB 向量存储封装
workspace/
  SOUL.md            — Agent 人格与规则
  USER.md            — 用户画像（由 Agent 持续更新）
  HEARTBEAT.md       — 自主检查任务的提示词
  memory/            — 每日记忆日志（.md 文件）+ ChromaDB 向量索引
  skills/            — 用户自定义 tool（.py）和 skill（.md）
```

### 记忆系统

每次调用 `brain.think()` 时，系统提示都会实时重新构建：

```
当前时间
SOUL.md            （完整内容，每次都包含）
USER.md            （完整内容，每次都包含）
Skill 文档          （workspace/skills/ 下所有 .md skill，每次都包含）
相关记忆            （ChromaDB 语义搜索，返回最相关的 8 条）
```

当 Agent 调用 `memory_append` 时，内容会同时写入：
- 纯文本每日日志 `workspace/memory/YYYY-MM-DD.md`（人类可读的原始记录）
- ChromaDB 向量存储（用于检索）

### Skill 系统

`workspace/skills/` 支持两种文件类型：

- **`.py` 文件（Tool，工具）** —— 暴露 `TOOL_DEFINITION` 字典和 `async execute()` 函数。注册为 Claude API 工具，Claude 可以调用它们执行代码。同名 workspace tool 会覆盖内置版本。
- **`.md` 文件（Skill，行为指南）** —— 需要 `---` YAML frontmatter。内容注入 system prompt 作为行为指南，不执行代码。适合定义回复风格、领域知识或约束条件，无需编写 Python。

### 危险命令审批

当终端工具检测到命令中存在高风险模式时，会暂停执行并向 Discord 发送审批请求。Agent 等待最多 60 秒，等你回复 `yes` 或 `no`。若无回复，命令自动拒绝。

### 历史压缩

当对话历史超过 `HISTORY_COMPRESS_THRESHOLD` 条消息时，`brain.py` 会用 `claude-haiku` 将较旧的部分摘要压缩，只保留最近 `HISTORY_KEEP_RECENT` 条消息不变。

## 安装与配置

**1. 克隆并安装依赖**

```bash
git clone <repo-url>
cd pyagent
uv sync
```

**2. 配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env` 填入你的密钥：

```
ANTHROPIC_API_KEY=sk-ant-...
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...

# 可选 —— 括号内为默认值
HEARTBEAT_INTERVAL=1800          # 心跳任务间隔（秒）
HISTORY_COMPRESS_THRESHOLD=40    # 触发压缩的消息数阈值
HISTORY_KEEP_RECENT=20           # 压缩后保留的最近消息数
TAVILY_API_KEY=...               # 仅在使用 web_search 工具时需要
```

**3. 配置工作区文件**

```bash
cp workspace/SOUL.md.example workspace/SOUL.md
cp workspace/USER.md.example workspace/USER.md
```

编辑 `workspace/SOUL.md`，为你的 Agent 设定名字和人格。
编辑 `workspace/USER.md`，告诉 Agent 你是谁（也可以留空，让 Agent 随时间自己填写）。
编辑 `workspace/HEARTBEAT.md`，定义 Agent 定期应该检查什么。

**4. 启动**

```bash
uv run python main.py
```

## 系统要求

- Python 3.12+
- [Anthropic API 密钥](https://console.anthropic.com)
- 开启了消息内容意图（Message Content Intent）的 Discord 机器人令牌（[配置指南](https://discord.com/developers/docs/intro)）

## 管理记忆

```bash
# 列出所有存储的记忆
uv run python manage_memory.py list

# 语义搜索记忆
uv run python manage_memory.py search "你的查询词"

# 按索引删除特定记忆（先用 list 查找索引）
uv run python manage_memory.py delete <index>

# 清空向量存储中的所有记忆
uv run python manage_memory.py clear
```

原始的 `.md` 记忆日志存放在 `workspace/memory/`，不被 git 追踪。

## 添加自定义 Tool 和 Skill

在 `workspace/skills/` 中放置文件，下次启动时自动加载。

**Tool**（`.py`）—— 需要执行代码的能力：

```python
# 一行中文注释说明用途

TOOL_DEFINITION = {
    "name": "my_tool",
    "description": "工具描述（Claude 根据这段话决定何时调用）",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "参数说明"}
        },
        "required": ["param"]
    }
}

async def execute(args: dict) -> str:
    return "结果"
```

**Skill**（`.md`）—— 注入 system prompt 的行为指南：

```markdown
---
name: my_skill
description: 简短说明
---

## 规则

- 规则 1
- 规则 2
```

> 没有 `---` frontmatter 的 `.md` 文件会被跳过（`README.md` 不会被误加载）。

若工具名与内置工具相同，workspace 版本优先生效。
