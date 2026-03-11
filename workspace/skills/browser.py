import base64
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

WORKSPACE_DIR = Path(__file__).resolve().parent.parent

# --- 全局持久化实例 ---
_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None


async def _get_page() -> Page:
    global _playwright, _browser, _context, _page

    if _page is None or _page.is_closed():
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=False)
        _context = await _browser.new_context()
        _page = await _context.new_page()

    return _page


# --- 工具实现 ---

async def _goto(args: dict) -> str:
    try:
        page = await _get_page()
        await page.goto(args["url"], wait_until="domcontentloaded")
        return f"已导航到 {args['url']}"
    except Exception as e:
        return f"操作失败：{e}"


async def _screenshot(args: dict) -> str:
    try:
        page = await _get_page()
        data = await page.screenshot(type="png")
        return {"type": "image", "data": base64.b64encode(data).decode()}
    except Exception as e:
        return f"操作失败：{e}"


async def _click(args: dict) -> str:
    try:
        page = await _get_page()
        await page.wait_for_selector(args["selector"])
        await page.click(args["selector"])
        return f"已点击 {args['selector']}"
    except Exception as e:
        return f"操作失败：{e}"


async def _type(args: dict) -> str:
    try:
        page = await _get_page()
        await page.wait_for_selector(args["selector"])
        await page.fill(args["selector"], args["text"])
        return f"已输入文字到 {args['selector']}"
    except Exception as e:
        return f"操作失败：{e}"


async def _get_text(args: dict) -> str:
    try:
        page = await _get_page()
        elements = await page.query_selector_all(args["selector"])
        if not elements:
            return "未找到匹配元素"
        texts = []
        for el in elements:
            t = await el.inner_text()
            if t.strip():
                texts.append(t.strip())
        return "\n".join(texts) if texts else "元素存在但无文字内容"
    except Exception as e:
        return f"操作失败：{e}"


async def _get_all_text(args: dict) -> str:
    try:
        page = await _get_page()
        limit = args.get("limit", 10)
        elements = await page.query_selector_all(args["selector"])
        if not elements:
            return "未找到匹配元素"
        texts = []
        for el in elements[:limit]:
            t = await el.inner_text()
            if t.strip():
                texts.append(t.strip())
        return "\n".join(texts) if texts else "元素存在但无文字内容"
    except Exception as e:
        return f"操作失败：{e}"


async def _wait(args: dict) -> str:
    try:
        page = await _get_page()
        timeout = args.get("timeout", 5000)
        await page.wait_for_selector(args["selector"], timeout=timeout)
        return f"元素已出现：{args['selector']}"
    except Exception as e:
        return f"操作失败：{e}"


async def _close(args: dict) -> str:
    global _playwright, _browser, _context, _page
    try:
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
        return "浏览器已关闭"
    except Exception as e:
        return f"操作失败：{e}"
    finally:
        _playwright = None
        _browser = None
        _context = None
        _page = None


# --- 分发表 ---

_HANDLERS = {
    "browser_goto": _goto,
    "browser_screenshot": _screenshot,
    "browser_click": _click,
    "browser_type": _type,
    "browser_get_text": _get_text,
    "browser_get_all_text": _get_all_text,
    "browser_wait": _wait,
    "browser_close": _close,
}

TOOL_DEFINITIONS = [
    {
        "name": "browser_goto",
        "description": "导航到指定网址",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要访问的网址，包含 http:// 或 https://"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_screenshot",
        "description": "截取当前页面截图，返回 base64 编码的 PNG 图片，供视觉分析使用",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "browser_click",
        "description": "点击页面上的指定元素，会等待元素出现后再点击",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器或文本选择器，例如 'button#submit' 或 'text=登录'"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_type",
        "description": "清空指定输入框后输入文字",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "输入框的 CSS 选择器"},
                "text": {"type": "string", "description": "要输入的文字"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "browser_get_text",
        "description": "获取页面上所有匹配元素的文字内容，每条一行",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "目标元素的 CSS 选择器"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_get_all_text",
        "description": "批量获取匹配元素的文字，可限制返回数量，适合读取列表类内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "目标元素的 CSS 选择器"},
                "limit": {"type": "integer", "description": "最多返回几条，默认 10"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_wait",
        "description": "等待页面上指定元素出现",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "要等待的元素的 CSS 选择器"},
                "timeout": {"type": "integer", "description": "超时时间（毫秒），默认 5000"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_close",
        "description": "关闭浏览器并释放资源，下次使用时会重新初始化",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


async def execute(tool_name: str, args: dict) -> str:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return f"[错误] 未知工具：{tool_name}"
    return await handler(args)
