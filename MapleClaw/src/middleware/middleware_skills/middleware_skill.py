# ============================================================
#  中间件 1：SkillMiddleware — 技能渐进式加载
# ============================================================
import re
import time
import yaml
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, field
from langchain.agents import  AgentState
from langchain.agents.middleware import AgentMiddleware

from MapleClaw.src.prompts.system import WORKSPACE

SKILL_DIR =  Path(__file__).parent.parent.parent.parent/"skills"


# ============================================================
#  技能注册表
# ============================================================

class SkillRegistry:
    """
    技能注册表：扫描 skills/ 目录，构建索引。

    目录结构：
      skills/
      ├── code-review/
      │   └── SKILL.md
      ├── research/
      │   └── SKILL.md
      └── writing/
          └── SKILL.md
    """

    def __init__(self, skill_dir: Path = SKILL_DIR):
        self.skill_dir = skill_dir
        self.entries: dict[str, SkillEntry] = {}
        self._scan()

    def _scan(self):
        """扫描目录，加载所有技能的元数据"""
        if not self.skill_dir.exists():
            return
        for child in self.skill_dir.iterdir():
            skill_file = child / "SKILL.md"
            if not skill_file.exists():
                continue
            raw = skill_file.read_text(encoding="utf-8")
            meta = parse_skill_frontmatter(raw)
            if not meta.get("name"):
                continue
            self.entries[meta["name"]] = SkillEntry(
                name=meta["name"],
                description=meta.get("description", ""),
                triggers=meta.get("triggers", []),
                priority=meta.get("priority", "medium"),
                max_tokens=meta.get("max_tokens", 3000),
                tools=meta.get("tools", []),
                content=get_skill_body(raw),
                path=str(skill_file),
            )

    def match(
        self, message: str, top_k: int = 2, threshold: float = 3.0
    ) -> list[SkillEntry]:
        """
        根据用户消息匹配技能。

        匹配策略（中英文混合、无分词依赖）：
        1. trigger 完整子串命中 → +10 分
        2. trigger 中的中文片段在消息中出现 → +5 分
        3. trigger 中的英文单词在消息中出现 → +5 分
        4. 长中文 trigger 做 bigram 覆盖率匹配 → 最高 +4 分
        5. description 中 >= 3 字的中文片段命中 → +1.5 分
        6. priority 微调 → +0.1~0.3

        只有总分 >= threshold 的技能才会被选中。

        生产环境升级路径：
        - 替换为 embedding 模型做语义匹配
        - 在 SkillMiddleware.__init__ 中注入自定义 matcher
        """
        if not message:
            return []

        scored: list[tuple[float, SkillEntry]] = []
        msg_lower = message.lower()

        for entry in self.entries.values():
            score = 0.0

            # ---- Trigger 匹配（核心信号）----
            for trigger in entry.triggers:
                t = trigger.lower().strip()

                # 策略1：完整子串包含
                if t in msg_lower:
                    score += 10.0
                    continue

                # 策略2：中文片段 + 英文单词分别匹配
                cn_parts = re.findall(r"[\u4e00-\u9fff]+", t)
                en_parts = re.findall(r"[a-z]+", t)

                for part in cn_parts:
                    if len(part) >= 2 and part in msg_lower:
                        score += 5.0
                    elif len(part) >= 4:
                        # 长中文做 bigram 覆盖率
                        bigrams = [part[i : i + 2] for i in range(len(part) - 1)]
                        hits = sum(1 for bg in bigrams if bg in msg_lower)
                        ratio = hits / len(bigrams) if bigrams else 0
                        if ratio >= 0.6:
                            score += 4.0 * ratio

                for part in en_parts:
                    if part in msg_lower:
                        score += 5.0

            # ---- Description 辅助匹配（低权重，防止噪音）----
            desc_fragments = re.findall(r"[\u4e00-\u9fff]{3,}", entry.description.lower())
            for frag in desc_fragments:
                if frag in msg_lower:
                    score += 1.5

            # ---- Priority 微调 ----
            score += entry.priority_score * 0.1

            if score >= threshold:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def get(self, name: str) -> SkillEntry | None:
        return self.entries.get(name)

    def list_names(self) -> list[str]:
        return list(self.entries.keys())

