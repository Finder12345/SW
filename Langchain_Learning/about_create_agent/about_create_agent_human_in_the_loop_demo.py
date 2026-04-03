from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from MapleClaw.src.model.llm import get_llm


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件。"""
    return f"邮件已发送给 {to}，主题是《{subject}》"


checkpointer = InMemorySaver()

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个办公助手。
    当用户要求发邮件时，请先调用工具。
    """,
    tools=[send_email],
    checkpointer=checkpointer,
    interrupt_before=["tools"],
)

config = {"configurable": {"thread_id": "human-loop-demo-1"}}
query = {
    "messages": [
        {
            "role": "user",
            "content": "请给 boss@example.com 发邮件，主题是 项目进展，正文是 今天已经完成第一阶段开发。",
        }
    ]
}

print("第一阶段：agent 先执行，到 tools 前暂停，等待人工审核")
for event in agent.stream(query, config=config, stream_mode="updates"):
    print(event)
    print("-" * 80)
approved = input("请输入人工审核结果（y/n）：")=="y"
if approved:
    print("第二阶段：人工审核通过，恢复执行")
    for event in agent.stream(None, config=config, stream_mode="updates"):
        print(event)
        print("-" * 80)
else:
    print("人工审核未通过，不继续执行")
