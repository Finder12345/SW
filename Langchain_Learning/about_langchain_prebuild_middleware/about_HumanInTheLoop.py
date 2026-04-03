"""
HumanInTheLoopMiddleware 全面体验示例
=====================================

本文件演示了 LangChain 内置 HumanInTheLoopMiddleware 的各种用法：
1. 工具执行前需要人工批准 (approve / reject)
2. 工具执行前允许人工编辑参数 (edit)
3. 某些工具跳过人工审核 (False)
4. 组合多种 interrupt_on 策略

核心概念:
- HumanInTheLoopMiddleware 会在指定工具执行前暂停(interrupt) agent
- 用户可以选择: approve(批准) / edit(修改参数) / reject(拒绝)
- 需要 checkpointer 来保存中断时的状态，以便恢复执行
- 使用 agent.stream(None, config) 来恢复被中断的执行
"""
from pathlib import Path
import sys


if __package__ in {None, ""}:
    package_parent = Path(__file__).resolve().parents[2]
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage, ToolMessage
from MapleClaw.src.model.llm import get_llm


# ============================================================
# 第一步：定义各种工具，模拟不同风险等级的操作
# ============================================================

@tool
def search_web(query: str) -> str:
    """搜索网页信息。这是一个低风险的只读操作。"""
    return f"搜索结果：关于「{query}」的信息 —— 这是一个模拟的搜索结果，包含了相关的网页内容摘要。"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件给指定收件人。这是一个高风险操作，邮件发出后无法撤回。"""
    return f"邮件已成功发送！\n  收件人: {to}\n  主题: {subject}\n  正文: {body}"


@tool
def delete_file(file_path: str) -> str:
    """删除指定路径的文件。这是一个危险操作，文件删除后无法恢复。"""
    return f"文件 '{file_path}' 已被永久删除。"


@tool
def query_database(sql: str) -> str:
    """执行 SQL 查询语句。查询操作相对安全，但需要注意 SQL 注入。"""
    return f"SQL 查询执行成功：\n  语句: {sql}\n  结果: [模拟数据] 共返回 5 条记录"


@tool
def transfer_money(from_account: str, to_account: str, amount: float) -> str:
    """执行转账操作。这是一个极高风险操作，涉及资金变动。"""
    return f"转账成功！从 {from_account} 向 {to_account} 转账 {amount} 元。"


# ============================================================
# 第二步：辅助函数 —— 处理人工审核逻辑
# ============================================================

def handle_human_review(agent, config, tool_calls):
    """
    处理人工审核流程：
    - 展示待执行的工具调用信息
    - 让用户选择 approve / edit / reject
    - 根据用户选择执行对应操作
    """
    print("\n" + "=" * 60)
    print("  🔔 人工审核中断 —— 以下工具调用等待您的审核")
    print("=" * 60)

    for i, tc in enumerate(tool_calls):
        print(f"\n  📌 工具调用 [{i + 1}]:")
        print(f"     工具名称: {tc['name']}")
        print(f"     调用参数: {tc['args']}")
        if 'id' in tc:
            print(f"     调用 ID:  {tc['id']}")

    print("\n" + "-" * 60)
    print("  请选择操作:")
    print("    [a] approve  - 批准执行")
    print("    [e] edit     - 修改参数后执行")
    print("    [r] reject   - 拒绝执行")
    print("-" * 60)

    choice = input("  您的选择 (a/e/r): ").strip().lower()

    if choice == "a":
        # 批准：直接恢复执行
        print("\n  ✅ 已批准，恢复执行...")
        return resume_agent(agent, config)

    elif choice == "e":
        # 编辑：让用户修改工具参数
        print("\n  ✏️  进入编辑模式...")
        return edit_and_resume(agent, config, tool_calls)

    elif choice == "r":
        # 拒绝：向 agent 注入一条拒绝消息，让它知道工具被用户否决
        print("\n  ❌ 已拒绝执行。")
        return reject_and_resume(agent, config, tool_calls)

    else:
        print("\n  ⚠️  无效选择，默认拒绝。")
        return reject_and_resume(agent, config, tool_calls)


def resume_agent(agent, config):
    """批准后恢复 agent 执行"""
    results = []
    for event in agent.stream(None, config=config, stream_mode="updates"):
        results.append(event)
        print_event(event)
    return results


def edit_and_resume(agent, config, tool_calls):
    """
    编辑工具参数后恢复执行。
    通过 update_state 修改 agent 状态中的工具调用参数。
    """
    # 获取当前状态
    state = agent.get_state(config)
    last_message = state.values["messages"][-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        print("  ⚠️  当前状态没有待执行的工具调用，无法编辑。")
        return resume_agent(agent, config)

    new_tool_calls = []
    for tc in last_message.tool_calls:
        print(f"\n  正在编辑工具「{tc['name']}」的参数:")
        new_args = {}
        for key, value in tc["args"].items():
            new_value = input(f"    {key} (当前值: {value}, 直接回车保持不变): ").strip()
            new_args[key] = new_value if new_value else value
        new_tool_calls.append({**tc, "args": new_args})

    # 用修改后的工具调用更新 agent 状态
    edited_message = AIMessage(
        content=last_message.content,
        tool_calls=new_tool_calls,
    )
    agent.update_state(config, {"messages": [edited_message]})

    print("\n  ✅ 参数已修改，恢复执行...")
    return resume_agent(agent, config)


def reject_and_resume(agent, config, tool_calls):
    """
    拒绝工具执行。
    为每个被拒绝的工具调用注入一条 ToolMessage 告知 agent 该操作被用户否决，
    然后恢复执行让 agent 做出适当回应。
    """
    rejection_messages = []
    for tc in tool_calls:
        rejection_messages.append(
            ToolMessage(
                content=f"[用户拒绝] 工具「{tc['name']}」的执行被用户否决。请尊重用户的决定，不要重复调用。",
                tool_call_id=tc["id"],
            )
        )
    # 注入拒绝消息并恢复执行
    agent.update_state(config, {"messages": rejection_messages})

    results = []
    for event in agent.stream(None, config=config, stream_mode="updates"):
        results.append(event)
        print_event(event)
    return results


def print_event(event):
    """美化打印 stream 事件"""
    for node_name, data in event.items():
        print(f"\n  📍 节点: {node_name}")
        # data 可能为 None（如 HumanInTheLoopMiddleware 的中间节点）
        if data is None:
            continue
        if not isinstance(data, dict):
            print(f"     {data}")
            continue
        if "messages" in data:
            for msg in data["messages"]:
                role = type(msg).__name__
                content = getattr(msg, "content", "")
                if content:
                    # 截取前 200 字符展示
                    display = content[:200] + ("..." if len(content) > 200 else "")
                    print(f"     [{role}] {display}")
                # 如果是 AI 消息且包含工具调用
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"     🔧 工具调用: {tc['name']}({tc['args']})")


# ============================================================
# 第三步：获取 agent 中断后的待审核工具调用
# ============================================================

def get_pending_tool_calls(agent, config):
    """从 agent 状态中提取被中断的工具调用"""
    state = agent.get_state(config)
    messages = state.values.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            return last_msg.tool_calls
    return []


# ============================================================
# 场景一：高风险工具需审批，低风险工具自动放行
# ============================================================

def demo_selective_approval():
    """
    演示场景：
    - send_email, delete_file, transfer_money → 需要人工批准 (approve/edit/reject)
    - search_web, query_database → 自动执行，不需要审批 (False)
    """
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║   场景一：选择性审批 —— 高风险操作需审批，低风险自动放行   ║")
    print("╚" + "═" * 58 + "╝")

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=get_llm(),
        system_prompt="""
