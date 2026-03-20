# 离线工具选择 Benchmark：测试给定 prompt 时 agent 是否选择了正确工具

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# 把 pyagent 根目录加入路径，让 import brain / skills 等正常工作
PYAGENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PYAGENT_DIR))

# 在 import anthropic 之前加载 .env，否则 API key 不可用
from dotenv import load_dotenv
load_dotenv(PYAGENT_DIR / ".env")

from brain import Brain
from skills.loader import load_skills

CASES_FILE = Path(__file__).parent / "cases.json"
RESULTS_DIR = Path(__file__).parent / "results"


def make_mock_tool_map(tool_names: list[str], called_tools: list[str]) -> dict:
    """为每个工具创建 mock handler：记录调用，立即返回 OK，不执行真实逻辑。"""
    async def mock_handler(args: dict, _name: str = None) -> str:
        called_tools.append(_name)
        return f"[mock] {_name} OK"

    return {
        name: (lambda args, n=name: mock_handler(args, n))
        for name in tool_names
    }


def evaluate(called: list[str], expected: list[str], mode: str) -> tuple[bool, str]:
    """
    判断本条用例是否通过，返回 (passed, reason)。

    - first_tool: called[0] 必须在 expected 中
    - any: expected 中每个工具至少调用过一次
    - none: called 必须为空（不调用任何工具）
    """
    if mode == "none":
        passed = len(called) == 0
        reason = "" if passed else f"期望不调用工具，实际调用了 {called}"
        return passed, reason

    if mode == "first_tool":
        if not called:
            return False, f"期望第一个工具为 {expected}，实际未调用任何工具"
        passed = called[0] in expected
        reason = "" if passed else f"期望第一个工具为 {expected}，实际为 {called[0]}"
        return passed, reason

    if mode == "any":
        missing = [t for t in expected if t not in called]
        passed = len(missing) == 0
        reason = "" if passed else f"缺少工具调用：{missing}，实际调用：{called}"
        return passed, reason

    return False, f"未知 match_mode: {mode}"


async def run_case(case: dict, tools: list[dict], tool_names: list[str], verbose: bool) -> dict:
    """运行单条用例，返回结果 dict。"""
    called_tools: list[str] = []
    mock_tool_map = make_mock_tool_map(tool_names, called_tools)

    brain = Brain(tools=tools, tool_map=mock_tool_map, save_history=False)

    try:
        await brain.think(case["prompt"])
    except Exception as e:
        return {
            "id": case["id"],
            "prompt": case["prompt"],
            "tags": case.get("tags", []),
            "passed": False,
            "called_tools": called_tools,
            "expected_tools": case["expected_tools"],
            "match_mode": case["match_mode"],
            "reason": f"[异常] {e}",
        }

    passed, reason = evaluate(called_tools, case["expected_tools"], case["match_mode"])

    if verbose:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] called={called_tools}  expected={case['expected_tools']}")
        if not passed:
            print(f"         {reason}")

    return {
        "id": case["id"],
        "prompt": case["prompt"],
        "tags": case.get("tags", []),
        "passed": passed,
        "called_tools": called_tools,
        "expected_tools": case["expected_tools"],
        "match_mode": case["match_mode"],
        "reason": reason,
    }


def print_results(results: list[dict]) -> None:
    """打印结果表格和汇总。"""
    col_w = 42
    print("\nPyAgent Tool Selection Benchmark")
    print("=" * 65)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        prompt_short = r["prompt"][:col_w] + "…" if len(r["prompt"]) > col_w else r["prompt"]
        expected_str = str(r["expected_tools"]) if r["expected_tools"] else "[]"
        print(f"[{status}]  {prompt_short:<{col_w}}  →  {expected_str}")
        if not r["passed"] and r["reason"]:
            print(f"       {r['reason']}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print("=" * 65)
    print(f"结果: {passed}/{total} 通过 ({100 * passed / total:.1f}%)" if total else "无用例")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"失败用例: {len(failed)}")
        for r in failed:
            print(f"  #{r['id']} {r['prompt'][:50]}  →  got: {r['called_tools']}  expected: {r['expected_tools']}")


def save_results(results: list[dict]) -> Path:
    """保存结果到 benchmarks/results/YYYY-MM-DD.json。"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    output_path = RESULTS_DIR / f"{today}.json"

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    payload = {
        "date": today,
        "total": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0,
        "cases": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return output_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="PyAgent 工具选择 Benchmark")
    parser.add_argument("--tag", help="只运行指定标签的用例，如 --tag search")
    parser.add_argument("--case", type=int, help="只运行第 N 条用例（按 id）")
    parser.add_argument("--verbose", action="store_true", help="显示每条用例的实际 vs 期望工具调用")
    args = parser.parse_args()

    cases = json.loads(CASES_FILE.read_text())

    # 过滤用例
    if args.case is not None:
        cases = [c for c in cases if c["id"] == args.case]
    elif args.tag:
        cases = [c for c in cases if args.tag in c.get("tags", [])]

    if not cases:
        print("没有符合条件的用例。")
        return

    # 加载真实工具定义（只用 schema，不用真实 handler）
    tools, _, _ = load_skills()
    tool_names = [t["name"] for t in tools]

    print(f"加载了 {len(tools)} 个工具: {tool_names}")
    print(f"运行 {len(cases)} 条用例...\n")

    results = []
    for case in cases:
        prompt_short = case["prompt"][:50]
        print(f"#{case['id']} {prompt_short}", end="  ", flush=True)
        result = await run_case(case, tools, tool_names, verbose=args.verbose)
        status = "✓" if result["passed"] else "✗"
        print(status)
        results.append(result)

    print_results(results)

    output_path = save_results(results)
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
