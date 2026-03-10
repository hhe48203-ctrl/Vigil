# 消息路由中枢：维护消息队列，协调 Discord 和 Brain 之间的通信

import asyncio

from brain import Brain
from channels.discord_channel import DiscordChannel


class Gateway:
    """消息路由，从队列取消息交给 Brain，把回复传回 Discord"""

    def __init__(self, brain: Brain, discord_channel: DiscordChannel):
        self.brain = brain
        self.discord = discord_channel
        self.queue: asyncio.Queue[dict] = asyncio.Queue()

    async def enqueue(self, message: dict) -> None:
        """Discord 收到消息后调用，把消息塞进队列"""
        await self.queue.put(message)

    async def run(self) -> None:
        """主循环：不断从队列取消息，交给 Brain，发送回复"""
        while True:
            message = await self.queue.get()
            print(f"收到消息: {message['author']}: {message['content']}")

            try:
                reply = await self.brain.think(message["content"])
                for img_data in self.brain.last_images:
                    await self.discord.send_image(img_data)
                await self.discord.send_message(reply)
            except Exception as e:
                print(f"处理消息出错: {e}")
                await self.discord.send_message(f"出错了: {e}")
