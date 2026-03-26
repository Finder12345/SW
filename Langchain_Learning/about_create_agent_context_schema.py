from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from MapleClaw.src.model.llm import get_llm


@dataclass
class CustomContext:
    user_id: str
    city: str


@tool
def get_user_profile(runtime: ToolRuntime[CustomContext]) -> str:
    """读取 context 中的用户资料。"""
    return f"当前用户ID是 {runtime.context.user_id}，所在城市是 {runtime.context.city}"


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个乐于助人的助手。
    如果需要用户资料，就调用工具读取 context。
    """,
    tools=[get_user_profile],
    context_schema=CustomContext,
)


query = {
    "messages": [{"role": "user", "content": "请告诉我当前用户资料。先调用工具。"}]
}

res = agent.invoke(query, context=CustomContext(user_id="张三", city="杭州"))
print(res)
print("-" * 80)
print(res["messages"][-1].content)
