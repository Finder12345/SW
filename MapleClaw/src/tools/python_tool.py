"""Python 代码执行工具。"""

from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

from langchain_core.tools import tool

MAX_OUTPUT_LENGTH = 8000


@tool
def run_python(code: str) -> str:
    """在当前进程中执行 Python 代码并返回输出。

    代码中的 print() 输出和最终表达式的值都会被捕获。
    共享全局命名空间，前一次执行中定义的变量在后续调用中可用。

    Args:
        code: 要执行的 Python 代码
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    # 使用持久化命名空间，让多次调用间共享变量
    if not hasattr(run_python, "_namespace"):
        run_python._namespace = {"__builtins__": __builtins__}

    ns = run_python._namespace

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            # 尝试作为表达式求值（捕获返回值）
            try:
                result = eval(compile(code, "<agent_python>", "eval"), ns)
                if result is not None:
                    print(repr(result))
            except SyntaxError:
                # 作为语句块执行
                exec(compile(code, "<agent_python>", "exec"), ns)
    except Exception:
        stderr_buf.write(traceback.format_exc())

    parts: list[str] = []
    stdout_val = stdout_buf.getvalue()
    stderr_val = stderr_buf.getvalue()

    if stdout_val:
        parts.append(f"[stdout]\n{stdout_val}")
    if stderr_val:
        parts.append(f"[stderr]\n{stderr_val}")
    if not parts:
        parts.append("[OK] 执行完成，无输出")

    full = "\n".join(parts)
    return _truncate(full)


@tool
def run_python_isolated(code: str) -> str:
    """在隔离的命名空间中执行 Python 代码。每次调用都是全新环境，变量不会跨调用保留。

    Args:
        code: 要执行的 Python 代码
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    ns = {"__builtins__": __builtins__}

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<agent_python_isolated>", "exec"), ns)
    except Exception:
        stderr_buf.write(traceback.format_exc())

    parts: list[str] = []
    stdout_val = stdout_buf.getvalue()
    stderr_val = stderr_buf.getvalue()

    if stdout_val:
        parts.append(f"[stdout]\n{stdout_val}")
    if stderr_val:
        parts.append(f"[stderr]\n{stderr_val}")
    if not parts:
        parts.append("[OK] 执行完成，无输出")

    full = "\n".join(parts)
    return _truncate(full)


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LENGTH:
        return text
    half = MAX_OUTPUT_LENGTH // 2
    return (
        text[:half]
        + f"\n\n... [截断，总长 {len(text)} 字符] ...\n\n"
        + text[-half:]
    )