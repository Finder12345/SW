# HumanInTheLoopMiddleware 详解

> LangChain 内置中间件，用于在 Agent 执行工具之前暂停（interrupt），交由人类审核后再决定是否继续。

---

## 目录

1. [它是什么](#1-它是什么)
2. [它能解决什么问题（用途）](#2-它能解决什么问题用途)
3. [前置依赖](#3-前置依赖)
4. [基本用法](#4-基本用法)
5. [参数详解](#5-参数详解)
6. [三种人工决策详解](#6-三种人工决策详解)
7. [完整执行流程图](#7-完整执行流程图)
8. [恢复执行的三种方式](#8-恢复执行的三种方式)
9. [实战配置模式](#9-实战配置模式)
10. [与 create_agent 的 interrupt_before 的区别](#10-与-create_agent-的-interrupt_before-的区别)
11. [注意事项与踩坑记录](#11-注意事项与踩坑记录)
12. [完整代码参考](#12-完整代码参考)

---

## 1. 它是什么

`HumanInTheLoopMiddleware` 是 LangChain `create_agent` 的一个**内置中间件**（middleware），导入路径：

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware
```

它的核心作用是：**在 Agent 决定调用某个工具之后、工具实际执行之前**，暂停（interrupt）整个 Agent 的执行流程，把控制权交给人类，让人类决定：

- **approve**（批准）—— 确认执行
- **edit**（编辑）—— 修改工具参数后执行
- **reject**（拒绝）—— 否决这次工具调用

---

## 2. 它能解决什么问题（用途）

### 2.1 高风险操作的安全门

| 场景 | 示例 |
|------|------|
| 发送邮件/消息 | 邮件发出后无法撤回，需要确认收件人、内容 |
| 删除文件/数据 | 不可逆操作，必须人工确认 |
| 资金转账/支付 | 涉及金钱，金额和账户必须正确 |
| 数据库写入/更新 | 修改生产数据前需要审核 SQL |
| 调用外部 API | 付费 API 或有副作用的第三方接口 |

### 2.2 合规与审计

- 金融、医疗、法律等行业要求**关键操作必须有人工审批记录**
- 通过 interrupt 机制自然形成审计日志（谁在什么时候批准了什么操作）

### 2.3 参数纠错

- LLM 提取的参数可能有误（如邮箱地址写错、金额识别错误）
- edit 功能允许人类在工具执行前修正参数

### 2.4 分级信任策略

- 低风险工具（搜索、查询）→ 自动放行
- 高风险工具（发送、删除、支付）→ 必须人工审批
- 实现 **"信任但验证"** 的 Agent 使用模式

### 2.5 人机协作工作流

- Agent 负责思考和规划
- 人类负责最终决策
- 形成 **"AI 建议 → 人类决策 → AI 执行"** 的协作模式

---

## 3. 前置依赖

### 3.1 必须有 checkpointer

`HumanInTheLoopMiddleware` **强制要求** `create_agent` 传入 `checkpointer` 参数。因为 interrupt 会暂停 Agent 执行，需要 checkpointer 保存当前状态，以便后续恢复。

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()  # 内存存储，开发/测试用
```

> 生产环境可以使用持久化的 checkpointer（如 PostgresSaver、SQLiteSaver）。

### 3.2 必须有 thread_id

每次调用必须在 config 中指定 `thread_id`，用于标识对话线程：

```python
config = {"configurable": {"thread_id": "my-thread-1"}}
```

### 3.3 使用 stream 模式

interrupt 发生时，`agent.stream()` 会正常结束（不报错），但 Agent 的执行实际上被暂停了。你需要通过检查状态来判断是否发生了 interrupt。

---

## 4. 基本用法

### 4.1 最简示例

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件。"""
    return f"邮件已发送给 {to}"

agent = create_agent(
    model=get_llm(),
    tools=[send_email],
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
            },
        ),
    ],
)
```

### 4.2 触发并恢复

```python
config = {"configurable": {"thread_id": "thread-1"}}

# 第一次调用：Agent 思考后决定调用 send_email → 被 interrupt 暂停
for event in agent.stream(query, config=config, stream_mode="updates"):
    print(event)

# 此时 Agent 已暂停，检查待审核的工具调用
state = agent.get_state(config)
last_msg = state.values["messages"][-1]
print(last_msg.tool_calls)  # 查看 Agent 想调用什么

# 人类审核通过后，恢复执行
for event in agent.stream(None, config=config, stream_mode="updates"):
    print(event)
```

**关键点**：恢复执行时传 `None` 作为输入，表示"继续之前被中断的流程"。

---

## 5. 参数详解

### 5.1 `interrupt_on` 参数

`interrupt_on` 是一个字典，key 是**工具函数名**（字符串），value 有两种形式：

#### 形式一：配置字典 —— 需要中断审核

```python
"send_email": {
    "allowed_decisions": ["approve", "edit", "reject"],
}
```

- `allowed_decisions`：列表，指定人类可以做出的决策类型
  - `"approve"` —— 批准执行
  - `"edit"` —— 修改参数后执行
  - `"reject"` —— 拒绝执行
  - 可以任意组合，比如只允许 approve 和 reject：`["approve", "reject"]`

#### 形式二：`False` —— 跳过中断，直接执行

```python
"search_web": False,
```

表示这个工具不需要人工审核，直接执行。

### 5.2 未在 `interrupt_on` 中出现的工具

如果某个工具**没有**出现在 `interrupt_on` 字典中，其行为取决于中间件的默认策略。建议**显式列出所有工具**的配置，避免歧义。

### 5.3 配置组合示例

```python
HumanInTheLoopMiddleware(
    interrupt_on={
        # 全部三种决策
        "transfer_money": {"allowed_decisions": ["approve", "edit", "reject"]},
        # 只允许批准或拒绝（不能编辑参数）
        "delete_file": {"allowed_decisions": ["approve", "reject"]},
        # 跳过审核
        "search_web": False,
        "query_database": False,
    }
)
```

---

## 6. 三种人工决策详解

### 6.1 approve（批准）

**含义**：同意 Agent 的工具调用，按原参数执行。

**实现**：直接恢复 Agent 执行即可。

```python
# 批准 = 直接恢复
for event in agent.stream(None, config=config, stream_mode="updates"):
    print(event)
```

**流程**：
```
Agent 想调用 send_email(to="a@b.com", subject="Hi") 
  → interrupt 暂停
  → 人类选择 approve
  → agent.stream(None, config) 恢复
  → send_email 按原参数执行
  → Agent 继续处理工具返回结果
```

### 6.2 edit（编辑参数）

**含义**：人类修改 Agent 提议的工具调用参数，然后用修改后的参数执行。

**实现**：需要通过 `agent.update_state()` 修改状态中的 `AIMessage.tool_calls`。

```python
from langchain_core.messages import AIMessage

# 1. 获取当前状态
state = agent.get_state(config)
last_message = state.values["messages"][-1]

# 2. 修改工具调用参数
new_tool_calls = []
for tc in last_message.tool_calls:
    modified_args = {**tc["args"]}
    modified_args["amount"] = 3000  # 比如把金额从 5000 改为 3000
    new_tool_calls.append({**tc, "args": modified_args})

# 3. 构造新的 AIMessage 并更新状态
edited_message = AIMessage(
    content=last_message.content,
    tool_calls=new_tool_calls,
)
agent.update_state(config, {"messages": [edited_message]})

# 4. 恢复执行（使用修改后的参数）
for event in agent.stream(None, config=config, stream_mode="updates"):
    print(event)
```

**流程**：
```
Agent 想调用 transfer_money(from="A", to="B", amount=5000)
  → interrupt 暂停
  → 人类修改 amount 为 3000
  → update_state 写入新参数
  → agent.stream(None, config) 恢复
  → transfer_money(from="A", to="B", amount=3000) 执行
```

### 6.3 reject（拒绝）

**含义**：人类否决这次工具调用，Agent 不执行该工具。

**实现**：为每个被拒绝的 tool_call 注入一条 `ToolMessage`，告知 Agent 操作被否决，然后恢复执行让 Agent 做出回应。

```python
from langchain_core.messages import ToolMessage

# 1. 为每个工具调用构造拒绝消息
rejection_messages = []
for tc in tool_calls:
    rejection_messages.append(
        ToolMessage(
            content="[用户拒绝] 该操作被用户否决。",
            tool_call_id=tc["id"],  # 必须关联到对应的 tool_call
        )
    )

# 2. 注入拒绝消息到 Agent 状态
agent.update_state(config, {"messages": rejection_messages})

# 3. 恢复执行，Agent 会看到拒绝消息并做出回应
for event in agent.stream(None, config=config, stream_mode="updates"):
    print(event)
```

**流程**：
```
Agent 想调用 delete_file(path="/important/data.db")
  → interrupt 暂停
  → 人类选择 reject
  → 注入 ToolMessage（内容为拒绝说明）
  → agent.stream(None, config) 恢复
  → Agent 读到拒绝消息，生成友好回复（如"好的，已取消删除操作"）
```

> **重要**：reject 时注入的 `ToolMessage` 的 `tool_call_id` 必须与被拒绝的 `tool_call` 的 `id` 对应，否则 LangGraph 会报错。

---

## 7. 完整执行流程图

```
用户输入
  │
  ▼
┌─────────────────┐
│   Agent 思考     │  ← model 节点（LLM 推理）
│  决定调用工具    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  HumanInTheLoopMiddleware       │  ← after_model 钩子
│  检查 interrupt_on 配置         │
│                                 │
│  该工具是否需要中断？           │
│  ├─ False → 跳过，直接执行工具  │
│  └─ {...} → 触发 interrupt      │
└────────┬────────────────────────┘
         │
    ┌────┴────────────────────────┐
    │  interrupt!  Agent 暂停     │
    │  stream() 正常返回          │
    │  等待人类决策...            │
    └────┬────────────────────────┘
         │
    人类做出决策
    ├─ approve → agent.stream(None, config) 直接恢复
    ├─ edit   → update_state(修改参数) → agent.stream(None, config) 恢复
    └─ reject → update_state(注入拒绝ToolMessage) → agent.stream(None, config) 恢复
         │
         ▼
┌─────────────────┐
│  工具执行        │  ← tools 节点（approve/edit 走这里）
│  或              │
│  Agent 回应拒绝  │  ← model 节点（reject 走这里）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent 继续      │  ← 可能继续调用工具或生成最终回复
└─────────────────┘
```

---

## 8. 恢复执行的三种方式

| 决策 | 恢复方式 | 关键操作 |
|------|---------|---------|
| approve | `agent.stream(None, config)` | 无需额外操作 |
| edit | `agent.update_state()` + `agent.stream(None, config)` | 修改 `AIMessage.tool_calls` |
| reject | `agent.update_state()` + `agent.stream(None, config)` | 注入 `ToolMessage`（带 tool_call_id） |

三种方式的共同点：**恢复时都是调用 `agent.stream(None, config)`**，传 `None` 表示"继续中断的流程"。

---

## 9. 实战配置模式

### 模式一：全部工具都需要审批

```python
HumanInTheLoopMiddleware(
    interrupt_on={
        "tool_a": {"allowed_decisions": ["approve", "edit", "reject"]},
        "tool_b": {"allowed_decisions": ["approve", "edit", "reject"]},
        "tool_c": {"allowed_decisions": ["approve", "edit", "reject"]},
    }
)
```

适用于：所有操作都是高风险的场景（如金融系统）。

### 模式二：按风险分级

```python
HumanInTheLoopMiddleware(
    interrupt_on={
        # 读操作：自动放行
        "search": False,
        "query": False,
        "read_file": False,
        # 写操作：需要审批
        "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
        "write_file": {"allowed_decisions": ["approve", "edit", "reject"]},
        # 危险操作：只能批准或拒绝（不让编辑，防止误操作）
        "delete_file": {"allowed_decisions": ["approve", "reject"]},
        "drop_table": {"allowed_decisions": ["approve", "reject"]},
    }
)
```

适用于：大多数实际应用。读操作放行，写操作审批，危险操作严格控制。

### 模式三：只编辑不拒绝

```python
HumanInTheLoopMiddleware(
    interrupt_on={
        "generate_report": {"allowed_decisions": ["approve", "edit"]},
    }
)
```

适用于：人类想参与内容生成过程，但不会完全否决的场景。

---

## 10. 与 create_agent 的 interrupt_before 的区别

LangChain 的 `create_agent` 本身也有 `interrupt_before` 参数可以实现中断：

```python
# 方式一：create_agent 原生参数
agent = create_agent(
    model=get_llm(),
    tools=[send_email],
    checkpointer=InMemorySaver(),
    interrupt_before=["tools"],  # 在所有工具执行前中断
)

# 方式二：HumanInTheLoopMiddleware
agent = create_agent(
    model=get_llm(),
    tools=[send_email, search_web],
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
                "search_web": False,
            }
        )
    ],
)
```

### 对比表

| 特性 | `interrupt_before` | `HumanInTheLoopMiddleware` |
|------|-------------------|---------------------------|
| 粒度 | 节点级别（`"tools"` = 所有工具） | **工具级别**（每个工具单独配置） |
| 选择性中断 | 不支持（全部或不中断） | 支持（部分工具中断，部分放行） |
| 决策类型 | 需自己实现 approve/edit/reject | 内置 `allowed_decisions` 配置 |
| 配置方式 | `create_agent` 的参数 | middleware 列表 |
| 灵活性 | 较低 | **较高** |
| 代码复杂度 | 简单（适合简单场景） | 稍复杂（适合复杂场景） |

### 选择建议

- **简单场景**（所有工具都需要审批，只需 approve/reject）→ 用 `interrupt_before=["tools"]`
- **复杂场景**（不同工具不同策略，需要 edit 功能）→ 用 `HumanInTheLoopMiddleware`

---

## 11. 注意事项与踩坑记录

### 11.1 checkpointer 是强制的

没有 checkpointer 会报错。即使是开发测试，也必须传入：

```python
checkpointer=InMemorySaver()  # 最简单的内存版
```

### 11.2 stream 事件中 data 可能为 None

`HumanInTheLoopMiddleware` 会产生自己的中间节点事件（如 `HumanInTheLoopMiddleware.after_model`），这些事件的 data **可能为 None**。打印事件时必须做空值检查：

```python
def print_event(event):
    for node_name, data in event.items():
        if data is None:       # 关键！中间件节点可能返回 None
            continue
        if not isinstance(data, dict):
            continue
        if "messages" in data:
            # 处理消息...
```

**不做检查会报**：`TypeError: argument of type 'NoneType' is not iterable`

### 11.3 reject 时 tool_call_id 必须匹配

注入拒绝的 `ToolMessage` 时，`tool_call_id` 必须与被拒绝的 `tool_call["id"]` 严格对应：

```python
ToolMessage(
    content="操作被拒绝",
    tool_call_id=tc["id"],  # 必须从原始 tool_call 中取
)
```

如果 id 不匹配，LangGraph 会报错或产生不可预期的行为。

### 11.4 edit 时要构造完整的 AIMessage

编辑工具参数后更新状态时，需要构造**完整的 AIMessage**（包含 content 和修改后的 tool_calls）：

```python
edited_message = AIMessage(
    content=last_message.content,    # 保留原始 content
    tool_calls=new_tool_calls,       # 使用修改后的 tool_calls
)
agent.update_state(config, {"messages": [edited_message]})
```

### 11.5 恢复执行用 `None`

恢复被中断的 Agent 时，输入传 `None`：

```python
agent.stream(None, config=config, stream_mode="updates")
#            ^^^^ 不是空字符串，不是空字典，是 None
```

### 11.6 每个 thread_id 是独立的

不同的 `thread_id` 代表独立的对话线程，状态互不影响：

```python
config1 = {"configurable": {"thread_id": "thread-1"}}
config2 = {"configurable": {"thread_id": "thread-2"}}
# thread-1 被中断不影响 thread-2
```

### 11.7 多轮对话中 interrupt 的行为

在同一个 thread 的多轮对话中：
- 每次高风险工具调用都会触发 interrupt
- checkpointer 保证历史消息完整保留
- 恢复执行后，Agent 能看到之前所有的对话历史

---

## 12. 完整代码参考

参见项目文件：

```
about_langchain_prebuild_middleware/about_HumanInTheLoop.py
```

该文件包含 4 个完整的演示场景：

| 场景 | 覆盖功能 |
|------|---------|
| 场景一：选择性审批 | 高风险工具 interrupt + 低风险工具 False 自动放行 |
| 场景二：编辑工具参数 | edit 流程：get_state → 修改参数 → update_state → 恢复 |
| 场景三：拒绝危险操作 | reject 流程：注入 ToolMessage → 恢复 → Agent 优雅回应 |
| 场景四：多轮对话 | 同一 thread 下多轮交互，展示 checkpointer 状态持久化 |

---

## 总结一句话

> `HumanInTheLoopMiddleware` = **工具级别的中断网关** + **approve/edit/reject 三种人工决策** + **checkpointer 状态持久化**，让 Agent 在执行高风险操作前必须经过人类审批，实现安全可控的人机协作。
