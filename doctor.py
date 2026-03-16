# 诊断工具：检查配置、依赖、服务连接是否正常
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from config import DEFAULTS, load_config, CONFIG_FILE
from memory.vector_store import get_stats


WORKSPACE_DIR = Path(__file__).parent / "workspace"


def check_config() -> list[str]:
    """检查配置完整性"""
    issues = []
    config = load_config()

    for key, spec in DEFAULTS.items():
        val = config.get(key)
        if spec["required"] and not val:
            issues.append(f"  [缺失] {key} — {spec['desc']}")

    return issues


def check_workspace() -> list[str]:
    """检查 workspace 目录结构"""
    issues = []
    required_files = ["SOUL.md", "USER.md", "HEARTBEAT.md"]

    for fname in required_files:
        fpath = WORKSPACE_DIR / fname
        if not fpath.exists():
            issues.append(f"  [缺失] workspace/{fname}")
        elif fpath.stat().st_size == 0:
            issues.append(f"  [空文件] workspace/{fname}")

    return issues


def check_memory() -> list[str]:
    """检查记忆系统状态"""
    issues = []
    try:
        stats = get_stats()
        total = stats["total"]
        if total == 0:
            issues.append("  [提示] 向量库为空，尚无记忆")
        else:
            print(f"  记忆总数: {total}")
            print(f"  日期范围: {stats['date_range']}")
            if stats["tags"]:
                print(f"  标签分布: {stats['tags']}")
    except Exception as e:
        issues.append(f"  [错误] ChromaDB 初始化失败: {e}")

    return issues


async def check_anthropic() -> list[str]:
    """测试 Anthropic API 连通性"""
    issues = []
    try:
        import anthropic
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        if response.content:
            print("  API 连通正常")
    except Exception as e:
        issues.append(f"  [错误] Anthropic API: {e}")

    return issues


async def check_discord() -> list[str]:
    """检查 Discord token 格式（不实际连接）"""
    issues = []
    config = load_config()
    token = config.get("discord_bot_token", "")

    if not token:
        issues.append("  [缺失] Discord Bot Token")
    elif len(token) < 50:
        issues.append("  [可疑] Discord Bot Token 太短，可能无效")
    else:
        print("  Token 格式看起来正常")

    channel_id = config.get("discord_channel_id", "")
    if channel_id and not str(channel_id).isdigit():
        issues.append(f"  [错误] DISCORD_CHANNEL_ID 应为数字，当前值: {channel_id}")

    return issues


async def run_doctor():
    """执行全部检查"""
    load_dotenv()

    print("=" * 50)
    print("PyAgent Doctor — 配置与环境诊断")
    print("=" * 50)

    all_issues = []

    # 1. 配置文件
    print(f"\n[1/5] 配置文件 ({CONFIG_FILE.name})")
    if CONFIG_FILE.exists():
        print(f"  配置文件: {CONFIG_FILE}")
    else:
        print("  配置文件不存在，将使用 .env + 默认值")
    issues = check_config()
    all_issues.extend(issues)
    for issue in issues:
        print(issue)
    if not issues:
        print("  所有必填配置已设置")

    # 2. Workspace
    print("\n[2/5] Workspace 目录")
    issues = check_workspace()
    all_issues.extend(issues)
    for issue in issues:
        print(issue)
    if not issues:
        print("  所有必需文件存在")

    # 3. 记忆系统
    print("\n[3/5] 记忆系统 (ChromaDB)")
    issues = check_memory()
    all_issues.extend(issues)
    for issue in issues:
        print(issue)

    # 4. Anthropic API
    print("\n[4/5] Anthropic API")
    issues = await check_anthropic()
    all_issues.extend(issues)
    for issue in issues:
        print(issue)

    # 5. Discord
    print("\n[5/5] Discord")
    issues = await check_discord()
    all_issues.extend(issues)
    for issue in issues:
        print(issue)

    # 汇总
    print("\n" + "=" * 50)
    if all_issues:
        print(f"发现 {len(all_issues)} 个问题：")
        for issue in all_issues:
            print(issue)
        print("\n请修复以上问题后重试。")
    else:
        print("所有检查通过！PyAgent 可以正常运行。")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_doctor())
