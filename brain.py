# 核心模块：ReAct 推理循环，组装 prompt、调用 Claude API、执行工具

import base64
import json
import os
from pathlib import Path

import anthropic
from memory.vector_store import search_memory


MAX_STEPS = 10
SUMMARY_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_HISTORY_COMPRESS_THRESHOLD = 40
DEFAULT_HISTORY_KEEP_RECENT = 20
SUMMARY_SYSTEM_PROMPT = (
    "你是对话摘要助手，将以下对话压缩成一段简洁的中文摘要，"
    "保留所有重要信息、决策和事实，去掉闲聊和重复内容。"
)
WORKSPACE_DIR = Path(__file__).parent / "workspace"


class Brain:
    """ReAct 推理引擎，接收消息，返回最终回复文本"""

    def __init__(self, tools: list, tool_map: dict):
        self.client = anthropic.AsyncAnthropic()
        self.tools = tools
        self.tool_map = tool_map
        self.model = "claude-haiku-4-5-20251001"
        self.history_compress_threshold = int(
            os.getenv("HISTORY_COMPRESS_THRESHOLD", str(DEFAULT_HISTORY_COMPRESS_THRESHOLD))
        )
        self.history_keep_recent = int(
            os.getenv("HISTORY_KEEP_RECENT", str(DEFAULT_HISTORY_KEEP_RECENT))
        )
        # 跨轮次的对话历史，bot 重启后清空
        self.history: list = []
        # think() 执行期间收集的截图，调用方读取后应清空
        self.last_images: list[bytes] = []

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

    def _serialize_message_content(self, content) -> str:
        """把历史消息序列化成纯文本，供摘要模型压缩。"""
        if isinstance(content, str):
            return content

        if not isinstance(content, list):
            return str(content)

        parts = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block))
                continue

            block_type = block.get("type")
            if block_type == "text":
                parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_input = json.dumps(block.get("input", {}), ensure_ascii=False)
                parts.append(f"[工具调用] {block.get('name')} {tool_input}")
            elif block_type == "tool_result":
                result_content = block.get("content")
                if isinstance(result_content, str):
                    parts.append(f"[工具结果] {result_content}")
                elif isinstance(result_content, list):
                    result_parts = []
                    for item in result_content:
                        if isinstance(item, dict) and item.get("type") == "image":
                            result_parts.append("[图片结果]")
                        elif isinstance(item, dict) and item.get("type") == "text":
                            result_parts.append(item.get("text", ""))
                        else:
                            result_parts.append(str(item))
                    parts.append(f"[工具结果] {' '.join(result_parts)}")
                else:
                    parts.append(f"[工具结果] {result_content}")
            else:
                parts.append(json.dumps(block, ensure_ascii=False))

        return "\n".join(part for part in parts if part)

    def _serialize_messages_for_summary(self, messages: list) -> str:
        lines = []
        for message in messages:
            role = message.get("role", "unknown")
            content = self._serialize_message_content(message.get("content"))
            lines.append(f"[{role}]\n{content}")
        return "\n\n".join(lines)

    async def _compress_history(self, messages: list) -> list:
        """把较旧的历史压缩成一条摘要，保留最近若干条原始消息。"""
        if len(messages) <= self.history_keep_recent:
            return messages

        old_messages = messages[:-self.history_keep_recent]
        recent_messages = messages[-self.history_keep_recent:]
        summary_input = self._serialize_messages_for_summary(old_messages)

        try:
            response = await self.client.messages.create(
                model=SUMMARY_MODEL,
                max_tokens=512,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": summary_input}],
            )
            summary_text = "\n".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
        except Exception as e:
            print(f"[history] 压缩失败，保留原始历史：{e}")
            return messages

        if not summary_text:
            print("[history] 压缩结果为空，保留原始历史")
            return messages

        print(
            f"[history] 已压缩 {len(old_messages)} 条旧消息，保留最近 {len(recent_messages)} 条"
        )
        return [{"role": "user", "content": f"[之前对话的摘要]\n{summary_text}"}] + recent_messages

    async def think(self, user_message: str) -> str:
        """ReAct 循环：调用 Claude API，遇到 tool_use 就执行并继续，遇到文本就返回"""
        system_prompt = self._build_system_prompt(user_message)
        self.last_images = []

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
                if len(messages) > self.history_compress_threshold:
                    messages = await self._compress_history(messages)
                self.history = messages
                return final_text

            # 有工具调用 → 执行工具，把结果追加到 messages 继续循环
            # response.content 是 SDK 对象，转成纯 dict 才能被序列化后保存到 history
            messages.append({"role": "assistant", "content": [block.model_dump() for block in response.content]})

            tool_results = []
            for tool_use in tool_uses:
                print(f"[工具] {tool_use.name} {json.dumps(tool_use.input, ensure_ascii=False)}")
                result = await self.tool_map[tool_use.name](tool_use.input)

                if isinstance(result, dict) and result.get("type") == "image":
                    print(f"[结果] <image {len(result['data'])} bytes base64>")
                    self.last_images.append(base64.b64decode(result["data"]))
                    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": result["data"]}}]
                else:
                    print(f"[结果] {str(result)[:200]}")
                    content = str(result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": content,
                })

            messages.append({"role": "user", "content": tool_results})
            api_kwargs["messages"] = messages

        # 超出最大步数，也保存历史
        if len(messages) > self.history_compress_threshold:
            messages = await self._compress_history(messages)
        self.history = messages
        return final_text or "（达到最大推理步数，停止）"
