from langchain.agents import create_agent
from langchain.tools import tool
from MapleClaw.src.model.llm import get_llm


@tool
def get_weather(city: str) -> str:
    """查询城市天气。"""
    return f"{city} 今天晴天，25度。"


@tool
def get_transport(city: str) -> str:
    """查询城市交通。"""
    return f"{city} 今天交通情况良好，没有事故与拥堵发生。"

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个个人助手。
    """,
    tools=[get_weather,get_transport],
    interrupt_before=["tools"],
)


for event in agent.stream(
    {"messages": [{"role": "user", "content": "杭州天气怎么样？,交通如何"}]},
    stream_mode="values",
):
    print(event)
    print("-" * 80)

####################
# query = {"messages": [{"role": "user", "content": "杭州天气怎么样？,交通如何"}]}
# res = agent.invoke(query)
# print(res)
# print("-" * 80)
# print(res["messages"][-1].content)