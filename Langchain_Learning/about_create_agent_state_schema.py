from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from MapleClaw.src.model.llm import get_llm


class CustomAgentState(AgentState):
    preference: str


@tool
def read_preference(runtime: ToolRuntime) -> str:
    """读取当前状态中的 preference。"""
    return f"当前记录的用户偏好是：{runtime.state['preference']}"


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个乐于助人的助手。
    如果用户问到偏好，就调用工具读取状态。
    """,
    tools=[read_preference],
    state_schema=CustomAgentState,
)


query = {
    "messages": [{"role": "user", "content": "我的偏好是什么？"}],
    "preference": "我喜欢简洁、直接的回答",
}

res = agent.invoke(query)
print(res)
print("-" * 80)
print(res["messages"][-1].content)
