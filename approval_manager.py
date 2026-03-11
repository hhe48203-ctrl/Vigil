# 用户审批中间件：在 shell 技能和 Discord 之间传递危险命令审批结果

import asyncio
from typing import Awaitable, Callable

APPROVAL_TIMEOUT = 60  # 等待用户回复的超时秒数


class ApprovalManager:
    """
    单例中间件，用于危险 shell 命令的用户审批流程。

    工作流程：
      shell.py 检测到危险命令 → request() 挂起等待
      discord_channel.py 收到 yes/no → resolve() 唤醒
      shell.py 得到结果 → 执行或拒绝
    """

    def __init__(self) -> None:
        self._pending_event: asyncio.Event | None = None
        self._result: bool = False
        self._send_callback: Callable[[str], Awaitable[None]] | None = None

    def set_send_callback(self, cb: Callable[[str], Awaitable[None]]) -> None:
        """注入 Discord 发送函数，由 main.py 在启动时调用一次。"""
        self._send_callback = cb

    @property
    def is_pending(self) -> bool:
        """是否有正在等待审批的命令。"""
        return self._pending_event is not None

    async def request(self, command: str) -> bool:
        """
        发送审批请求到 Discord，阻塞等待用户回复。
        返回 True 表示批准，False 表示拒绝或超时。
        """
        self._pending_event = asyncio.Event()
        self._result = False

        if self._send_callback:
            await self._send_callback(
                f"⚠️ **危险命令需要审批**\n"
                f"```\n{command}\n```\n"
                f"回复 `yes` 执行，`no` 拒绝（{APPROVAL_TIMEOUT} 秒后自动取消）"
            )

        try:
            await asyncio.wait_for(self._pending_event.wait(), timeout=APPROVAL_TIMEOUT)
        except asyncio.TimeoutError:
            if self._send_callback:
                await self._send_callback("⏱️ 审批超时，命令已自动取消。")
            self._result = False
        finally:
            self._pending_event = None

        return self._result

    def resolve(self, approved: bool) -> None:
        """
        discord_channel.py 收到用户回复后调用（可在非 async 上下文中调用）。
        approved=True 批准，False 拒绝。
        """
        if self._pending_event is not None:
            self._result = approved
            self._pending_event.set()


# 模块级单例，所有模块统一从这里 import
approval_manager = ApprovalManager()
