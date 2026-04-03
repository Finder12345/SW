from langchain.agents import create_agent, AgentState
from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pathlib import Path
import sys

if __package__ in {None, ""}:
    package_parent = Path(__file__).resolve().parents[2]
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))

from MapleClaw.src.model.llm import get_llm


# ============================================================
# 1. 自定义 State：新增 times 字段
# ============================================================
class CustomAgentState(AgentState):
    preference: str
    times: int


# ============================================================
# 2. 工具本身：纯业务逻辑，不关心计数
# ============================================================
@tool
def read_preference(runtime: ToolRuntime) -> str:
    """读取当前状态中的 preference。"""
    return f"当前记录的用户偏好是：{runtime.state['preference']}"


# ============================================================
# 3. 中间件：在 wrap_tool_call 中拦截每次 tool 执行，累加 times
# ============================================================
class ToolCallCounter(AgentMiddleware):
    """通过 wrap_tool_call 拦截 tool 执行，每次调用后累加 state.times。"""

    # 声明该中间件需要的额外 state 字段
    state_schema = CustomAgentState

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        # 1. 先正常执行 tool，拿到原始结果
        result = handler(request)  

        # 2. 读取当前 times
        old_times = request.state.get("times", 0)
        new_times = old_times + 1
        print(f"  [ToolCallCounter 中间件] tool={request.tool_call['name']}, times: {old_times} -> {new_times}")

        # 3. 通过 Command 把 tool 结果 + state 更新一起返回
        #    这是唯一能让 state 变化生效的方式
        if isinstance(result, ToolMessage):
            return Command(
                update={
                    "messages": [result],
                    "times": new_times,
                }
            )
        # 如果 tool 本身就返回了 Command，则合并 times 更新
        elif isinstance(result, Command):
            update = dict(result.update) if result.update else {}
            update["times"] = new_times
            return Command(update=update, goto=result.goto)

        return result


# ============================================================
# 4. 创建 agent
# ============================================================
agent = create_agent(
    model=get_llm(),
    system_prompt="你是一个乐于助人的助手。如果用户问到偏好，就调用 read_preference 工具。",
    tools=[read_preference],
    middleware=[ToolCallCounter()],
    state_schema=CustomAgentState,
)


# ============================================================
# 实验 1：单次 invoke，观察 times 是否被中间件更新
# ============================================================
print("=" * 80)
print("实验 1：单次 invoke，中间件 wrap_tool_call 是否成功更新 times")
print("=" * 80)

res1 = agent.invoke({
    "messages": [{"role": "user", "content": "我的偏好是什么？"}],
    "preference": "我喜欢简洁、直接的回答",
    "times": 0,
})
print(f"[实验1] 返回 state.times = {res1.get('times', 'N/A')}")
print(f"[实验1] assistant: {res1['messages'][-1].content}")


# ============================================================
# 实验 2：多次 invoke，手动衔接 times
# ============================================================
print()
print("=" * 80)
print("实验 2：多次 invoke，手动衔接 times，验证累加效果")
print("=" * 80)

state_times = 0
for i in range(3):
    res = agent.invoke({
        "messages": [{"role": "user", "content": "我的偏好是什么？"}],
        "preference": "简洁",
        "times": state_times,
    })
    state_times = res.get("times", 0)
    print(f"[第 {i+1} 次 invoke] 返回 state.times = {state_times}")

# ============================================================
# 结论
# ============================================================
print()
print("=" * 80)
print("结论：")
print("=" * 80)
print("""
选择 wrap_tool_call 的原因：

┌─────────────────┬──────────────────────────────────────────────┐
│ 钩子            │ 时机 & 粒度                                   │
├─────────────────┼──────────────────────────────────────────────┤
│ before_model    │ 每次调 LLM 前触发（不是调 tool 时）            │
│                 │ → 不知道 LLM 会不会调 tool，也不知道调哪个       │
│                 │ → ❌ 不适合                                    │
├─────────────────┼──────────────────────────────────────────────┤
│ after_model     │ 每次 LLM 返回后触发                            │
│                 │ → 能看到 tool_calls，但 tool 还没执行           │
│                 │ → 如果 tool 执行失败了也会被计数 ❌              │
├─────────────────┼──────────────────────────────────────────────┤
│ wrap_tool_call  │ 包裹每一次 tool 执行                           │
│ ✅ 最佳选择     │ → 精确到每个 tool call                         │
│                 │ → 可以在执行前/后都插入逻辑                     │
│                 │ → 能拿到 request.tool_call["name"] 区分工具    │
│                 │ → 能拿到执行结果判断成功/失败再决定是否计数      │
│                 │ → 通过 Command(update=...) 回写 state          │
├─────────────────┼──────────────────────────────────────────────┤
│ wrap_model_call │ 包裹 LLM 调用，不是 tool 调用 ❌               │
└─────────────────┴──────────────────────────────────────────────┘

核心理由：
1. 语义精确 —— "每次调用工具时计数" → wrap_tool_call 就是为此设计的
2. 解耦彻底 —— tool 只写业务逻辑，计数完全由中间件处理
3. 可扩展 —— 可以按 tool name 区分、按成功/失败过滤
4. 能回写 state —— 通过返回 Command(update=...) 正式更新 graph state
""")
