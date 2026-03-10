# 工具：执行 shell 命令，返回 stdout + stderr，拒绝危险命令

import asyncio

TOOL_DEFINITION = {
    "name": "shell_exec",
    "description": "执行一条 shell 命令并返回输出",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令"
            }
        },
        "required": ["command"]
    }
}

DANGEROUS_PATTERNS = ["rm -rf", "sudo", "mkfs", "dd if=", "> /dev/"]


async def execute(args: dict) -> str:
    """执行 shell 命令，返回输出结果；危险命令直接拒绝"""
    command = args["command"]

    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            return f"[拒绝] 命令包含危险操作 '{pattern}'，未执行。"

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    output = stdout.decode().strip()
    error = stderr.decode().strip()

    if output and error:
        return f"{output}\n[stderr] {error}"
    return output or error or "(无输出)"
