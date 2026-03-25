from langchain.agents import create_agent
from langchain.tools import tool
from MapleClaw.src.model.llm import get_llm


@tool
def get_weather(city: str) -> str:
    """查询城市天气。"""
    return f"{city} 今天晴天，25度。"


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个天气助手，需要先调用工具再回答。
    """,
    tools=[get_weather],
    interrupt_after=["tools"],
)


for event in agent.stream(
    {"messages": [{"role": "user", "content": "杭州天气怎么样？"}]},
    stream_mode="values",
):
    print(event)
    print("-" * 80)
