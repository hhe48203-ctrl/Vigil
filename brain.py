# 核心模块：ReAct 推理循环，组装 prompt、调用 Claude API、执行工具

import base64
import json
import os
from datetime import datetime
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

    def __init__(self, tools: list, tool_map: dict, skill_docs: list | None = None,
                 history_file: Path | None = None, save_history: bool = True):
        self.client = anthropic.AsyncAnthropic()
        self.tools = tools
        self.tool_map = tool_map
        self.skill_docs = skill_docs or []
        self.model = "claude-haiku-4-5-20251001"
        self.save_history_enabled = save_history
        self.history_compress_threshold = int(
            os.getenv("HISTORY_COMPRESS_THRESHOLD", str(DEFAULT_HISTORY_COMPRESS_THRESHOLD))
        )
        self.history_keep_recent = int(
            os.getenv("HISTORY_KEEP_RECENT", str(DEFAULT_HISTORY_KEEP_RECENT))
        )
        self.history_file = history_file or (WORKSPACE_DIR / "memory" / "conversation_history.json")
        if self.save_history_enabled and self.history_file.exists():
            self.history = self._normalize_history(json.loads(self.history_file.read_text()))
            self._save_history(self.history)
            print(f"[brain] 已加载历史对话，共 {len(self.history)} 条")
        else:
            self.history = []
        # think() 执行期间收集的截图，调用方读取后应清空
        self.last_images: list[bytes] = []

    def _build_system_prompt(self, query: str) -> str:
        """读取 SOUL.md + USER.md + 相关记忆，组装 system prompt"""
        parts = []

        # 当前时间放在最前面，让 LLM 准确感知时间，避免幻觉日期
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        time_block = (
            f"# Current Time\n"
            f"现在是 {now.strftime('%Y-%m-%d')} {weekdays[now.weekday()]} "
            f"{now.strftime('%H:%M:%S')}（本机时间）"
        )
        parts.append(time_block)

        soul_path = WORKSPACE_DIR / "SOUL.md"
        if soul_path.exists():
            parts.append(soul_path.read_text())

        user_path = WORKSPACE_DIR / "USER.md"
        if user_path.exists():
            parts.append(user_path.read_text())

        # 注入 .md skill 行为指南
        for skill in self.skill_docs:
            header = f"# Skill: {skill['name']}"
            if skill.get("description"):
                header += f"\n_{skill['description']}_"
            parts.append(f"{header}\n\n{skill['content']}")

        # 可用工具概览，帮助 LLM 快速了解自己的能力边界
        if self.tools:
            tool_names = [t["name"] for t in self.tools]
            tool_overview = (
                "# Available Tools\n"
                f"你可以调用以下工具：{', '.join(tool_names)}\n"
                "根据用户请求选择合适的工具。可以连续调用多个工具完成复杂任务。"
                "如果不确定用哪个工具，参考 SOUL.md 中的工具选择决策树。"
            )
            parts.append(tool_overview)

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

    def _is_turn_start_message(self, message: dict) -> bool:
        """只有普通 user 文本消息才算一轮对话的安全起点。"""
        return message.get("role") == "user" and isinstance(message.get("content"), str)

    def _has_tool_result(self, message: dict) -> bool:
        """检查消息是否包含 tool_result 块。"""
        content = message.get("content")
        if not isinstance(content, list):
            return False
        return any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        )

    def _get_tool_use_ids(self, message: dict) -> set[str]:
        """从 assistant 消息中提取所有 tool_use id。"""
        content = message.get("content")
        if not isinstance(content, list):
            return set()
        return {
            block.get("id") for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id")
        }

    def _normalize_history(self, messages: list) -> list:
        """全量清洗历史，移除所有孤立的 tool_result/tool_use 消息对。"""
        if not messages:
            return []

        original_len = len(messages)
        cleaned = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if self._has_tool_result(msg):
                if not cleaned or cleaned[-1].get("role") != "assistant" or not self._get_tool_use_ids(cleaned[-1]):
                    print(f"[brain] 丢弃孤立的 tool_result 消息（index {i}）")
                    i += 1
                    continue

            if msg.get("role") == "assistant" and self._get_tool_use_ids(msg):
                if i + 1 >= len(messages) or not self._has_tool_result(messages[i + 1]):
                    print(f"[brain] 丢弃没有 tool_result 跟随的 tool_use 消息（index {i}）")
                    i += 1
                    continue

            cleaned.append(msg)
            i += 1

        if len(cleaned) < original_len:
            print(f"[brain] 历史清洗：{original_len} → {len(cleaned)} 条")

        return cleaned

    def _serialize_messages(self, messages: list) -> list:
        """把消息内容转成可写入 JSON 的普通 dict/list。"""
        result = []
        for msg in messages:
            if isinstance(msg["content"], list):
                content = []
                for block in msg["content"]:
                    if hasattr(block, "model_dump"):
                        content.append(block.model_dump())
                    else:
                        content.append(block)
                result.append({"role": msg["role"], "content": content})
            else:
                result.append(msg)
        return result

    def _save_history(self, messages: list) -> None:
        """更新内存中的 history，并持久化到磁盘。"""
        self.history = messages
        if not self.save_history_enabled:
            return
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(
            json.dumps(self._serialize_messages(self.history), ensure_ascii=False, indent=2)
        )

    async def _compress_history(self, messages: list) -> list:
        """把较旧的历史压缩成一条摘要，保留最近若干条原始消息。"""
        if len(messages) <= self.history_keep_recent:
            return messages

        split_idx = len(messages) - self.history_keep_recent
        while split_idx > 0 and not self._is_turn_start_message(messages[split_idx]):
            split_idx -= 1

        if split_idx == 0:
            print("[history] 未找到安全切分点，跳过压缩")
            return messages

        old_messages = messages[:split_idx]
        recent_messages = messages[split_idx:]
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
        return self._normalize_history(
            [
                {"role": "user", "content": f"[之前对话的摘要]\n{summary_text}"},
                # 插入 assistant 桥接消息，避免摘要（user）和
                # recent_messages 第一条（也是 user）形成连续 user 序列，
                # 连续 user 消息会被 Claude API 以 400 错误拒绝。
                {"role": "assistant", "content": "收到，我已了解之前的对话上下文。"},
            ] + recent_messages
        )

    async def think(self, user_message: str) -> str:
        """ReAct 循环：调用 Claude API，遇到 tool_use 就执行并继续，遇到文本就返回"""
        system_prompt = self._build_system_prompt(user_message)
        self.last_images = []

        # 在历史记录末尾追加本轮用户消息
        messages = self.history + [{"role": "user", "content": user_message}]

        api_kwargs = {
            "model": self.model,
            "max_tokens": 4096,
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
                self._save_history(messages)
                return final_text

            # 有工具调用 → 执行工具，把结果追加到 messages 继续循环
            # response.content 是 SDK 对象，转成纯 dict 才能被序列化后保存到 history
            messages.append({"role": "assistant", "content": [block.model_dump() for block in response.content]})

            tool_results = []
            for tool_use in tool_uses:
                print(f"[工具] {tool_use.name} {json.dumps(tool_use.input, ensure_ascii=False)}")
                
                handler = self.tool_map.get(tool_use.name)
                if handler is None:
                    result = f"[错误] 未知工具：{tool_use.name}"
                else:
                    result = await handler(tool_use.input)

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

        # 超出最大步数：此时 messages 末尾是 user（tool_results），
        # 如果直接保存，下次用户发消息时会出现两条连续 user，导致 API 400。
        # 解决方案：禁用工具再调用一次 API，强制 LLM 生成纯文字总结，
        # 确保历史末尾始终是 assistant 消息。
        print("[brain] 达到最大推理步数，请求 LLM 生成最终总结")
        try:
            final_kwargs = {
                "model": self.model,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": messages + [{
                    "role": "user",
                    "content": "（已达到最大推理步数，请根据目前的工具执行结果，给出简洁的最终回复。）"
                }],
            }
            # 不传 tools，强制 LLM 只生成文字，不再调用工具
            summary_response = await self.client.messages.create(**final_kwargs)
            final_text = "\n".join(
                block.text for block in summary_response.content if block.type == "text"
            ).strip() or "（达到最大推理步数，停止）"
            # 把这条强制总结追加进历史，使历史末尾为 assistant
            messages.append({"role": "assistant", "content": final_text})
        except Exception as e:
            print(f"[brain] 最终总结请求失败：{e}")
            # 兜底：追加硬编码的 assistant 消息，保证历史结构合法
            final_text = "（达到最大推理步数，停止）"
            messages.append({"role": "assistant", "content": final_text})

        if len(messages) > self.history_compress_threshold:
            messages = await self._compress_history(messages)
        self._save_history(messages)
        return final_text

