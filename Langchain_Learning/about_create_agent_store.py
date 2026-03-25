from langchain.agents import create_agent
from langgraph.store.memory import InMemoryStore
from langchain.tools import tool, ToolRuntime
from MapleClaw.src.model.llm import get_llm


store = InMemoryStore()


@tool
def save_note(note: str, runtime: ToolRuntime) -> str:
    """保存一条笔记到 store。"""
    user_id = runtime.context.user_id
    store.put(("notes", user_id), note, {"text": note})
    return f"已为 {user_id} 保存笔记：{note}"


@tool
def read_notes(runtime: ToolRuntime) -> str:
    """读取当前用户在 store 中的笔记。"""
    user_id = runtime.context.user_id
    items = store.search(("notes", user_id))
    if not items:
        return "当前没有笔记"
    return "；".join(item.value["text"] for item in items)


class UserContext:
    def __init__(self, user_id: str):
        self.user_id = user_id


agent = create_agent(
    model=get_llm(),
    system_prompt="""
    你是一个笔记助手。
    当用户要求保存或读取笔记时，调用工具。
    """,
    tools=[save_note, read_notes],
    context_schema=UserContext,
    store=store,
)

context = UserContext(user_id="张三")

res1 = agent.invoke(
    {"messages": [{"role": "user", "content": "请帮我记住：周五下午开会"}]},
    context=context,
)
print("第一次调用:")
print(res1["messages"][-1].content)
print("-" * 80)

res2 = agent.invoke(
    {"messages": [{"role": "user", "content": "读取我保存过的笔记"}]},
    context=context,
)
print("第二次调用:")
print(res2["messages"][-1].content)
