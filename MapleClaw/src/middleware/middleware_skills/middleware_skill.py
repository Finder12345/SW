"""技能中间件：遵循 skills 规范的 progressive disclosure。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.runtime import Runtime

from MapleClaw.src.agent.state import AgentState, SkillMetadata
from MapleClaw.src.middleware.middleware_skills.utils import discover_skills, format_skills_list

logger = logging.getLogger(__name__)


SKILLS_SYSTEM_PROMPT = """

## Skills System

You have access to a skills library that provides specialized capabilities.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills:**

1. Recognize when a skill matches the user's request.
2. Read the skill's `SKILL.md` file when you need full instructions.
3. Follow the skill instructions using the tools already available in this runtime.
4. If a skill lists requirements that are unavailable, explain the limitation instead of pretending the skill can run.

Use skills as instruction artifacts, not as automatically loaded code.
"""


class SkillMiddleware(AgentMiddleware[AgentState, Any]):
    state_schema = AgentState

    def __init__(self, sources: list[str | Path]) -> None:
        self.sources = [Path(s) for s in sources]

    @property
    def name(self) -> str:
        return "SkillMiddleware"

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if "skills_metadata" in state:
            return None

        all_skills: dict[str, SkillMetadata] = {}
        for source_dir in self.sources:
            for skill in discover_skills(source_dir):
                all_skills[skill.metadata["name"]] = skill.metadata

        metadatas = list(all_skills.values())
        logger.info(
            "[SkillMiddleware] loaded %d skill(s) from %d source(s)",
            len(metadatas),
            len(self.sources),
        )
        return {"skills_metadata": metadatas}

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        return handler(self._inject_prompt(request))

    def before_model(self, state, runtime):
        return None

    def after_model(self, state, runtime):
        return None

    def after_agent(self, state, runtime):
        return None

    def wrap_tool_call(self, request, handler):
        return handler(request)

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    async def awrap_model_call(self, request, handler):
        return await handler(self._inject_prompt(request))

    async def abefore_model(self, state, runtime):
        return None

    async def aafter_model(self, state, runtime):
        return None

    async def aafter_agent(self, state, runtime):
        return None

    async def awrap_tool_call(self, request, handler):
        return await handler(request)

    def _inject_prompt(self, request: ModelRequest) -> ModelRequest:
        skills_metadata: list[SkillMetadata] = request.state.get("skills_metadata", [])
        skills_section = SKILLS_SYSTEM_PROMPT.format(
            skills_locations=self._format_locations(),
            skills_list=format_skills_list(skills_metadata),
        )

        system_message = request.system_message
        if system_message is None:
            return request.override(system_message=skills_section)

        return request.override(system_message=f"{system_message}\n{skills_section}")

    def _format_locations(self) -> str:
        lines: list[str] = []
        for i, source in enumerate(self.sources):
            label = source.name.capitalize()
            suffix = " (higher priority)" if i == len(self.sources) - 1 and len(self.sources) > 1 else ""
            lines.append(f"**{label} Skills**: `{source.resolve()}`{suffix}")
        return "\n".join(lines)
