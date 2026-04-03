from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个带名字的 agent。
    """,
    name="teaching_agent",
)

print(agent)
print("agent name 已设置为 teaching_agent")
