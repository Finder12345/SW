# ============================================================
# 阶段 2：InternalHookEvent — 理解事件对象的结构
# ============================================================

"""
1. 一个事件包含哪些信息？
    - 进行统一管理这个事件
"""

from datetime import datetime
from typing import Any, Callable, List
from dataclasses import dataclass, field

print("=" * 60)
print("阶段 2：事件对象 InternalHookEvent")
print("=" * 60)





@dataclass
class InternalHookEvent:
    """
    事件对象
    对于一个触发事件
    """
    type:str # "command" | "session" | "agent" | "gateway" | "message"
    action:str # "new", "reset", "stop", "received", "sent"
    session_key: str  # 会话标识符
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    messages: list[str] = field(default_factory=list)  # ← 关键！Hook 可以推消息给用户


# =====================
# Hook registry
# =====================

hooks: List[Callable[[InternalHookEvent], None]] = []


def register_hook(fn):
    hooks.append(fn)


# =====================
# Trigger
# =====================

def trigger(event: InternalHookEvent):
    print("触发事件:", event.type, event.action)

    for h in hooks:
        h(event)


# =====================
# Hook 1
# =====================

def welcome_hook(event: InternalHookEvent):
    if event.type == "command" and event.action == "new":
        event.messages.append("👋 欢迎使用系统")


# =====================
# Hook 2
# =====================

def log_hook(event: InternalHookEvent):
    print("LOG:", event.type, event.action)



if __name__ == "__main__":
    # 实例化事件
    register_hook(welcome_hook)
    register_hook(log_hook)
    event = InternalHookEvent(
        type="command",
        action="new",
        session_key="agent:main",
        context={
            "session_id": "abc123",
            "command_source": "telegram",
            "workspace_dir": "~/.openclaw/workspace",
        },
        messages=["欢迎使用 OpenClaw"],
    )
    trigger(event)

    print("最终消息:", event.messages)