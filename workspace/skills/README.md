# workspace/skills/ 使用说明

在这里放自定义的 tool 或 skill，agent 启动时自动加载。

---

## Tool 模板（.py 文件）

> **Tool = 可执行代码**，Claude 可以主动调用，会真正运行 Python 函数。

新建 `my_tool.py`：

```python
# 一行中文注释说明这个文件的用途

TOOL_DEFINITION = {
    "name": "my_tool",
    "description": "这个工具做什么（Claude 看到这段描述来决定何时调用）",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "参数说明"}
        },
        "required": ["param"]
    }
}

async def execute(args: dict) -> str:
    param = args["param"]
    # 实现逻辑
    return "结果"
```

**同名 tool 会覆盖 `skills/builtin/` 中的内置版本。**

---

## Skill 模板（.md 文件）

> **Skill = 行为指南**，不执行代码，内容注入 system prompt，告诉 Claude 某方面的行为规范。

新建 `my_skill.md`：

```markdown
---
name: my_skill
description: 这个 skill 的简短说明
---

## 行为规范标题

- 具体规则 1
- 具体规则 2
- ...
```

**必须有 `---` frontmatter，否则文件会被跳过（README.md 等说明文档不会被误加载）。**
