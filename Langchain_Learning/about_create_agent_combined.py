from pydantic import BaseModel, Field
from dataclasses import dataclass
from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from MapleClaw.src.model.llm import get_llm


class AnswerCard(BaseModel):
    topic: str = Field(description="主题")
    summary: str = Field(description="总结")


class CustomAgentState(AgentState):
    preference: str


@dataclass
class CustomContext:
    user_id: str


@tool

def read_runtime_info(runtime: ToolRuntime[CustomContext]) -> str:
    """同时读取 state 和 context。"""
    return (
        f"user_id={runtime.context.user_id}；"
        f"preference={runtime.state['preference']}"
    )


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个总结助手。
    先调用工具读取运行时信息，再输出结构化结果。
    """,
    tools=[read_runtime_info],
    state_schema=CustomAgentState,
    context_schema=CustomContext,
    response_format=AnswerCard,
)


query = {
    "messages": [{"role": "user", "content": "总结一下当前运行时信息"}],
    "preference": "偏好分点表达",
}

res = agent.invoke(query, context=CustomContext(user_id="张三"))
print(res)
print("-" * 80)
print("structured_response:", res.get("structured_response"))
print("messages 最后一条:", res["messages"][-1].content)
