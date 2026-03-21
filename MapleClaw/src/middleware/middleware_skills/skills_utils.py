from pathlib import Path
import re
import yaml
from dataclasses import dataclass


# 工作空间，存在agent的一些特性
WORKSPACE = Path(__file__).parent.parent.parent.parent.parent / ".MapleClaw" / "workspace"

# 内置的skill路径，也可以自己进行提供路径
SKILL_DIR = Path(__file__).parent.parent.parent.parent/"skills"

# todo 添加外接形式的skill

# 储存的记忆
MEMORY_DIR = WORKSPACE / "memory"


def load_md(path: Path) -> str:
    """安全加载 Markdown 文件"""
    return path.read_text(encoding="utf-8") if path.exists() else ""



def parse_skill_frontmatter(content: str) -> dict:
    """
    从 SKILL.md 中解析 YAML frontmatter。

    期望格式：
    ---
    name: code-review
    description: "当用户要求审查代码时..."
    triggers: ["代码审查", "code review", "检查bug"]
    tools: [file_read, code_execute]
    priority: high
    max_tokens: 2000
    ---
    """
    match = re.match(r"^---\s*\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def get_skill_body(content: str) -> str:
    """提取 frontmatter 之后的正文部分"""
    match = re.match(r"^---\s*\n.+?\n---\s*\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


@dataclass
class SkillEntry:
    """技能注册表中的单个条目"""
    name: str
    description: str
    triggers: list[str]
    priority: str  # "low" | "medium" | "high"
    max_tokens: int
    tools: list[str]
    content: str  # SKILL.md 完整正文（不含 frontmatter）
    path: str

    @property
    def priority_score(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(self.priority, 0)




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