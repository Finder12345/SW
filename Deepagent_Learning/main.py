from deepagents import create_deep_agent
from MapleClaw.src.model.llm import get_llm
from deepagents.middleware.skills import SkillsMiddleware


def build__agent():
    agent = create_deep_agent(
        model=get_llm(),
        system_prompt="""
        You are a helpful assistant.
        """,
        # tools=ALL_BUILTIN_TOOLS,
    )
    return agent
