from pydantic import BaseModel, Field
from langchain.agents import create_agent
from MapleClaw.src.model.llm import get_llm


class TravelPlan(BaseModel):
    city: str = Field(description="目标城市")
    days: int = Field(description="旅行天数")
    must_try_food: list[str] = Field(description="建议尝试的食物")

agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个旅行规划助手。
    请严格按照结构化格式输出。
    """,
    response_format=TravelPlan,
)


query = {
    "messages": [{"role": "user", "content": "帮我做一个去成都玩3天的简单计划"}]
}

res = agent.invoke(query)
print(res)
print("-" * 80)
print("structured_response:", res.get("structured_response"))
# structured_response: city='成都' days=3
# must_try_food=['火锅', '串串香', '担担面', '龙抄手', '钟水饺', '夫妻肺片', '兔头', '甜水面']
print("messages 最后一条:", res["messages"][-1].content)
# messages 最后一条: {"city":"成都","days":3,"must_try_food":
# ["火锅","串串香","担担面","龙抄手","钟水饺","夫妻肺片","兔头","甜水面"]}

