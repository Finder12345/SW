from langchain.agents import create_agent
from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime
from MapleClaw.src.model.llm import get_llm
from langchain.agents import AgentState


class CustomAgentState(AgentState):
    """自定义运行时状态。"""
    preference: str  # 偏好


@dataclass
class CustomContext:
    user_id:str

@tool
def get_user_location(runtime: ToolRuntime[CustomContext]) -> str:
    """根据用户 ID 获取用户信息。"""
    user_id = runtime.context.user_id
    return "Florida" if user_id == "1" else "SF"


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    You are a helpful assistant.
    """,
    tools=[get_user_location],
    middleware=[],
    state_schema=CustomAgentState,
    context_schema=CustomContext,
)

query = {
    "messages": [{"role": "user", "content": "我是谁"}]}

res = agent.invoke(query,context=CustomContext(user_id="小王"))
print(res["messages"][-1].content)