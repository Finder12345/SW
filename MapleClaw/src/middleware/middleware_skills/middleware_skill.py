"""技能中间件：基于 AgentMiddleware 实现技能的按需发现、加载与注入。

生命周期：

  before_agent   → 扫描 skills/ 目录，生成注册表文本写入 state.skill_registry，
                    初始化 state.loaded_skills = {}，state.phase = "discovery"。

  wrap_model_call → 根据 state.phase 决定注入什么系统提示词：
                    - "discovery": 注入注册表 + "请根据用户意图调用 load_skill"
                    - "ready":    注入已加载技能正文摘要 + 技能工具列表

  wrap_tool_call  → 拦截 load_skill / load_skill_section 的 ToolMessage，
                    从返回 JSON 中提取 _skill_update，写入
                    ToolMessage.additional_kwargs["_skill_update"]。
                    其他工具透传。

  after_model     → 检查本轮消息中是否有携带 _skill_update 的 ToolMessage，
                    将技能信息合并进 state.loaded_skills，
                    并判断是否切换 state.phase → "ready"。

为什么不在 wrap_tool_call 中直接写 state？
  因为 tool call 发生时消息还没有落盘到 state.messages，直接写 state 可能
  导致竞态或与 LangGraph 的 reducer 冲突。统一在 after_model 合并最稳妥。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime
from langgraph.types import Command

from MapleClaw.src.agent.state import AgentState, SkillEntry
from MapleClaw.src.middleware.middleware_skills.utils import (
    SKILL_MANAGEMENT_TOOLS,
    SKILL_UPDATE_KEY,
    discover_skill_registry,
    get_all_loaded_skill_tools,
    init_caches,
)


# ── 系统提示词模板 ────────────────────────────────────────────

_DISCOVERY_PROMPT_FRAGMENT = """\

## Skill System — Discovery Phase

You have access to a skill registry. Based on the user's request, decide whether
to load any skills by calling `load_skill(skill_name)` or
`load_skill_section(skill_name, section_name)`.

{registry}

If no skill is needed, answer the user directly with your built-in tools.
After loading the skill(s) you need, proceed to answer the user's question \
using the newly available tools.
"""

_READY_PROMPT_FRAGMENT = """\

## Loaded Skills

{loaded_summary}

