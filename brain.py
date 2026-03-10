# 核心模块：ReAct 推理循环，组装 prompt、调用 Claude API、执行工具

import json
import os
from pathlib import Path

import anthropic
from memory.vector_store import search_memory


MAX_STEPS = 10
MAX_HISTORY = 20
WORKSPACE_DIR = Path(__file__).parent / "workspace"


class Brain:
    """ReAct 推理引擎，接收消息，返回最终回复文本"""

    def __init__(self, tools: list, tool_map: dict):
        self.client = anthropic.AsyncAnthropic()
        self.tools = tools
        self.tool_map = tool_map
        self.model = "claude-haiku-4-5-20251001"
        # 跨轮次的对话历史，bot 重启后清空
        self.history: list = []

    def _build_system_prompt(self, query: str) -> str:
        """读取 SOUL.md + USER.md + 相关记忆，组装 system prompt"""
        parts = []

        soul_path = WORKSPACE_DIR / "SOUL.md"
        if soul_path.exists():
            parts.append(soul_path.read_text())

        user_path = WORKSPACE_DIR / "USER.md"
        if user_path.exists():
            parts.append(user_path.read_text())

        memories = search_memory(query)
        if memories:
            memory_block = ["# Relevant Memories", ""]
            memory_block.extend(f"- {memory}" for memory in memories)
            parts.append("\n".join(memory_block))

        return "\n\n---\n\n".join(parts)

    async def think(self, user_message: str) -> str:
        """ReAct 循环：调用 Claude API，遇到 tool_use 就执行并继续，遇到文本就返回"""
        system_prompt = self._build_system_prompt(user_message)

        # 在历史记录末尾追加本轮用户消息
        messages = self.history + [{"role": "user", "content": user_message}]

        api_kwargs = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages,
        }
        if self.tools:
            api_kwargs["tools"] = self.tools

        final_text = ""
        for _ in range(MAX_STEPS):
            response = await self.client.messages.create(**api_kwargs)

            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # 没有工具调用 → 保存历史，返回
            if not tool_uses:
                final_text = "\n".join(text_parts)
                messages.append({"role": "assistant", "content": final_text})
                # 只保留最近 20 条消息（工具调用的中间过程不算）
                self.history = messages[-MAX_HISTORY:]
                return final_text

            # 有工具调用 → 执行工具，把结果追加到 messages 继续循环
            # response.content 是 SDK 对象，转成纯 dict 才能被序列化后保存到 history
            messages.append({"role": "assistant", "content": [block.model_dump() for block in response.content]})

            tool_results = []
            for tool_use in tool_uses:
                print(f"[工具] {tool_use.name} {json.dumps(tool_use.input, ensure_ascii=False)}")
                result = await self.tool_map[tool_use.name](tool_use.input)
                print(f"[结果] {str(result)[:200]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                })

            messages.append({"role": "user", "content": tool_results})
            api_kwargs["messages"] = messages

        # 超出最大步数，也保存历史
        self.history = messages[-MAX_HISTORY:]
        return final_text or "（达到最大推理步数，停止）"
