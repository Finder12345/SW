"""Bash / Shell 命令执行工具。"""

from __future__ import annotations

import subprocess

from langchain_core.tools import tool

# 安全限制：默认超时时间（秒）
DEFAULT_TIMEOUT = 60
# 输出截断长度（字符）
MAX_OUTPUT_LENGTH = 8000


@tool
def run_bash(command: str, timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> str:
    """在 bash shell 中执行命令并返回输出。

    Args:
        command: 要执行的 bash 命令
        timeout: 超时时间（秒），默认 60
        cwd: 工作目录，默认为当前目录
    """
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=min(timeout, 300),  # 上限 5 分钟
            cwd=cwd,
        )
        output_parts: list[str] = []

        if result.stdout:
            output_parts.append(f"[stdout]\n{result.stdout}")
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        output_parts.append(f"[exit_code] {result.returncode}")

        full_output = "\n".join(output_parts)
        return _truncate(full_output)

    except subprocess.TimeoutExpired:
        return f"[Error] 命令超时（{timeout}s）: {command}"
    except Exception as e:
        return f"[Error] 执行失败: {e}"


@tool
def run_bash_interactive(commands: list[str], timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> str:
    """按顺序执行多条 bash 命令，返回每条的输出。适合有依赖关系的连续命令。

    Args:
        commands: 命令列表，按顺序执行
        timeout: 每条命令的超时时间（秒）
        cwd: 工作目录
    """
    results: list[str] = []
    for i, cmd in enumerate(commands):
        results.append(f"--- [{i + 1}] $ {cmd} ---")
        output = run_bash.invoke({"command": cmd, "timeout": timeout, "cwd": cwd})
        results.append(output)
    return _truncate("\n".join(results))


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LENGTH:
        return text
    half = MAX_OUTPUT_LENGTH // 2
    return (
        text[:half]
        + f"\n\n... [截断，总长 {len(text)} 字符] ...\n\n"
        + text[-half:]
    )