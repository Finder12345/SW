"""
进行构建各种提示词
"""
from pathlib import Path
from datetime import datetime




def load_md(path)->str:
    p = Path(path)
    return p.read_text(encoding='utf-8') if p.exists() else ''


WORKSPACE = Path(__file__).parent.parent.parent.parent / ".MapleClaw" / "workspace"
SOUL = load_md(WORKSPACE / "SOUL.md")
USER = load_md(WORKSPACE / "USER.md")
TOOLS = load_md(WORKSPACE / "TOOLS.md")


def build_system_prompt(system_prompt):
    return f"""
    You are a helpful assistant.
    {system_prompt}
    """

if __name__ == '__main__':
    print(SOUL)