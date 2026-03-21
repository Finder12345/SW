from typing import List, Dict, Optional, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from typing_extensions import TypedDict

from typing import Annotated, Any, Sequence

class SkillEntry(TypedDict, total=False):
    """单个已加载技能在 state 中的表示。"""
    name: str
    description: str
    sections: dict[str, str]     # section_name -> section_content
    tool_names: list[str]        # 该技能注册的工具名列表
    fully_loaded: bool           # 是否已加载全部 section

class AgentState(BaseModel):

    # ===== 核心 =====
    messages: Annotated[Sequence[AnyMessage], add_messages]

    step: int = 0
    max_steps: int = 10

    next: Optional[str] = None

    final_answer: Optional[str] = None

    intermediate_steps: List[Dict] = []

    # ===== tool =====

    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_output: Optional[str] = None

    tools: Optional[List[str]] = None

    # ===== memory =====

    memory: Dict[str, Any] = {}

    rag_context: Optional[str] = None

    # ===== control =====

    finished: bool = False

    error: Optional[str] = None

    metadata: Dict[str, Any] = {}

    # skill
    skill_registry: str
    loaded_skills: dict[str, SkillEntry]
    phase: str          # "discovery" | "ready"
    turn_count: int
    metadata: dict[str, Any]