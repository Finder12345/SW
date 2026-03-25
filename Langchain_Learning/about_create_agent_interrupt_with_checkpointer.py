from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from MapleClaw.src.model.llm import get_llm


@tool
def get_weather(city: str) -> str:
    """查询城市天气。"""
    return f"{city} 今天晴天，25度。"


checkpointer = InMemorySaver()

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个天气助手。
    当用户询问天气时，先调用工具。
    """,
    tools=[get_weather],
    checkpointer=checkpointer,
    interrupt_before=["tools"],
)

config = {"configurable": {"thread_id": "interrupt-demo-1"}}
query = {"messages": [{"role": "user", "content": "杭州天气怎么样？"}]}

res = agent.invoke(query,config=config)
print(res["messages"][-1].content)
print("-" * 80)

res2 = agent.invoke(None, config=config)
print("第2次:", res2["messages"][-1].content)
print("消息数量:", len(res2["messages"]))
print("-" * 80)
res3 = agent.invoke(None, config=config)
print("第3次:", res3["messages"][-1].content)
print("消息数量:", len(res3["messages"]))
print("-" * 80)
# 你会发现 res2 和 res3 的内容和消息数量完全一样
res = agent.invoke(None,config=config)
print(res["messages"][-1].content)
quit()

print("第一次执行：会在 tools 节点之前暂停")
# agent.stream()是一个生成器函数，返回一个迭代器
for event in agent.stream(query, config=config, stream_mode="updates"):
    print(event)
    print("-" * 80)

# print("第二次执行：基于同一个 thread_id 恢复继续")
# for event in agent.stream(None, config=config, stream_mode="updates"):
#     print(event)
#     print("-" * 80)

res = agent.invoke(config=config)
print(res.messages[-1].content)
