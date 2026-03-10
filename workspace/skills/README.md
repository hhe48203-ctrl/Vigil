TOOL_DEFINITION = {
    "name": "tool_name",
    "description": "这个工具做什么",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "参数说明"}
        },
        "required": ["param"]
    }
}

async def execute(args: dict) -> str:
    # 实现逻辑
    return "结果"