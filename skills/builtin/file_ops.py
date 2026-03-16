# 工具：读写本地文件系统，与 shell_exec 的路径视角保持一致

from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent.resolve()
WORKSPACE_DIR = PROJECT_DIR / "workspace"

# 写权限黑名单：这些文件有专用工具，不允许通过 file_write 修改
WRITE_BLACKLIST = {
    (WORKSPACE_DIR / "SOUL.md").resolve(),
    (WORKSPACE_DIR / "USER.md").resolve(),
}

TOOL_DEFINITIONS = [
    {
        "name": "file_read",
        "description": (
            "读取本地文件的完整内容并返回。支持绝对路径、相对路径和 ~/。"
            "用途：查看配置文件、代码文件、日志、文档等。"
            "修改文件前必须先 file_read 获取当前内容。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径，如 '/Users/aa/Desktop/test.py'、'workspace/SOUL.md'、'~/notes.txt'"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "file_write",
        "description": (
            "创建或覆写本地文件。支持绝对路径、相对路径和 ~/。"
            "用途：创建新文件、保存代码、写入配置。"
            "注意：这是覆盖写入，修改已有文件时请先 file_read 读取内容再修改后写回。"
            "SOUL.md 和 USER.md 有专用工具，不能用此工具修改。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径，如 '/Users/aa/Desktop/test.py'、'workspace/notes.md'"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的完整内容（会覆盖文件原有内容）"
                }
            },
            "required": ["path", "content"]
        }
    }
]


def _resolve_path(raw_path: str) -> Path:
    """解析本地路径：支持绝对路径、相对当前工作目录和 ~。"""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()

    return path


def _is_protected_file(target: Path) -> bool:
    """SOUL.md 和 USER.md 只能通过专用工具修改。"""
    try:
        return target.resolve() in WRITE_BLACKLIST
    except FileNotFoundError:
        return target in WRITE_BLACKLIST


async def execute(tool_name: str, args: dict) -> str:
    """根据 tool_name 分发本地文件读写操作"""
    try:
        target = _resolve_path(args["path"])
    except Exception as e:
        return f"[错误] 路径解析失败：{e}"

    if tool_name == "file_read":
        if not target.exists():
            return f"[错误] 文件不存在：{args['path']}"
        if target.is_dir():
            return f"[错误] 目标是目录，不是文件：{args['path']}"
        return target.read_text()

    if tool_name == "file_write":
        if _is_protected_file(target):
            return f"[错误] {target.name} 禁止写入，请使用专用工具"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"])
        return f"已写入：{str(target)}"

    return f"[错误] 未知工具：{tool_name}"