你是一个全能办公助手，可以帮用户搜索信息、发邮件、删文件、查数据库、转账。
请根据用户需求调用合适的工具。回答请使用中文。
""",
        tools=[search_web, send_email, delete_file, query_database, transfer_money],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    # 高风险工具：需要人工审核
                    "send_email": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                    },
                    "delete_file": {
                        "allowed_decisions": ["approve", "reject"],  # 删除文件不允许编辑，只能批准或拒绝
                    },
                    "transfer_money": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                    },
                    # 低风险工具：跳过审核，直接执行
                    "search_web": False,
                    "query_database": False,
                },
            ),
        ],
    )

    config = {"configurable": {"thread_id": "demo-selective-1"}}

    # --- 测试 1：低风险操作（搜索）应该直接执行 ---
    print("\n📝 测试 1：低风险操作 —— 搜索（应自动执行，不中断）")
    print("-" * 50)
    query1 = {"messages": [{"role": "user", "content": "帮我搜索一下 LangChain middleware 的最新文档"}]}

    for event in agent.stream(query1, config=config, stream_mode="updates"):
        print_event(event)

    # --- 测试 2：高风险操作（发邮件）应该中断等待审批 ---
    config2 = {"configurable": {"thread_id": "demo-selective-2"}}
    print("\n\n📝 测试 2：高风险操作 —— 发邮件（应中断等待审批）")
    print("-" * 50)
    query2 = {
        "messages": [
            {
                "role": "user",
                "content": "请给 zhangsan@company.com 发一封邮件，主题是「项目周报」，内容是「本周完成了 HumanInTheLoop 中间件的学习和实践。」",
            }
        ]
    }

    for event in agent.stream(query2, config=config2, stream_mode="updates"):
        print_event(event)

    # 检查是否有被中断的工具调用
    pending = get_pending_tool_calls(agent, config2)
    if pending:
        handle_human_review(agent, config2, pending)
    else:
        print("  ℹ️  没有待审核的工具调用。")


# ============================================================
# 场景二：编辑工具参数
# ============================================================

def demo_edit_tool_args():
    """
    演示场景：
    - 转账操作中断后，用户可以修改转账金额、收款账户等参数
    - 体验 edit 功能的完整流程
    """
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║   场景二：编辑工具参数 —— 转账前修改金额和账户        ║")
    print("╚" + "═" * 58 + "╝")

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=get_llm(),
        system_prompt="""
