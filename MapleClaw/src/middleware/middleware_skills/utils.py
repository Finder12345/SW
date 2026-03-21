"""技能发现与加载工具函数。

两层设计：
  1. 发现层 — 扫描 skills/ 目录，解析每个 SKILL.md 的 front-matter 生成注册表。
  2. 加载层 — 提供 load_skill / load_skill_section 两个 LangChain Tool，
              供 LLM 按需调用来获取技能正文和脚本工具。

技能目录结构约定::

    skills/
      └─ weather_query_skill/
         ├─ SKILL.md          # YAML front-matter (name, description) + Markdown body
         └─ scripts/
            ├─ get_current_weather.py   # 导出 tool 变量
            └─ get_forecast.py

工具返回值中的 ``_skill_update`` 字段由 SkillMiddleware.wrap_tool_call 读取，
暂存到 ToolMessage.additional_kwargs["_skill_update"]，最终在 after_model 合并进 state。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import BaseTool, tool


# ══════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════

@dataclass
class SkillMeta:
    """解析后的技能元数据（注册表级别，不含正文）。"""
    name: str
    description: str
    dir_path: Path
    sections: list[str] = field(default_factory=list)  # SKILL.md 中的 ## 标题

    @property
    def registry_line(self) -> str:
        sec = ", ".join(self.sections) if self.sections else "N/A"
        return f"- {self.name}: {self.description} [sections: {sec}]"


# ══════════════════════════════════════════════════════════════
# SKILL.md 解析
# ══════════════════════════════════════════════════════════════

def parse_skill_md(skill_md_path: Path) -> dict[str, Any]:
    """解析 SKILL.md，返回 front-matter 字段 + body sections。

    Returns::

        {
            "name": str,
            "description": str,
            "body": str,                     # 去掉 front-matter 后的全文
            "sections": {title: content, ...}
        }
    """
    text = skill_md_path.read_text(encoding="utf-8")

    # ── front-matter ──
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if fm_match:
        front = yaml.safe_load(fm_match.group(1)) or {}
        body = text[fm_match.end():]
    else:
        front = {}
        body = text

    name = front.get("name", skill_md_path.parent.name)
    description = front.get("description", "")

    # ── 按 ## 标题切分 section ──
    sections: dict[str, str] = {}
    current_title = "__intro__"
    current_lines: list[str] = []

    for line in body.splitlines():
        heading = re.match(r"^##\s+(.+)$", line)
        if heading:
            content = "\n".join(current_lines).strip()
            if content:
                sections[current_title] = content
            current_title = heading.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    content = "\n".join(current_lines).strip()
    if content:
        sections[current_title] = content

    return {
        "name": name,
        "description": description,
        "body": body.strip(),
        "sections": sections,
    }


# ══════════════════════════════════════════════════════════════
# Scripts 工具加载
# ══════════════════════════════════════════════════════════════

def load_tools_from_scripts(scripts_dir: Path) -> list[BaseTool]:
    """从 scripts/ 目录下的每个 .py 文件加载导出的 tool 对象。"""
    tools: list[BaseTool] = []
    if not scripts_dir.is_dir():
        return tools

    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"_skill_script_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            print(f"[SkillLoader] ⚠ Failed to load {py_file}: {exc}")
            continue

        if hasattr(mod, "tool") and isinstance(mod.tool, BaseTool):
            tools.append(mod.tool)
        else:
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, BaseTool) and obj not in tools:
                    tools.append(obj)
    return tools


# ══════════════════════════════════════════════════════════════
# 技能注册表发现（轻量级，仅读 front-matter）
# ══════════════════════════════════════════════════════════════

def discover_skill_registry(skills_dir: str | Path) -> tuple[list[SkillMeta], str]:
    """扫描技能根目录，返回 (技能元数据列表, 注册表提示文本)。

    此阶段 **不** 加载 scripts，仅解析 SKILL.md 元数据。
    """
    skills_dir = Path(skills_dir)
    if not skills_dir.is_dir():
        return [], "No skills directory found."

    metas: list[SkillMeta] = []
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        parsed = parse_skill_md(skill_md)
        meta = SkillMeta(
            name=parsed["name"],
            description=parsed["description"],
            dir_path=child,
            sections=list(parsed["sections"].keys()),
        )
        metas.append(meta)

    if not metas:
        return [], "No skills found."

    registry_text = "Available skills (use load_skill to activate):\n"
    registry_text += "\n".join(m.registry_line for m in metas)
    return metas, registry_text


# ══════════════════════════════════════════════════════════════
# 模块级缓存 — 由 SkillMiddleware.before_agent 初始化
# ══════════════════════════════════════════════════════════════

_skill_meta_cache: dict[str, SkillMeta] = {}
_skill_parsed_cache: dict[str, dict[str, Any]] = {}
_skill_tools_cache: dict[str, list[BaseTool]] = {}

# wrap_tool_call 用此 key 在 ToolMessage.additional_kwargs 中标记技能更新
SKILL_UPDATE_KEY = "_skill_update"


def init_caches(metas: list[SkillMeta]) -> None:
    """由 SkillMiddleware 在 before_agent 中调用，初始化缓存。"""
    _skill_meta_cache.clear()
    _skill_parsed_cache.clear()
    _skill_tools_cache.clear()
    for m in metas:
        _skill_meta_cache[m.name] = m


def _ensure_parsed(skill_name: str) -> dict[str, Any] | None:
    if skill_name in _skill_parsed_cache:
        return _skill_parsed_cache[skill_name]
    meta = _skill_meta_cache.get(skill_name)
    if meta is None:
        return None
    parsed = parse_skill_md(meta.dir_path / "SKILL.md")
    _skill_parsed_cache[skill_name] = parsed
    return parsed


def _ensure_tools(skill_name: str) -> list[BaseTool]:
    if skill_name in _skill_tools_cache:
        return _skill_tools_cache[skill_name]
    meta = _skill_meta_cache.get(skill_name)
    if meta is None:
        return []
    tools = load_tools_from_scripts(meta.dir_path / "scripts")
    _skill_tools_cache[skill_name] = tools
    return tools


# ══════════════════════════════════════════════════════════════
# LLM 可调用的 Tool：load_skill / load_skill_section
# ══════════════════════════════════════════════════════════════

@tool
def load_skill(skill_name: str) -> str:
    """加载指定技能的完整内容（SKILL.md 正文 + 注册其 scripts 工具）。

    调用此工具后，该技能的工具将在后续轮次中可用。

    Args:
        skill_name: 技能名称（来自技能注册表中的 name 字段）
    """
    if skill_name not in _skill_meta_cache:
        available = ", ".join(_skill_meta_cache.keys()) or "none"
        return json.dumps({
            "error": f"Skill '{skill_name}' not found. Available: [{available}]",
            SKILL_UPDATE_KEY: None,
        }, ensure_ascii=False)

    parsed = _ensure_parsed(skill_name)
    tools = _ensure_tools(skill_name)
    tool_names = [t.name for t in tools]

    body_text = parsed["body"] if parsed else ""
    result_for_llm = (
        f"✅ Skill '{skill_name}' loaded.\n"
        f"Tools registered: {tool_names}\n\n"
        f"--- SKILL.md content ---\n{body_text}"
    )

    skill_update = {
        "skill_name": skill_name,
        "description": parsed.get("description", "") if parsed else "",
        "sections": parsed.get("sections", {}) if parsed else {},
        "tool_names": tool_names,
        "fully_loaded": True,
    }

    return json.dumps({
        "content": result_for_llm,
        SKILL_UPDATE_KEY: skill_update,
    }, ensure_ascii=False)


@tool
def load_skill_section(skill_name: str, section_name: str) -> str:
    """加载指定技能的某个 section（SKILL.md 中 ## 标题下的内容）。

    适用于技能文档较长、只需要部分内容的场景。

    Args:
        skill_name: 技能名称
        section_name: section 标题（从注册表的 sections 列表中选择）
    """
    if skill_name not in _skill_meta_cache:
        return json.dumps({
            "error": f"Skill '{skill_name}' not found.",
            SKILL_UPDATE_KEY: None,
        }, ensure_ascii=False)

    parsed = _ensure_parsed(skill_name)
    if not parsed:
        return json.dumps({
            "error": "Failed to parse SKILL.md",
            SKILL_UPDATE_KEY: None,
        }, ensure_ascii=False)

    sections = parsed.get("sections", {})
    if section_name not in sections:
        available = list(sections.keys())
        return json.dumps({
            "error": f"Section '{section_name}' not found. Available: {available}",
            SKILL_UPDATE_KEY: None,
        }, ensure_ascii=False)

    section_content = sections[section_name]
    tools = _ensure_tools(skill_name)
    tool_names = [t.name for t in tools]

    result_for_llm = (
        f"✅ Skill '{skill_name}' section '{section_name}' loaded.\n"
        f"Tools registered: {tool_names}\n\n"
        f"--- {section_name} ---\n{section_content}"
    )

    skill_update = {
        "skill_name": skill_name,
        "description": parsed.get("description", ""),
        "sections": {section_name: section_content},
        "tool_names": tool_names,
        "fully_loaded": False,
    }

    return json.dumps({
        "content": result_for_llm,
        SKILL_UPDATE_KEY: skill_update,
    }, ensure_ascii=False)


def get_all_loaded_skill_tools() -> list[BaseTool]:
    """返回当前所有已缓存技能的脚本工具（合并去重）。"""
    all_tools: list[BaseTool] = []
    seen: set[str] = set()
    for tools in _skill_tools_cache.values():
        for t in tools:
            if t.name not in seen:
                all_tools.append(t)
                seen.add(t.name)
    return all_tools


# 技能管理工具，由 SkillMiddleware 注册到 create_agent
SKILL_MANAGEMENT_TOOLS: list[BaseTool] = [load_skill, load_skill_section]