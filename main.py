# 入口文件：读取配置，启动 Discord bot、Gateway、Heartbeat 三个并发任务

import asyncio
import os
import sys

from dotenv import load_dotenv

from gateway import Gateway
from brain import Brain
from heartbeat import Heartbeat
from channels.discord_channel import DiscordChannel
from skills.loader import load_skills


async def main():
    """启动所有模块，用 TaskGroup 并发运行"""
    load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        print("请在 .env 中设置 DISCORD_BOT_TOKEN 和 DISCORD_CHANNEL_ID")
        sys.exit(1)

    # 加载工具（Week 1 暂时为空列表也能跑）
    tools, tool_map = load_skills()

    # 初始化各模块
    # heartbeat 用独立的 Brain 实例，避免和用户对话共享 history 导致 tool_use 消息错位
    brain = Brain(tools=tools, tool_map=tool_map)
    heartbeat_brain = Brain(tools=tools, tool_map=tool_map)
    discord_channel = DiscordChannel(token=token, channel_id=int(channel_id))
    gateway = Gateway(brain=brain, discord_channel=discord_channel)
    heartbeat = Heartbeat(brain=heartbeat_brain, discord_channel=discord_channel)

    # 注入依赖
    discord_channel.set_gateway(gateway)

    print("启动 PyAgent...")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(discord_channel.run())
        tg.create_task(gateway.run())
        tg.create_task(heartbeat.run())


if __name__ == "__main__":
    asyncio.run(main())
