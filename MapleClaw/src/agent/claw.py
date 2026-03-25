from langchain.agents import create_agent

from MapleClaw.src.model.llm import get_llm
from MapleClaw.src.middleware.middleware_skills.middleware_skill import SkillMiddleware
from MapleClaw.src.tools import ALL_BUILTIN_TOOLS

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def build_agent():
    skills_dir = r"D:\CODE\MYSELF\SW\MapleClaw\skills"

    agent = create_agent(
        model=get_llm(),
        system_prompt="""
        You are a helpful assistant.
        When a skill is relevant, use it as guidance and read its SKILL.md when needed.
        """,
        tools=ALL_BUILTIN_TOOLS,
        middleware=[SkillMiddleware([skills_dir])],
    )
    return agent


if __name__ == '__main__':
    agent = build_agent()
    ans = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请先告诉我当前已加载了哪些skills，然后再回答：武汉接下来三天的天气如何？",
                }
            ]
        }
    )
    print(ans["messages"][-1].content)
