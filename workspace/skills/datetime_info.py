from datetime import datetime

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

TOOL_DEFINITION = {
    "name": "datetime_info",
    "description": "返回当前的日期、时间和星期几",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


async def execute(args: dict) -> str:
    now = datetime.now()
    weekday = WEEKDAYS[now.weekday()]
    return f"{now.strftime('%Y-%m-%d')} {now.strftime('%H:%M:%S')} {weekday}"
