# 技能加载器：扫描 skills/builtin/ 和 workspace/skills/ 目录，收集工具定义和执行函数

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path

import yaml

WORKSPACE_SKILLS_DIR = Path(__file__).parent.parent / "workspace" / "skills"


def _register_module(module, tool_map: dict) -> list[dict]:
    """从模块中提取工具定义，返回 (tool_definitions 列表)。单工具和多工具模块都支持。"""
    registered = []

    if hasattr(module, "TOOL_DEFINITION"):
        defn = module.TOOL_DEFINITION
        registered.append(defn)
        tool_map[defn["name"]] = module.execute

    if hasattr(module, "TOOL_DEFINITIONS"):
        for defn in module.TOOL_DEFINITIONS:
            registered.append(defn)
            tool_map[defn["name"]] = lambda args, _name=defn["name"], _mod=module: _mod.execute(_name, args)

    return registered


def _load_workspace_skill(path: Path, tool_map: dict) -> list[dict]:
    """用 importlib.util 动态加载单个 workspace skill 文件，返回注册的工具定义列表。"""
    module_name = f"_workspace_skill_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "TOOL_DEFINITION") and not hasattr(module, "TOOL_DEFINITIONS"):
            print(f"[skills] 跳过 {path.name}：缺少 TOOL_DEFINITION 或 TOOL_DEFINITIONS")
            return []
        if not hasattr(module, "execute"):
            print(f"[skills] 跳过 {path.name}：缺少 execute 函数")
            return []

        return _register_module(module, tool_map)

    except Exception as e:
        print(f"[skills] 跳过 {path.name}：加载失败 — {e}")
        return []


def _load_md_skills(skills_dir: Path) -> list[dict]:
    """读取 .md skill 文件，解析 frontmatter 和正文，返回 [{name, description, content}]。"""
    docs = []
    for path in sorted(skills_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        # 没有 frontmatter 的文件（如 README.md）跳过，不作为 skill 加载
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            frontmatter: dict = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError as e:
            print(f"[skills] 跳过 {path.name}：frontmatter 解析失败 — {e}")
            continue
        content = parts[2]
        docs.append({
            "name": frontmatter.get("name", path.stem),
            "description": frontmatter.get("description", ""),
            "content": content.strip(),
        })
        print(f"[skills] 已加载 .md skill：{path.name}")
    return docs


def load_skills() -> tuple[list[dict], dict, list[dict]]:
    """
    1. 加载 skills/builtin/ 中的内置 skill
    2. 加载 workspace/skills/ 中的自定义 .py skill（同名工具会覆盖内置版本）
    3. 加载 workspace/skills/ 中的 .md skill（注入 system prompt 的行为指南）

    返回:
        tools: Claude API 格式的工具定义列表
        tool_map: {工具名: execute 函数} 的字典
        skill_docs: [{name, description, content}] 的 .md skill 列表
    """
    tool_map: dict = {}
    # 用 dict 暂存，key 是工具名，保证同名工具后加载的覆盖先加载的
    tool_defs: dict[str, dict] = {}

    # --- 第一步：加载 builtin ---
    builtin_dir = Path(__file__).parent / "builtin"
    for _, module_name, _ in pkgutil.iter_modules([str(builtin_dir)]):
        if module_name.startswith("_"):
            continue
        module = importlib.import_module(f"skills.builtin.{module_name}")
        for defn in _register_module(module, tool_map):
            tool_defs[defn["name"]] = defn

    # --- 第二步：加载 workspace/skills/（同名工具覆盖 builtin）---
    skill_docs: list[dict] = []
    if WORKSPACE_SKILLS_DIR.exists():
        for path in sorted(WORKSPACE_SKILLS_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue
            for defn in _load_workspace_skill(path, tool_map):
                if defn["name"] in tool_defs:
                    print(f"[skills] {path.name} 覆盖内置工具：{defn['name']}")
                tool_defs[defn["name"]] = defn

        skill_docs = _load_md_skills(WORKSPACE_SKILLS_DIR)

    tools = list(tool_defs.values())
    print(f"已加载 {len(tools)} 个工具: {[t['name'] for t in tools]}")
    if skill_docs:
        print(f"已加载 {len(skill_docs)} 个 .md skill: {[s['name'] for s in skill_docs]}")
    return tools, tool_map, skill_docs
