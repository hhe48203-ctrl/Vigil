# 工具：执行 shell 命令，危险命令需用户审批后才执行

import asyncio
import re

from approval_manager import approval_manager

TOOL_DEFINITION = {
    "name": "shell_exec",
    "description": (
        "在 macOS 上执行 shell 命令并返回 stdout/stderr。"
        "适用场景：运行脚本、安装软件、查系统信息、网络诊断、列目录、搜代码、"
        "查进程端口、执行 git 命令等。危险命令会自动请求用户审批。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令，如 'ls -la', 'python3 script.py', 'curl https://...'"
            }
        },
        "required": ["command"]
    }
}

# 危险命令正则模式，覆盖空格变体和路径前缀绕过
# 使用正则而非字符串匹配，防止 "rm  -rf"（双空格）或 "/usr/bin/sudo" 绕过
_DANGEROUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("rm -rf",     re.compile(r"rm\s+-[^\s]*r[^\s]*f|rm\s+-[^\s]*f[^\s]*r")),
    ("sudo",       re.compile(r"(^|[\s/])sudo(\s|$)")),
    ("mkfs",       re.compile(r"\bmkfs\b")),
    ("dd 写磁盘",   re.compile(r"\bdd\b.*\bif=")),
    ("写入 /dev",  re.compile(r">\s*/dev/")),
    ("远程执行脚本", re.compile(r"(curl|wget).*\|\s*(ba)?sh")),
]


def _detect_dangerous(command: str) -> str | None:
    """返回匹配到的危险模式描述，或 None（命令安全）。"""
    for label, pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return label
    return None


async def execute(args: dict) -> str:
    """执行 shell 命令；危险命令先向用户请求审批，批准后再执行。"""
    command = args["command"]

    danger = _detect_dangerous(command)
    if danger:
        print(f"[shell] 检测到危险命令（{danger}），请求用户审批")
        approved = await approval_manager.request(command)
        if not approved:
            return f"[拒绝] 用户未批准命令（危险类型：{danger}），未执行。"

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()  # 清理子进程资源
        return "[超时] 命令执行超过 30 秒，已终止。"

    output = stdout.decode().strip()
    error = stderr.decode().strip()

    if output and error:
        return f"{output}\n[stderr] {error}"
    return output or error or "(无输出)"
