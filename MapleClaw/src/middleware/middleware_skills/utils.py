"""技能发现与格式化。

以 skills 规范为主：
  1. 解析 SKILL.md front-matter → SkillMetadata
  2. 将技能摘要注入 system prompt，完整说明按需读取 SKILL.md

可执行脚本不在 middleware 层自动注入为工具，避免偏离 progressive
 disclosure 的技能范式。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from MapleClaw.src.agent.state import SkillMetadata

logger = logging.getLogger(__name__)

MAX_SKILL_FILE_SIZE = 1 * 1024 * 1024


# ══════════════════════════════════════════════════════════════
# SKILL.md 解析
# ══════════════════════════════════════════════════════════════

def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip(", ") for item in value.split() if item.strip(", ")]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_requires(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for key in ("config", "bins", "tools", "os"):
        items = _normalize_string_list(value.get(key, []))
        if items:
            normalized[key] = items
    return normalized


def parse_skill_md(skill_md_path: Path) -> SkillMetadata | None:
    """解析 SKILL.md，返回 SkillMetadata（包含 OpenCalw 兼容字段）。"""
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read %s: %s", skill_md_path, e)
        return None

    if len(text) > MAX_SKILL_FILE_SIZE:
        logger.warning("Skipping %s: too large (%d bytes)", skill_md_path, len(text))
        return None

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not fm_match:
        logger.warning("Skipping %s: no YAML front-matter", skill_md_path)
        return None

    try:
        front = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in %s: %s", skill_md_path, e)
        return None

    if not isinstance(front, dict):
        return None

    name = str(front.get("name", "")).strip()
    description = str(front.get("description", "")).strip()
    if not name or not description:
        logger.warning("Skipping %s: missing name or description", skill_md_path)
        return None

    metadata = front.get("metadata", {})
    openclaw_meta = metadata.get("openclaw", {}) if isinstance(metadata, dict) else {}

    triggers = _normalize_string_list(front.get("triggers", []))
    priority = str(front.get("priority", "medium")).strip() or "medium"

    try:
        max_tokens = int(front.get("max_tokens", 3000))
    except (TypeError, ValueError):
        max_tokens = 3000

    requires = _normalize_requires(openclaw_meta.get("requires", {}))
    emoji = str(openclaw_meta.get("emoji", "")).strip()
    install = openclaw_meta.get("install", []) if isinstance(openclaw_meta.get("install", []), list) else []

    allowed_tools = _normalize_string_list(
        front.get("allowed-tools", front.get("allowed_tools", []))
    )

    body = text[fm_match.end():]
    sections = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)

    return SkillMetadata(
        name=name,
        description=description,
        path=str(skill_md_path.resolve()),
        sections=sections,
        allowed_tools=allowed_tools,
        # OpenCalw 扩展字段
        triggers=triggers,
        priority=priority,
        max_tokens=max_tokens,
        requires=requires,
        emoji=emoji,
        install=install,
    )


class DiscoveredSkill:
    """发现的技能：仅包含 metadata。"""
    __slots__ = ("metadata",)

    def __init__(self, metadata: SkillMetadata):
        self.metadata = metadata


def discover_skills(skills_dir: str | Path) -> list[DiscoveredSkill]:
    """扫描技能目录，仅返回 metadata。"""
    skills_dir = Path(skills_dir)
    if not skills_dir.is_dir():
        logger.warning("Skills directory not found: %s", skills_dir)
        return []

    results: list[DiscoveredSkill] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue

        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue

        meta = parse_skill_md(skill_md)
        if meta is None:
            continue

        results.append(DiscoveredSkill(metadata=meta))

    return results


# ══════════════════════════════════════════════════════════════
# 格式化（给 system prompt 用）
# ══════════════════════════════════════════════════════════════

def format_skills_list(skills: list[SkillMetadata]) -> str:
    """将技能元数据格式化为系统提示词中的列表文本（支持 OpenCalw 字段）。"""
    if not skills:
        return "(No skills available.)"

    lines: list[str] = []
    for s in skills:
        # 构建 emoji + 名称
        emoji_prefix = f"{s.get('emoji', '')} " if s.get('emoji') else ""
        name_with_emoji = f"{emoji_prefix}**{s['name']}**" if s.get('emoji') else f"**{s['name']}**"
        
        line = f"- {name_with_emoji}: {s['description']}"

        if s["allowed_tools"]:
            line += f"\n  Suggested tools: {', '.join(s['allowed_tools'])}"
        
        # 添加触发关键词（OpenCalw 字段）
        if s.get("triggers"):
            triggers_str = ', '.join(s['triggers'])
            line += f"\n  Triggers: {triggers_str}"
        
        # 添加优先级（OpenCalw 字段）
        if s.get("priority"):
            line += f"\n  Priority: {s['priority']}"
        
        # 添加依赖条件（OpenCalw 字段）
        if s.get("requires"):
            requires = s['requires']
            if requires:
                requires_list = []
                if requires.get("config"):
                    requires_list.append(f"config: {', '.join(requires['config'])}")
                if requires.get("bins"):
                    requires_list.append(f"bins: {', '.join(requires['bins'])}")
                if requires.get("tools"):
                    requires_list.append(f"tools: {', '.join(requires['tools'])}")
                line += f"\n  Requires: {', '.join(requires_list)}"
        
        # 添加 sections
        if s["sections"]:
            line += f"\n  Sections: {', '.join(s['sections'])}"
        line += f"\n  Full instructions: `{s['path']}`"
        lines.append(line)
    return "\n".join(lines)