你是一个银行助手，可以帮用户执行转账操作。
当用户要求转账时，请调用 transfer_money 工具。回答请使用中文。
""",
        tools=[transfer_money],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "transfer_money": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                    },
                },
            ),
        ],
    )

    config = {"configurable": {"thread_id": "demo-edit-1"}}
    query = {
        "messages": [
            {
                "role": "user",
                "content": "帮我从账户 A001 向账户 B002 转账 5000 元。",
            }
        ]
    }

    print("\n📝 Agent 正在处理转账请求...")
    print("-" * 50)

    for event in agent.stream(query, config=config, stream_mode="updates"):
        print_event(event)

    pending = get_pending_tool_calls(agent, config)
    if pending:
        print("\n💡 提示：您可以选择 [e] 来修改转账参数（如金额、账户）")
        handle_human_review(agent, config, pending)


# ============================================================
# 场景三：拒绝危险操作
# ============================================================

def demo_reject_dangerous():
    """
    演示场景：
    - 删除文件操作被用户拒绝
    - Agent 收到拒绝通知后优雅地回应
    """
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║   场景三：拒绝危险操作 —— 阻止文件删除               ║")
    print("╚" + "═" * 58 + "╝")

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=get_llm(),
        system_prompt="""
你是一个文件管理助手，可以帮用户删除文件。
当用户要求删除文件时，请调用 delete_file 工具。
如果用户拒绝了操作，请尊重用户的决定并给出友好回应。回答请使用中文。
""",
        tools=[delete_file],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "delete_file": {
                        "allowed_decisions": ["approve", "reject"],
                    },
                },
            ),
        ],
    )

    config = {"configurable": {"thread_id": "demo-reject-1"}}
    query = {
        "messages": [
            {
                "role": "user",
                "content": "请删除 /important/production_data.db 这个文件。",
            }
        ]
    }

    print("\n📝 Agent 正在处理删除请求...")
    print("-" * 50)

    for event in agent.stream(query, config=config, stream_mode="updates"):
        print_event(event)

    pending = get_pending_tool_calls(agent, config)
    if pending:
        print("\n💡 提示：这是一个危险操作，建议选择 [r] 拒绝！")
        handle_human_review(agent, config, pending)


# ============================================================
# 场景四：连续多轮对话中的人工审核
# ============================================================

def demo_multi_turn():
    """
    演示场景：
    - 多轮对话中，每次高风险操作都会触发审核
    - 展示 checkpointer 如何跨轮次保持状态
    """
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║   场景四：多轮对话 —— 连续交互中的人工审核            ║")
    print("╚" + "═" * 58 + "╝")

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=get_llm(),
        system_prompt="""