You can now use the tools listed above to help the user.
If you need additional skills, you can still call `load_skill`.
"""


class SkillMiddleware(AgentMiddleware[AgentState, Any]):
    """技能加载中间件。

    Usage::

        mw = SkillMiddleware(skills_dir="skills")
        agent = create_agent(model=..., tools=[...], middleware=[mw])
    """

    state_schema = AgentState

    def __init__(self, skills_dir: str | Path=r"D:\CODE\MYSELF\SW\MapleClaw\skills"):
        self.skills_dir = Path(skills_dir)
        self._registry_text: str = ""

    @property
    def name(self) -> str:
        return "SkillMiddleware"

    @property
    def tools(self) -> list[BaseTool]:
        """向 create_agent 注册技能管理工具 (load_skill / load_skill_section)。

        注意：技能脚本工具（如 get_current_weather）不在此注册，
        而是在 wrap_model_call 中动态追加到 request.tools。
        """
        return list(SKILL_MANAGEMENT_TOOLS)

    # ══════════════════════════════════════════════════════════
    # 1) before_agent — 初始化 state，扫描注册表
    # ══════════════════════════════════════════════════════════

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 启动时扫描 skills/ 元数据，生成注册表。"""
        metas, registry_text = discover_skill_registry(self.skills_dir)
        self._registry_text = registry_text

        # 初始化缓存（供 load_skill / load_skill_section 使用）
        init_caches(metas)

        print(f"[SkillMiddleware] Discovered {len(metas)} skill(s)")

        return {
            "skill_registry": registry_text,
            "loaded_skills": {},
            "phase": "discovery",
        }

    # ══════════════════════════════════════════════════════════
    # 2) wrap_tool_call — 拦截 load_skill* 的返回，暂存 _skill_update
    # ══════════════════════════════════════════════════════════

    def wrap_tool_call(self, request, handler) -> ToolMessage | Command:
        """拦截 tool call，对 load_skill / load_skill_section 的返回做处理。"""
        result = handler(request)

        # 只处理 ToolMessage 类型的返回
        if not isinstance(result, ToolMessage):
            return result

        tool_name = request.tool_call.get("name", "")
        if tool_name not in ("load_skill", "load_skill_section"):
            return result

        # 从工具返回的 JSON 中提取 _skill_update
        try:
            payload = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return result

        skill_update = payload.get(SKILL_UPDATE_KEY)
        if skill_update is None:
            # 可能是错误返回（技能不存在等），原样透传
            # 但把 content 改为人类可读的错误信息
            error_msg = payload.get("error", result.content)
            result.content = error_msg
            return result

        # 将 _skill_update 暂存到 ToolMessage.additional_kwargs
        # after_model 会来读取
        if not hasattr(result, "additional_kwargs") or result.additional_kwargs is None:
            result.additional_kwargs = {}
        result.additional_kwargs[SKILL_UPDATE_KEY] = skill_update

        # 把给 LLM 看的内容替换为干净的文本（去掉 _skill_update JSON 壳）
        result.content = payload.get("content", result.content)

        return result

    # ══════════════════════════════════════════════════════════
    # 3) after_model — 从 ToolMessage 收集 _skill_update，合并进 state
    # ══════════════════════════════════════════════════════════

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """模型调用结束后，检查消息中是否有待合并的技能更新。"""
        loaded_skills: dict[str, SkillEntry] = dict(state.get("loaded_skills", {}))
        has_update = False

        # 扫描最近的消息，查找携带 _skill_update 的 ToolMessage
        for msg in reversed(state.get("messages", [])):
            if not isinstance(msg, ToolMessage):
                continue
            additional = getattr(msg, "additional_kwargs", None) or {}
            update = additional.get(SKILL_UPDATE_KEY)
            if update is None:
                continue

            has_update = True
            skill_name = update["skill_name"]

            # 合并策略：已有的 sections 保留，新的覆盖/追加
            existing = loaded_skills.get(skill_name, {})
            existing_sections = dict(existing.get("sections", {}))
            existing_sections.update(update.get("sections", {}))

            loaded_skills[skill_name] = SkillEntry(
                name=skill_name,
                description=update.get("description", existing.get("description", "")),
                sections=existing_sections,
                tool_names=update.get("tool_names", existing.get("tool_names", [])),
                fully_loaded=update.get("fully_loaded", False) or existing.get("fully_loaded", False),
            )

        if not has_update:
            return None

        # 有技能被加载了 → 切换 phase 到 ready
        new_phase = "ready" if loaded_skills else state.get("phase", "discovery")

        return {
            "loaded_skills": loaded_skills,
            "phase": new_phase,
        }

    # ══════════════════════════════════════════════════════════
    # 4) wrap_model_call — 根据 phase 注入不同的系统提示词 + 动态工具
    # ══════════════════════════════════════════════════════════

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """在模型调用前：
        - 注入技能发现/就绪提示到 system prompt
        - 将已加载技能的脚本工具动态追加到 request.tools
        """
        phase = request.state.get("phase", "discovery")
        loaded_skills = request.state.get("loaded_skills", {})

        # ── 构建提示词片段 ──
        if phase == "discovery" or not loaded_skills:
            prompt_fragment = _DISCOVERY_PROMPT_FRAGMENT.format(
                registry=self._registry_text
            )
        else:
            # 构建已加载技能的摘要
            lines = []
            for name, entry in loaded_skills.items():
                tool_names = entry.get("tool_names", [])
                desc = entry.get("description", "")
                lines.append(f"- **{name}**: {desc}  Tools: {tool_names}")
            loaded_summary = "\n".join(lines)
            prompt_fragment = _READY_PROMPT_FRAGMENT.format(
                loaded_summary=loaded_summary
            )

        # ── 注入系统提示词 ──
        current_system = ""
        if request.system_message:
            current_system = request.system_message.content

        new_system = current_system + prompt_fragment
        new_request = request.override(
            system_message=SystemMessage(content=new_system)
        )

        # ── 动态追加已加载技能的脚本工具 ──
        skill_tools = get_all_loaded_skill_tools()
        if skill_tools:
            existing_tools = list(new_request.tools or [])
            existing_names = {
                t.name if isinstance(t, BaseTool) else t.get("name", "")
                for t in existing_tools
            }
            for t in skill_tools:
                if t.name not in existing_names:
                    existing_tools.append(t)
            new_request = new_request.override(tools=existing_tools)

        return handler(new_request)

    # ══════════════════════════════════════════════════════════
    # 其余 hooks — 透传
    # ══════════════════════════════════════════════════════════

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        return None

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        return None

    # ══════════════════════════════════════════════════════════
    # Async 版本
    # ══════════════════════════════════════════════════════════

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    async def aafter_agent(self, state, runtime):
        return None

    async def abefore_model(self, state, runtime):
        return None

    async def aafter_model(self, state, runtime):
        return self.after_model(state, runtime)

    async def awrap_model_call(self, request, handler):
        # handler 在 async 场景下是 async 的，但我们的逻辑本身是同步的
        # 所以手动适配：先注入，再 await handler
        phase = request.state.get("phase", "discovery")
        loaded_skills = request.state.get("loaded_skills", {})

        if phase == "discovery" or not loaded_skills:
            prompt_fragment = _DISCOVERY_PROMPT_FRAGMENT.format(
                registry=self._registry_text
            )
        else:
            lines = []
            for name, entry in loaded_skills.items():
                tool_names = entry.get("tool_names", [])
                desc = entry.get("description", "")
                lines.append(f"- **{name}**: {desc}  Tools: {tool_names}")
            prompt_fragment = _READY_PROMPT_FRAGMENT.format(
                loaded_summary="\n".join(lines)
            )

        current_system = ""
        if request.system_message:
            current_system = request.system_message.content

        new_request = request.override(
            system_message=SystemMessage(content=current_system + prompt_fragment)
        )

        skill_tools = get_all_loaded_skill_tools()
        if skill_tools:
            existing_tools = list(new_request.tools or [])
            existing_names = {
                t.name if isinstance(t, BaseTool) else t.get("name", "")
                for t in existing_tools
            }
            for t in skill_tools:
                if t.name not in existing_names:
                    existing_tools.append(t)
            new_request = new_request.override(tools=existing_tools)

        return await handler(new_request)

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)

        if not isinstance(result, ToolMessage):
            return result

        tool_name = request.tool_call.get("name", "")
        if tool_name not in ("load_skill", "load_skill_section"):
            return result

        try:
            payload = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return result

        skill_update = payload.get(SKILL_UPDATE_KEY)
        if skill_update is None:
            error_msg = payload.get("error", result.content)
            result.content = error_msg
            return result

        if not hasattr(result, "additional_kwargs") or result.additional_kwargs is None:
            result.additional_kwargs = {}
        result.additional_kwargs[SKILL_UPDATE_KEY] = skill_update
        result.content = payload.get("content", result.content)

        return result