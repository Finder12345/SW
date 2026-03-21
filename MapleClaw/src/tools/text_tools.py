"""文本处理工具集：搜索、替换、diff 等常用文本操作。"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from langchain_core.tools import tool


@tool
def search_in_file(path: str, pattern: str, is_regex: bool = False, context_lines: int = 2) -> str:
    """在文件中搜索匹配的行，返回匹配行及上下文。

    Args:
        path: 文件路径
        pattern: 搜索模式（纯文本或正则表达式）
        is_regex: 是否作为正则表达式匹配，默认 False
        context_lines: 上下文行数，默认 2
    """
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return f"[Error] 文件不存在: {p}"

    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return "[Error] 无法解码文件，可能是二进制文件"

    matches: list[str] = []
    regex = re.compile(pattern) if is_regex else None

    for i, line in enumerate(lines):
        hit = regex.search(line) if regex else (pattern in line)
        if hit:
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            snippet = []
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                snippet.append(f"{marker} {j + 1:4d} | {lines[j]}")
            matches.append("\n".join(snippet))

    if not matches:
        return f"未找到匹配: '{pattern}'"

    header = f"找到 {len(matches)} 处匹配:\n"
    return header + "\n---\n".join(matches)


@tool
def replace_in_file(path: str, old: str, new: str, count: int = 0) -> str:
    """在文件中执行文本替换。

    Args:
        path: 文件路径
        old: 要替换的文本
        new: 替换后的文本
        count: 最大替换次数，0 表示全部替换
    """
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return f"[Error] 文件不存在: {p}"

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "[Error] 无法解码文件"

    if old not in content:
        return f"[Warning] 未找到要替换的文本: '{old[:80]}...'"

    if count > 0:
        new_content = content.replace(old, new, count)
    else:
        new_content = content.replace(old, new)

    n_replacements = content.count(old) if count == 0 else min(count, content.count(old))
    p.write_text(new_content, encoding="utf-8")
    return f"[OK] 替换了 {n_replacements} 处（文件: {p}）"


@tool
def diff_files(path_a: str, path_b: str) -> str:
    """比较两个文件的差异，输出 unified diff 格式。

    Args:
        path_a: 第一个文件路径
        path_b: 第二个文件路径
    """
    pa = Path(path_a).expanduser().resolve()
    pb = Path(path_b).expanduser().resolve()

    for fp in (pa, pb):
        if not fp.is_file():
            return f"[Error] 文件不存在: {fp}"

    try:
        lines_a = pa.read_text(encoding="utf-8").splitlines(keepends=True)
        lines_b = pb.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "[Error] 无法解码文件"

    diff = difflib.unified_diff(lines_a, lines_b, fromfile=str(pa), tofile=str(pb))
    result = "".join(diff)
    return result if result else "两个文件内容相同"


@tool
def count_tokens_estimate(text: str) -> str:
    """粗略估算文本的 token 数量（基于空格和标点分割，非精确）。

    Args:
        text: 输入文本
    """
    # 粗略估算：英文 ~1 token/word，中文 ~1.5 token/char
    words = len(text.split())
    cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_cjk_words = words
    estimated = int(non_cjk_words * 1.3 + cjk_chars * 1.5)
    return (
        f"字符数: {len(text)}\n"
        f"单词数（空格分割）: {words}\n"
        f"CJK 字符数: {cjk_chars}\n"
        f"估算 token 数: ~{estimated}"
    )