你是一个全能助手，可以搜索网页、发邮件和查询数据库。
根据用户的需求选择合适的工具。每次只需调用一个最合适的工具。回答请使用中文。
""",
        tools=[search_web, send_email, query_database],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "send_email": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                    },
                    "search_web": False,
                    "query_database": False,
                },
            ),
        ],
    )

    config = {"configurable": {"thread_id": "demo-multi-turn-1"}}

    # 第一轮：安全操作
    print("\n📝 第 1 轮：搜索操作（安全，自动执行）")
    print("-" * 50)
    query1 = {"messages": [{"role": "user", "content": "帮我搜索一下 Python 异步编程的最佳实践"}]}
    for event in agent.stream(query1, config=config, stream_mode="updates"):
        print_event(event)

    # 第二轮：需要审批的操作
    print("\n\n📝 第 2 轮：发邮件操作（需要审批）")
    print("-" * 50)
    query2 = {
        "messages": [
            {
                "role": "user",
                "content": "把刚才搜索到的内容通过邮件发给 team@company.com，主题是「Python异步编程学习资料」",
            }
        ]
    }
    for event in agent.stream(query2, config=config, stream_mode="updates"):
        print_event(event)

    pending = get_pending_tool_calls(agent, config)
    if pending:
        handle_human_review(agent, config, pending)

    # 第三轮：继续对话
    print("\n\n📝 第 3 轮：继续对话（查询数据库，安全操作）")
    print("-" * 50)
    query3 = {"messages": [{"role": "user", "content": "帮我查一下数据库里上个月的销售数据"}]}
    for event in agent.stream(query3, config=config, stream_mode="updates"):
        print_event(event)


# ============================================================
# 主菜单
# ============================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          HumanInTheLoopMiddleware 全面体验                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  本程序演示 LangChain HumanInTheLoopMiddleware 的各种场景：  ║
║                                                              ║
║  [1] 选择性审批 —— 高风险操作需审批，低风险自动放行          ║
║  [2] 编辑工具参数 —— 转账前修改金额和账户                    ║
║  [3] 拒绝危险操作 —— 阻止文件删除                            ║
║  [4] 多轮对话 —— 连续交互中的人工审核                        ║
║  [5] 运行所有场景                                            ║
║  [q] 退出                                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    demos = {
        "1": ("选择性审批", demo_selective_approval),
        "2": ("编辑工具参数", demo_edit_tool_args),
        "3": ("拒绝危险操作", demo_reject_dangerous),
        "4": ("多轮对话", demo_multi_turn),
    }

    while True:
        choice = input("\n请选择场景 (1-5, q退出): ").strip().lower()

        if choice == "q":
            print("\n👋 再见！")
            break
        elif choice == "5":
            for key in ["1", "2", "3", "4"]:
                name, func = demos[key]
                print(f"\n{'🚀' * 20}")
                print(f"  正在运行：{name}")
                print(f"{'🚀' * 20}")
                func()
        elif choice in demos:
            name, func = demos[choice]
            func()
        else:
            print("  ⚠️  无效选择，请输入 1-5 或 q。")


if __name__ == "__main__":
    main()
