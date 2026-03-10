import os

import httpx


TOOL_DEFINITION = {
    "name": "web_search",
    "description": "使用 Tavily 搜索网页信息并返回结果摘要",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "max_results": {
                "type": "integer",
                "description": "返回结果数量，默认 5",
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
