# 心跳模块：定时触发 Brain 执行检查任务，有异常时通知用户

import asyncio
import os
from pathlib import Path

from brain import Brain
from channels.discord_channel import DiscordChannel


WORKSPACE_DIR = Path(__file__).parent / "workspace"
DEFAULT_INTERVAL = 1800  # 30 分钟


class Heartbeat:
    """定时心跳，每 N 秒读取 HEARTBEAT.md 触发 Brain 检查"""

    def __init__(self, brain: Brain, discord_channel: DiscordChannel):
        self.brain = brain
        self.discord = discord_channel
        # 从环境变量读取间隔，缺省 1800 秒
        self.interval = int(os.getenv("HEARTBEAT_INTERVAL", DEFAULT_INTERVAL))

    def _load_heartbeat_prompt(self) -> str:
        """每次触发时重新读文件，支持运行时修改 HEARTBEAT.md"""
        path = WORKSPACE_DIR / "HEARTBEAT.md"
        if path.exists():
            return path.read_text()
        return "检查系统状态，如果一切正常回复 HEARTBEAT_OK"

    async def run(self) -> None:
        """主循环：等待 N 秒 → 触发 Brain → 判断是否需要通知"""
        print(f"心跳已启动，间隔 {self.interval} 秒")
        while True:
            await asyncio.sleep(self.interval)

            prompt = self._load_heartbeat_prompt()
            try:
                reply = await self.brain.think(prompt)
                # 不区分大小写，去除首尾空格后判断
                if reply.strip().upper() == "HEARTBEAT_OK":
                    print("心跳正常")
                else:
                    await self.discord.send_message(f"[心跳] {reply}")
            except Exception as e:
                print(f"心跳出错: {e}")
