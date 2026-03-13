# MCP 客户端：通过 stdio 连接外部 MCP server，获取工具定义并代理工具调用

import asyncio
import json
import os
from pathlib import Path

# 记录已启动的子进程，程序退出时统一清理
_processes: list[asyncio.subprocess.Process] = []


async def _send_request(
    process: asyncio.subprocess.Process,
    request_id: int,
    method: str,
    params: dict | None = None,
) -> dict:
    """发送一条 JSON-RPC 请求，等待并返回对应的响应结果"""
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params:
        request["params"] = params

    process.stdin.write((json.dumps(request) + "\n").encode())
    await process.stdin.drain()

    # server 有时会主动推送通知消息（无 id），跳过直到找到匹配的响应
    while True:
        raw = await process.stdout.readline()
        if not raw:
            raise RuntimeError("MCP server 意外关闭了连接")
        data = json.loads(raw)
        if data.get("id") == request_id:
            if "error" in data:
                raise RuntimeError(f"MCP 错误: {data['error']}")
            return data.get("result", {})


async def _send_notification(process: asyncio.subprocess.Process, method: str) -> None:
    """发送通知（没有 id，server 不会回复）"""
    notification = {"jsonrpc": "2.0", "method": method}
    process.stdin.write((json.dumps(notification) + "\n").encode())
    await process.stdin.drain()


async def _handshake(process: asyncio.subprocess.Process) -> None:
    """MCP 握手流程：initialize 请求 → initialized 通知"""
    await _send_request(process, 1, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "pyagent", "version": "0.1.0"},
    })
    await _send_notification(process, "notifications/initialized")


def _expand_env(env: dict) -> dict:
    """把 {"KEY": "${VAR}"} 替换为实际的环境变量值"""
    expanded = {}
    for key, value in env.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            expanded[key] = os.getenv(var_name, "")
        else:
            expanded[key] = value
    return expanded


def _to_claude_tool(mcp_tool: dict) -> dict:
    """MCP 工具格式 → Claude API 工具格式（inputSchema → input_schema）"""
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool.get("inputSchema", {"type": "object", "properties": {}}),
    }


def _make_handler(
    process: asyncio.subprocess.Process,
    lock: asyncio.Lock,
    tool_name: str,
    counter: list,
):
    """返回工具调用处理函数；lock 保证同一进程的请求不会并发交错"""
    async def handler(args: dict) -> str:
        async with lock:
            counter[0] += 1
            result = await _send_request(process, counter[0], "tools/call", {
                "name": tool_name,
                "arguments": args,
            })
        # MCP 返回的 content 是 [{type: text, text: ...}] 格式
        texts = [
            block["text"]
            for block in result.get("content", [])
            if block.get("type") == "text"
        ]
        return "\n".join(texts) if texts else str(result)

    return handler


async def load_mcp_tools(config_path: Path) -> tuple[list[dict], dict]:
    """
    读取 mcp.json，启动所有配置的 MCP server 子进程。
    返回 (tools, tool_map)，格式与本地 .py skill 完全一致，可直接合并后传给 Brain。
    """
    if not config_path.exists():
        return [], {}

    config = json.loads(config_path.read_text())
    all_tools: list[dict] = []
    tool_map: dict = {}

    for server in config.get("servers", []):
        server_name = server["name"]
        env = {**os.environ, **_expand_env(server.get("env", {}))}

        try:
            process = await asyncio.create_subprocess_exec(
                server["command"], *server.get("args", []),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            _processes.append(process)

            await _handshake(process)

            # 握手用了 id 1，tools/list 用 id 2，工具调用从 id 3 开始
            result = await _send_request(process, 2, "tools/list")
            mcp_tools = result.get("tools", [])

            lock = asyncio.Lock()
            counter = [2]  # 用列表包装，让闭包可以修改它
            for mcp_tool in mcp_tools:
                all_tools.append(_to_claude_tool(mcp_tool))
                tool_map[mcp_tool["name"]] = _make_handler(process, lock, mcp_tool["name"], counter)

            print(f"[mcp] {server_name}: 已连接，加载 {len(mcp_tools)} 个工具")

        except Exception as e:
            print(f"[mcp] {server_name}: 连接失败 — {e}")

    return all_tools, tool_map


def cleanup_mcp() -> None:
    """终止所有 MCP 子进程（在 main.py 退出时调用）"""
    for process in _processes:
        try:
            process.terminate()
        except Exception:
            pass
    _processes.clear()
