---
name: skill-creator
description: 为 pyagent 创建新的 tool 或 skill 文件。当用户说"帮我写一个工具"、"创建一个 skill"、"我想让你学会做 X"、"添加一个能力"，或者想扩展 agent 功能时，使用这个 skill。
---

# Skill Creator

为 pyagent 创建新的 `.py` tool 或 `.md` skill。

## 第一步：明确类型

先判断用户想要的是哪种类型：

| 需要执行代码？ | 类型 | 文件格式 |
|---|---|---|
| 是（调用 API、操作文件、运行命令等） | **Tool** | `.py` |
| 否（告诉 Claude 某方面如何行动） | **Skill** | `.md` |

不确定时问用户。如果用户描述的是"让你学会做 X"但 X 需要实际运行代码，就选 Tool。

---

## 创建 `.py` Tool

Tool 放在 `workspace/skills/` 目录下，agent 启动时自动加载。

### 模板

```python
# 一行中文注释说明这个文件的用途

TOOL_DEFINITION = {
    "name": "tool_name",           # 唯一标识，Claude 调用时用这个名字
    "description": "工具描述，Claude 根据这段话决定何时调用",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {
                "type": "string",
                "description": "参数说明"
            }
        },
        "required": ["param"]
    }
}

async def execute(args: dict) -> str:
    param = args["param"]
    # 实现逻辑
    return "结果字符串"
```

### 规则

- 文件顶部一行中文注释说明用途
- 函数名必须是 `execute`，接收 `args: dict`，返回字符串
- 用 `async/await`，不用线程
- 函数体不超过 40 行，否则拆分
- 注释用中文，变量名用英文
- 不引入新的第三方库，除非先征得用户同意
- 同名 tool 会覆盖 `skills/builtin/` 中的内置版本

### 多工具文件（可选）

一个 `.py` 文件可以暴露多个工具：

```python
TOOL_DEFINITIONS = [
    {"name": "tool_a", "description": "...", "input_schema": {...}},
    {"name": "tool_b", "description": "...", "input_schema": {...}},
]

async def execute(name: str, args: dict) -> str:
    if name == "tool_a":
        ...
    elif name == "tool_b":
        ...
```

---

## 创建 `.md` Skill

Skill 放在 `workspace/skills/` 目录下，内容注入 system prompt，告诉 Claude 某方面的行为规范。

### 模板

```markdown
---
name: skill_name
description: 这个 skill 的一句话说明（出现在加载日志里）
---

## 标题

- 规则 1
- 规则 2
- ...
```

### 规则

- **必须有 `---` frontmatter**，否则文件被跳过（不会被加载）
- `name` 用于日志标识，`description` 是可选说明
- 正文写给 Claude 看：清晰、简洁、用祈使句
- 适合写：行为指南、回复风格、特定领域知识、约束条件

---

## 第二步：写文件

确认类型后，直接在 `workspace/skills/` 下创建文件：

- Tool：`workspace/skills/<name>.py`
- Skill：`workspace/skills/<name>.md`

写完后告诉用户：
1. 创建了什么文件，路径是什么
2. 下次启动 `uv run python main.py` 时会自动加载
3. 如果是 Tool，说明 Claude 会在什么情况下调用它
4. 如果是 Skill，说明它会如何影响 Claude 的行为

---

## 验证方式

- **Tool**：重启 agent 后，在 Discord 中描述需要该工具的任务，观察 Claude 是否自动调用
- **Skill**：重启后，询问相关话题，看 Claude 的回复是否符合 skill 中定义的行为
- **加载日志**：启动时终端会打印 `已加载 N 个工具` 和 `已加载 N 个 .md skill`，确认文件被识别

---

## 修改已有 Tool/Skill

直接编辑 `workspace/skills/` 下对应文件，重启 agent 即可生效。同名 Tool 会覆盖内置版本。
