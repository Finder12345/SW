"""Agent 状态定义。"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SkillMetadata(TypedDict):
    """单个技能的元数据，从 SKILL.md front-matter 解析。

    对齐 Agent Skills specification (OpenCalw) 简化版：
    - name + description 用于 LLM 判断是否需要该技能
    - path 用于 LLM 通过文件读取工具按需加载全文
    - sections 列表用于 LLM 精准定位某个 section
    - allowed_tools 列表记录该 skill 建议搭配使用的运行时工具
    - triggers 触发关键词列表（OpenCalw 字段）
    - priority 优先级（OpenCalw 字段）
    - max_tokens 最大 token 数（OpenCalw 字段）
    - requires 依赖条件（OpenCalw Gate 规则）
    - emoji 展示图标（OpenCalw 字段）
    - install 安装指引（OpenCalw 字段）
    """
    name: str
    description: str
    path: str                      # SKILL.md 的绝对路径
    sections: list[str]            # ## 标题列表
    allowed_tools: list[str]       # front-matter 中声明的推荐工具名
    # OpenCalw 扩展字段
    triggers: list[str]           # 触发关键词
    priority: str                 # 优先级（high/medium/low）
    max_tokens: int              # 最大 token 数
    requires: dict[str, Any]       # 依赖条件（Gate 规则）
    emoji: str                    # 展示图标
    install: list[dict[str, Any]]  # 安装指引


class AgentState(TypedDict):
    """MapleClaw Agent 的核心状态。

    Attributes:
        messages: 对话消息列表，使用 add_messages reducer 自动合并。
        skills_metadata: 已扫描的技能元数据列表。由 SkillMiddleware.before_agent 填充，
                         后续轮次若已存在则跳过重复扫描。
        turn_count: 当前对话轮次计数。
        metadata: 可扩展的元数据字典。
    """
    messages: Annotated[Sequence[AnyMessage], add_messages]
    skills_metadata: NotRequired[list[SkillMetadata]]
    turn_count: int
    metadata: dict[str, Any]