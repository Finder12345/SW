from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个调试演示助手。
    """,
    debug=True,
)

res = agent.invoke(
    {"messages": [{"role": "user", "content": "请简单介绍一下你自己"}]}
)
print(res)
