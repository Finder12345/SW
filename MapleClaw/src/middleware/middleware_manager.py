"""
middleware_manager.py
=====================
职责：
1. 定义 AgentState — 中间件之间的唯一通信契约
2. 组装中间件列表，传入 create_agent

后续任何中间件需要共享数据，只需在 SkillAgentState 里加字段。
各中间件自己的内部逻辑、工具函数，各自放在自己的目录里。
"""

from pathlib import Path

from langchain.agents import create_agent, AgentState


# ============================================================
#  共享 State — 中间件之间的通信契约
# ============================================================

class SkillAgentState(AgentState):
    """
    在基础 AgentState（messages）上扩展的字段。
    所有中间件通过这个 state 读写数据，互相不直接依赖。

    后续要加共享数据，只需在这里补字段。
    """
    loaded_skills: list[str] = []              # 当前已加载的技能名称
    skill_load_history: list[str] = []         # 本会话加载过的所有技能
    loaded_skill_paths: dict[str, str] = {}    # 技能名称 → SKILL.md 绝对路径


# ============================================================
#  默认路径
# ============================================================

WORKSPACE = Path.home() / ".myagent" / "workspace"
SKILL_DIR = WORKSPACE / "skills"


# ============================================================
#  组装
# ============================================================

def build_agent(
    model: str = "anthropic:claude-sonnet-4-5-20250929",
    tools: list | None = None,
    workspace: Path = WORKSPACE,
    skill_dir: Path = SKILL_DIR,
    core_prompt: str | None = None,
    max_concurrent_skills: int = 2,
    sticky_skills: bool = True,
    max_skill_tokens: int = 6000,
):
    """
    组装 agent，接入两个独立中间件。

    执行顺序保证：
      skill_mw.before_model  →  写 state.loaded_skills / loaded_skill_paths
      prompt_mw.wrap_model_call  →  读 state，组装 system_message
    """
    # 延迟导入，避免循环引用
    from middleware_skills.middleware_skill import SkillMiddleware
    from middleware_prompt.middleware_prompt import PromptMiddleware

    skill_mw = SkillMiddleware(
        skill_dir=skill_dir,
        max_concurrent=max_concurrent_skills,
        sticky=sticky_skills,
    )

    prompt_mw = PromptMiddleware(
        workspace=workspace,
        core_prompt=core_prompt,
        max_skill_tokens=max_skill_tokens,
    )

    return create_agent(
        model=model,
        tools=tools or [],
        middleware=[skill_mw, prompt_mw],
    )