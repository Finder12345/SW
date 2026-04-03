from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from MapleClaw.src.model.llm import get_llm


checkpointer = InMemorySaver()

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个有记忆的助手。
    """,
    checkpointer=checkpointer,
)

config = {"configurable": {"thread_id": "orange-thread-1"}}


res1 = agent.invoke(
    {"messages": [{"role": "user", "content": "我叫张三，请记住。"}]},
    config=config,
)
print("第一次调用:")
print(res1["messages"][-1].content)
print("-" * 80)

res2 = agent.invoke(
    {"messages": [{"role": "user", "content": "我刚才叫什么名字？"}]},
    config=config,
)
print("第二次调用:")
print(res2["messages"][-1].content)
