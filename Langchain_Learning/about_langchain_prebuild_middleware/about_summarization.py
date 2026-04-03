from pathlib import Path
import sys


if __package__ in {None, ""}:
    package_parent = Path(__file__).resolve().parents[2]
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))    # 将项目根目录添加到 sys.path 中

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from MapleClaw.src.model.llm import get_llm


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个乐于助人的助手。
    """,
    middleware=[
        SummarizationMiddleware(
            model=get_llm(),
            max_summary_length=4000,
            meseages_to_keep = 20,
            summary_prompt="")],
)
