# Discord 通道：监听消息、过滤 bot 自身消息、发送回复

import io

import discord

from approval_manager import approval_manager


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

            # 优先检查是否有待审批的危险命令
            # 若有，拦截 yes/no 回复并 resolve，不路由到 Gateway
            if approval_manager.is_pending:
                text = message.content.strip().lower()
                if text in ("yes", "y", "是", "确认", "approve"):
                    approval_manager.resolve(True)
                    await message.channel.send("✅ 已批准，执行中...")
                    return
                if text in ("no", "n", "否", "拒绝", "deny"):
                    approval_manager.resolve(False)
                    await message.channel.send("❌ 已拒绝，命令取消。")
                    return
                # 其他内容：提示用户当前处于审批等待状态
                await message.channel.send(
                    "⏳ 正在等待命令审批，请回复 `yes` 或 `no`。"
                )
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

    async def send_image(self, data: bytes, filename: str = "screenshot.png") -> None:
        """发送图片到 Discord 频道"""
        channel = self.client.get_channel(self.channel_id)
        if channel is None:
            print(f"找不到频道 {self.channel_id}")
            return
        await channel.send(file=discord.File(io.BytesIO(data), filename=filename))

    async def run(self) -> None:
        """启动 Discord bot（阻塞式，需要在 TaskGroup 里跑）"""
        await self.client.start(self.token)
