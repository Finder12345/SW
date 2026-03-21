# ============================================================
# 阶段 3：Hook 发现机制 — 自动扫描目录加载 Hook
# ============================================================
from dataclasses import  dataclass
"""
1. 之前拿钩子都是实现写好，手动进行事件与钩子的绑定，是否可以优化
    - 事先定义一下钩子的元数据
        - 名字
        - 描述
        - emoji
        - 可以触发该钩子的事件
        - 需要的环境，条件等等
        
"""

print("=" * 60)
print("阶段 3：Hook 发现与加载机制")
print("=" * 60)

import os
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, List
from dataclasses import dataclass, field

@dataclass
class HookMetadata:
    """
    对应 HOOK.md 的 YAML frontmatter 解析结果。

    OpenClaw 中对应的文件：
    - src/hooks/frontmatter.ts  → 解析 HOOK.md 中的 YAML
    - src/hooks/types.ts        → 类型定义
    """

    name: str
    description: str
    emoji: str = "🔗"
    events: list[str] = field(default_factory=list)
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    requires_os: list[str] = field(default_factory=list)
    always: bool = False  # 跳过资格检查


@dataclass
class DiscoveredHook:
    """一个被发现的 Hook，包含元数据和 handler 函数"""

    metadata: HookMetadata
    handler: Any  # 实际的处理函数
    source: str  # "workspace" | "managed" | "bundled"
    enabled: bool = True



class HookDiscovery:
    """
    对应 OpenClaw 的 src/hooks/workspace.ts（目录扫描）
    和 src/hooks/config.ts（资格检查）。

    发现流程：
    1. 扫描 3 个目录（workspace → managed → bundled）
    2. 解析每个 Hook 的 HOOK.md
    3. 检查资格（所需二进制、环境变量、操作系统等）
    4. 加载 handler
    """

    # OpenClaw 的 3 层发现目录，优先级从高到低
    SEARCH_DIRS = [
        "{workspace}/hooks/",  # 工作空间级（最高优先级）
        "~/.openclaw/hooks/",  # 用户安装的（跨工作空间共享）
        "{openclaw}/dist/hooks/bundled/",  # 内置的
    ]

    @staticmethod
    def check_eligibility(meta: HookMetadata) -> tuple[bool, str]:
        """
        对应 src/hooks/config.ts 中的资格检查。检测这个钩子是否eligibility

        检查项：
        - bins: 所需的命令行工具是否存在（如 node, git）
        - env: 所需的环境变量是否设置
        - os: 当前操作系统是否匹配
        - config: 所需的配置项是否存在
        """
        import shutil
        import sys

        # 检查所需的二进制工具

        for bin_name in meta.requires_bins:
            if not shutil.which(bin_name):
                return False, f"缺少命令: {bin_name}"

        # 检查所需的环境变量
        for env_var in meta.requires_env:
            if env_var not in os.environ:
                return False, f"缺少环境变量: {env_var}"

        # 检查操作系统
        if meta.requires_os:
            current_os = sys.platform
            if current_os not in meta.requires_os:
                return False, f"当前 OS ({current_os}) 不匹配: {meta.requires_os}"

        return True, "ok"

if __name__ == "__main__":
    hook_meta = HookMetadata(
        name="session-memory",
        description="保存会话上下文到记忆文件",
        emoji="💾",
        events=["command:new", "command:reset"],
        requires_bins=["node"],
    )
    eligible, reason = HookDiscovery.check_eligibility(hook_meta)
    # print(f"  Hook: {hook_meta.emoji} {hook_meta.name}")
    # print(f"  事件: {hook_meta.events}")
    # print(f"  资格: {'✅ 合格' if eligible else '❌ 不合格'} ({reason})")

    print()