from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


shared_cache = {}

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个缓存演示助手。
    """,
    cache=shared_cache,
)



query = {"messages": [{"role": "user", "content": "请用一句话介绍杭州"}]}

res1 = agent.invoke(query)
print("第一次调用:")
print(res1["messages"][-1].content)
print("cache 当前内容:", shared_cache)
print("-" * 80)

res2 = agent.invoke(query)
print("第二次调用:")
print(res2["messages"][-1].content)
print("cache 当前内容:", shared_cache)
