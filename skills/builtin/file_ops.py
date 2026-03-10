# 工具：读写文件，限制只能操作 workspace/ 目录

from pathlib import Path

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"

# 写权限黑名单：这些文件有专用工具，不允许通过 file_write 修改
WRITE_BLACKLIST = {"SOUL.md", "USER.md"}

TOOL_DEFINITIONS = [
    {
        "name": "file_read",
        "description": "读取 workspace/ 目录内指定文件的内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径，相对于 workspace/，例如 SOUL.md"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "file_write",
        "description": "写入内容到 workspace/ 目录内的指定文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径，相对于 workspace/，例如 notes.md"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容（覆盖写）"
                }
            },
            "required": ["path", "content"]
        }
    }
]


def _safe_resolve(relative_path: str) -> Path:
    """解析路径并确认在 workspace/ 内，防止路径穿越攻击"""
    resolved = (WORKSPACE_DIR / relative_path).resolve()
    # resolve() 会展开 ../，再检查是否仍在 workspace 目录下
    if not str(resolved).startswith(str(WORKSPACE_DIR.resolve())):
        raise ValueError(f"路径越界：{relative_path} 不在 workspace/ 内")
    return resolved


async def execute(tool_name: str, args: dict) -> str:
    """根据 tool_name 分发读或写操作"""
    try:
        target = _safe_resolve(args["path"])
    except ValueError as e:
        return f"[错误] {e}"

    if tool_name == "file_read":
        if not target.exists():
            return f"[错误] 文件不存在：{args['path']}"
        return target.read_text()

    if tool_name == "file_write":
        if target.name in WRITE_BLACKLIST:
            return f"[错误] {target.name} 禁止写入"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"])
        return f"已写入：{args['path']}"

    return f"[错误] 未知工具：{tool_name}"
