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
        "description": (
            "将重要信息写入长期记忆（向量数据库 + 日志文件），未来对话会自动检索相关记忆。"
            "仅在以下情况调用：用户明确要求记住某事、完成重要多步骤任务、发现用户长期目标或偏好。"
            "日常闲聊和一次性问答不要调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要记录的内容，一句话简洁描述关键信息，如 '用户的毕业论文题目是《分布式系统中的一致性》'"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "user_profile_update",
        "description": (
            "覆写用户档案 USER.md。当用户透露个人信息（姓名、职业、所在地）、"
            "表达偏好（语言、风格）或提到新项目/目标时调用。"
            "调用前应先了解当前 USER.md 内容（已在 system prompt 中），在现有内容基础上修改。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "完整的 USER.md 内容（Markdown 格式），保持原有结构，只更新变化的字段"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "soul_update",
        "description": (
            "覆写 SOUL.md（agent 的人格与行为规则文件）。"
            "仅在以下情况调用：用户给 agent 起名、用户明确要求切换性格或风格、用户对 agent 提出新的长期行为要求。"
            "日常对话、完成任务、回答问题时绝不调用。修改时保持文件结构不变，只修改相关字段，不得删除已有规则。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "完整的 SOUL.md 内容（Markdown 格式），保持结构不变，只修改相关字段"
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
