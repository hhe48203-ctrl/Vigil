# Discord 通道：监听消息、过滤 bot 自身消息、发送回复

import discord


class DiscordChannel:
    """Discord bot，收发消息，把用户消息丢给 Gateway 的队列"""

    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.gateway = None

        # 只需要读消息内容的权限
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        self._register_events()

    def _register_events(self):
        """注册 Discord 事件回调"""

        @self.client.event
        async def on_ready():
            print(f"Discord bot 已上线: {self.client.user}")

        @self.client.event
        async def on_message(message: discord.Message):
            # 忽略 bot 自己发的消息
            if message.author == self.client.user:
                return
            # 只监听目标频道
            if message.channel.id != self.channel_id:
                return
            if self.gateway is None:
                return

            await self.gateway.enqueue({
                "content": message.content,
                "author": str(message.author),
                "channel_id": message.channel.id,
            })

    def set_gateway(self, gateway) -> None:
        """注入 Gateway 引用（避免循环依赖）"""
        self.gateway = gateway

    async def send_message(self, text: str) -> None:
        """发送消息到 Discord 频道，超过 2000 字符自动分段"""
        channel = self.client.get_channel(self.channel_id)
        if channel is None:
            print(f"找不到频道 {self.channel_id}")
            return

        # Discord 单条消息上限 2000 字符
        while text:
            chunk, text = text[:2000], text[2000:]
            await channel.send(chunk)

    async def run(self) -> None:
        """启动 Discord bot（阻塞式，需要在 TaskGroup 里跑）"""
        await self.client.start(self.token)
