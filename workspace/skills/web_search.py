import os

import httpx


TOOL_DEFINITION = {
    "name": "web_search",
    "description": (
        "搜索互联网，返回相关网页的标题、URL 和内容摘要。"
        "用途：查找最新信息、验证事实、获取技术文档、查新闻时事。"
        "技巧：技术话题用英文关键词效果更好；搜索结果不够详细时可用 browser_goto 访问具体链接。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如 'Python asyncio tutorial' 或 'Edmonton 天气'",
            },
            "max_results": {
                "type": "integer",
                "description": "返回结果数量（1-10），默认 5",
            },
        },
        "required": ["query"],
    },
}


async def execute(args: dict) -> str:
    query = args["query"]
    max_results = args.get("max_results", 5)
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return "搜索失败：未设置 TAVILY_API_KEY"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return f"搜索失败：{e}"

    results = data.get("results", [])
    if not results:
        return "未找到结果"

    lines = []
    for item in results:
        title = item.get("title", "无标题")
        url = item.get("url", "")
        content = item.get("content", "")
        lines.append(f"{title}\n{url}\n{content}")

    return "\n---\n".join(lines)
