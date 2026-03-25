from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个乐于助人的助手。
    """,
)


query = {
    "messages": [{"role": "user", "content": "请用一句话介绍你自己"}]
}

res = agent.invoke(query)
print(res)
print("-" * 80)
print(res["messages"][-1].content)
