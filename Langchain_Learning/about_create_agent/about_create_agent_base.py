from pathlib import Path
import sys


if __package__ in {None, ""}:
    package_parent = Path(__file__).resolve().parents[2]
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))    # 将项目根目录添加到 sys.path 中

from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm
from langchain.tools import tool
from langgraph.runtime import Runtime



@tool
def send_email(to: str, subject: str, body: str,runtime:Runtime) -> str:
    """发送邮件。"""
    return f"邮件已发送给 {to}，主题是《{subject}》"


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个乐于助人的助手。
    """,
    
)


query = {
    "messages": [{"role": "user", "content": "北京天气如何"}]
}

res = agent.invoke(query)
print(res)
print("-" * 80)
print(res["messages"][-1].content)
