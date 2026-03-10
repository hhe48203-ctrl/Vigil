# 技能加载器：扫描 skills/builtin/ 目录，收集工具定义和执行函数

import importlib
import pkgutil
from pathlib import Path


def load_skills() -> tuple[list[dict], dict]:
    """
    扫描 builtin 目录，加载所有 skill 模块。

    返回:
        tools: Claude API 格式的工具定义列表
        tool_map: {工具名: execute 函数} 的字典
    """
    tools = []
    tool_map = {}

    builtin_dir = Path(__file__).parent / "builtin"

    for finder, module_name, _ in pkgutil.iter_modules([str(builtin_dir)]):
        if module_name.startswith("_"):
            continue

        module = importlib.import_module(f"skills.builtin.{module_name}")

        # 单工具模块（如 shell.py、memory_ops.py）
        if hasattr(module, "TOOL_DEFINITION"):
            defn = module.TOOL_DEFINITION
            tools.append(defn)
            tool_map[defn["name"]] = module.execute

        # 多工具模块（如 file_ops.py）
        if hasattr(module, "TOOL_DEFINITIONS"):
            for defn in module.TOOL_DEFINITIONS:
                tools.append(defn)
                # 多工具模块的 execute 第一个参数是 tool_name
                tool_map[defn["name"]] = lambda args, _name=defn["name"], _mod=module: _mod.execute(_name, args)

    print(f"已加载 {len(tools)} 个工具: {[t['name'] for t in tools]}")
    return tools, tool_map