class SkillState(AgentState):
    """扩展 state，增加技能追踪字段"""
    loaded_skills: list[str] = []           # 当前已加载的技能名称列表
    skill_load_history: list[str] = []      # 本次会话加载过的所有技能（用于去重）




class SkillMiddleware(AgentMiddleware[SkillState, Any]):
    """
    技能渐进式加载中间件。

    工作流程：
    ┌─────────────────────────────────────────┐
    │ before_model                            │
    │  1. 读取最新用户消息                      │
    │  2. 用 SkillRegistry.match() 匹配技能     │
    │  3. 与当前 loaded_skills 对比             │
    │  4. 有变化 → 更新 state                   │
    │  5. 无变化 → 返回 None                    │
    └─────────────────────────────────────────┘

    设计要点：
    - 每轮 model call 前都会重新评估，因为多轮对话中意图会变化
    - 最多同时加载 max_concurrent 个技能，防止上下文膨胀
    - loaded_skills 只存名称，实际内容由 PromptMiddleware 读取并注入
    - skill_load_history 跨轮次累积，防止同一技能反复加载/卸载
    """

    state_schema = SkillState

    def __init__(
        self,
        skill_dir: Path = SKILL_DIR,
        max_concurrent: int = 2,
        sticky: bool = True,
    ):
        """
        Args:
            skill_dir: 技能目录路径
            max_concurrent: 最多同时加载的技能数
            sticky: True = 已加载的技能不会被自动卸载（除非手动清除）
                    False = 每轮重新匹配，可能替换旧技能
        """
        self.registry = SkillRegistry(skill_dir)
        self.max_concurrent = max_concurrent
        self.sticky = sticky

    @property
    def name(self) -> str:
        return "SkillMiddleware"

    def before_agent(self, state: SkillState, runtime) -> dict[str, Any] | None:
        """agent 启动时，初始化技能字段并输出可用技能日志"""
        runtime.stream_writer({
            "type": "skill_system",
            "message": f"技能系统就绪，已注册 {len(self.registry.entries)} 个技能: "
                       f"{', '.join(self.registry.list_names())}",
        })
        return {
            "loaded_skills": [],
            "skill_load_history": [],
        }

    def before_model(self, state: SkillState, runtime) -> dict[str, Any] | None:
        """每次 model call 前，根据最新消息重新评估技能匹配"""

        # 1. 取最新的用户消息
        last_user_msg = self._get_last_user_message(state)
        if not last_user_msg:
            return None

        # 2. 匹配技能
        matched = self.registry.match(last_user_msg, top_k=self.max_concurrent)
        matched_names = [e.name for e in matched]

        # 3. 计算最终加载列表
        current = state.get("loaded_skills", [])
        history = state.get("skill_load_history", [])

        if self.sticky:
            # sticky 模式：保留已有的，追加新匹配的，不超过上限
            new_names = [n for n in matched_names if n not in current]
            final = current + new_names
            # 如果超过上限，优先保留优先级高的
            if len(final) > self.max_concurrent:
                final = self._sort_by_priority(final)[: self.max_concurrent]
        else:
            # 非 sticky 模式：每轮重新匹配
            final = matched_names

        # 4. 如果没变化，跳过
        if set(final) == set(current):
            return None

        # 5. 记录加载事件
        newly_loaded = [n for n in final if n not in current]
        unloaded = [n for n in current if n not in final]

        if newly_loaded:
            runtime.stream_writer({
                "type": "skill_loaded",
                "skills": newly_loaded,
                "message": f"加载技能: {', '.join(newly_loaded)}",
            })
        if unloaded:
            runtime.stream_writer({
                "type": "skill_unloaded",
                "skills": unloaded,
                "message": f"卸载技能: {', '.join(unloaded)}",
            })

        # 6. 更新 state
        updated_history = list(set(history + final))
        return {
            "loaded_skills": final,
            "skill_load_history": updated_history,
        }

    def _get_last_user_message(self, state: SkillState) -> str:
        """从 state 中提取最新的用户消息文本"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
            if isinstance(msg, dict) and msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _sort_by_priority(self, names: list[str]) -> list[str]:
        """按技能优先级排序"""
        def key(n):
            entry = self.registry.get(n)
            return entry.priority_score if entry else 0
        return sorted(names, key=key, reverse=True)