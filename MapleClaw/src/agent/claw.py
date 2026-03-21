from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


def build_agent():
    agent = create_agent(
        model=get_llm(),
        system_prompt="""
        You are a helpful assistant.
        """,
        tools=[],
        middleware=[],
    )
    return agent


if __name__ == '__main__':
    agent = build_agent()
    ans = agent.invoke({"messages": [{"role": "user", "content": "旧金山天气如何？"}]})
    # 返回AI的回复即可，最后一个的回复
    print(ans["messages"][-1].content)
