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
        "description": "读取本地文件系统中的指定文件内容，支持绝对路径、相对路径和 ~",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径。可用绝对路径、相对当前工作目录的路径，或 ~/Desktop/a.txt 这类路径"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "file_write",
        "description": "写入内容到本地文件系统中的指定文件，支持绝对路径、相对路径和 ~",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径。可用绝对路径、相对当前工作目录的路径，或 ~/Desktop/a.txt 这类路径"
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
