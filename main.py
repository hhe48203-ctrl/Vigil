# 入口文件：读取配置，启动 Discord bot、Gateway、Heartbeat 三个并发任务

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from config import load_config
from gateway import Gateway
from brain import Brain
from heartbeat import Heartbeat
from channels.discord_channel import DiscordChannel
from skills.loader import load_skills
from skills.mcp_loader import load_mcp_tools, cleanup_mcp
from approval_manager import approval_manager

WORKSPACE_DIR = Path(__file__).parent / "workspace"


async def main():
    """启动所有模块，用 TaskGroup 并发运行"""
    load_dotenv()
    cfg = load_config()

    token = cfg.get("discord_bot_token")
    channel_id = cfg.get("discord_channel_id")
    if not token or not channel_id:
        print("请在 config.yaml 或 .env 中设置 discord_bot_token 和 discord_channel_id")
        print("运行 `uv run python doctor.py` 检查配置")
        sys.exit(1)

    # 加载本地工具和 .md skill 行为指南
    tools, tool_map, skill_docs = load_skills()

    # 加载 MCP 工具（workspace/mcp.json 不存在时自动跳过）
    mcp_tools, mcp_tool_map = await load_mcp_tools(WORKSPACE_DIR / "mcp.json")
    tools = tools + mcp_tools
    tool_map = {**tool_map, **mcp_tool_map}

    # 初始化各模块
    # heartbeat 用独立的 Brain 实例，禁用历史持久化，避免污染主对话历史
    brain = Brain(tools=tools, tool_map=tool_map, skill_docs=skill_docs)
    heartbeat_brain = Brain(tools=tools, tool_map=tool_map, skill_docs=skill_docs, save_history=False)
    discord_channel = DiscordChannel(token=token, channel_id=int(channel_id))
    gateway = Gateway(brain=brain, discord_channel=discord_channel)
    heartbeat = Heartbeat(brain=heartbeat_brain, discord_channel=discord_channel)

    # 注入依赖
    discord_channel.set_gateway(gateway)
    approval_manager.set_send_callback(discord_channel.send_message)

    print("启动 PyAgent...")
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(discord_channel.run())
            tg.create_task(gateway.run())
            tg.create_task(heartbeat.run())
    finally:
        cleanup_mcp()


if __name__ == "__main__":
    asyncio.run(main())
