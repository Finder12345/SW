from langchain.agents import create_agent

from MapleClaw.src.agent.state import AgentState

from MapleClaw.src.model.llm import get_llm
# 技能中间件
from MapleClaw.src.middleware.middleware_skills.middleware_skill import SkillMiddleware

# 基础工具
from MapleClaw.src.tools import ALL_BUILTIN_TOOLS



def build_agent():
    agent = create_agent(
        model=get_llm(),
        system_prompt="""
        You are a helpful assistant.
        """,
        tools=ALL_BUILTIN_TOOLS,
        middleware=[SkillMiddleware()],

        state_schema=AgentState
    )
    return agent


if __name__ == '__main__':
    agent = build_agent()
    ans = agent.invoke({"messages": [{"role": "user", "content": "北京天气如何？"}]})
    # 返回AI的回复即可，最后一个的回复
    print(ans["messages"][-1].content)
