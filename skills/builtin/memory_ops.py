# 工具：追加写入每日记忆文件 workspace/memory/YYYY-MM-DD.md
# 工具：覆写用户档案 workspace/USER.md 和 SOUL.md

from datetime import date, datetime
from pathlib import Path

from memory.vector_store import add_memory

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"
MEMORY_DIR = WORKSPACE_DIR / "memory"

TOOL_DEFINITIONS = [
    {
        "name": "memory_append",
        "description": "把重要信息追加写入今天的记忆日志，下次启动时会自动读取",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要记录的内容，一句话简洁描述"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "user_profile_update",
        "description": "覆写整个用户档案 USER.md，用于更新用户的基本信息、偏好、项目等",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "完整的 USER.md 内容（Markdown 格式）"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "soul_update",
        "description": (
            "覆写 SOUL.md（agent 的灵魂文件）。"
            "仅在以下情况调用：用户给 agent 起名、用户明确要求切换性格或风格、用户对 agent 提出新的长期行为要求。"
            "日常对话、完成任务、回答问题时不得调用。修改时保持文件结构不变，只修改相关字段。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "完整的 SOUL.md 内容（Markdown 格式）"
                }
            },
            "required": ["content"]
        }
    }
]


async def execute(tool_name: str, args: dict) -> str:
    """根据 tool_name 分发 memory_append 或 user_profile_update"""
    if tool_name == "memory_append":
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        memory_file = MEMORY_DIR / f"{today}.md"

        if not memory_file.exists():
            memory_file.write_text(f"# {today}\n\n")

        time_str = datetime.now().strftime("%H:%M")
        with memory_file.open("a") as f:
            f.write(f"- {time_str} {args['content']}\n")
        add_memory(args["content"], today)

        return f"已记录：{args['content']}"

    if tool_name == "user_profile_update":
        user_file = WORKSPACE_DIR / "USER.md"
        user_file.write_text(args["content"])
        return "已更新用户档案"

    if tool_name == "soul_update":
        soul_file = WORKSPACE_DIR / "SOUL.md"
        soul_file.write_text(args["content"])
        return "已更新 SOUL.md"

    return f"[错误] 未知工具：{tool_name}"
