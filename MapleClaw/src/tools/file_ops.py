"""文件读写操作工具集。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容并返回文本。

    Args:
        path: 文件路径（绝对路径或相对于工作目录的路径）
        encoding: 文件编码，默认 utf-8
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] 文件不存在: {p}"
    if not p.is_file():
        return f"[Error] 不是文件: {p}"
    try:
        return p.read_text(encoding=encoding)
    except UnicodeDecodeError:
        # 回退到二进制摘要
        size = p.stat().st_size
        return f"[Error] 无法以 {encoding} 解码，文件大小 {size} bytes，可能是二进制文件"


@tool
def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """将内容写入文件，若文件已存在则覆盖，父目录不存在时自动创建。

    Args:
        path: 目标文件路径
        content: 要写入的文本内容
        encoding: 文件编码，默认 utf-8
    """
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return f"[OK] 已写入 {p}（{len(content)} 字符）"
    except Exception as e:
        return f"[Error] 写入失败: {e}"


@tool
def append_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """向文件末尾追加内容，文件不存在时自动创建。

    Args:
        path: 目标文件路径
        content: 要追加的文本内容
        encoding: 文件编码，默认 utf-8
    """
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding=encoding) as f:
            f.write(content)
        return f"[OK] 已追加到 {p}（{len(content)} 字符）"
    except Exception as e:
        return f"[Error] 追加失败: {e}"


@tool
def list_directory(path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
    """列出目录内容。

    Args:
        path: 目录路径，默认为当前目录
        recursive: 是否递归列出子目录内容
        max_depth: 递归最大深度，默认 2
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] 目录不存在: {p}"
    if not p.is_dir():
        return f"[Error] 不是目录: {p}"

    lines: list[str] = [f"📁 {p}/"]

    def _walk(dir_path: Path, depth: int, prefix: str):
        if depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            lines.append(f"{prefix}[权限不足]")
            return
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}📁 {entry.name}/")
                if recursive:
                    ext = "    " if is_last else "│   "
                    _walk(entry, depth + 1, prefix + ext)
            else:
                size = entry.stat().st_size
                lines.append(f"{prefix}{connector}{entry.name} ({_fmt_size(size)})")

    _walk(p, 1, "")
    return "\n".join(lines)


@tool
def file_info(path: str) -> str:
    """获取文件或目录的详细信息（大小、修改时间、权限等）。

    Args:
        path: 文件或目录路径
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] 路径不存在: {p}"

    stat = p.stat()
    info = {
        "path": str(p),
        "type": "directory" if p.is_dir() else "file",
        "size": _fmt_size(stat.st_size),
        "size_bytes": stat.st_size,
        "permissions": oct(stat.st_mode)[-3:],
    }

    import datetime
    info["modified"] = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
    info["created"] = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()

    if p.is_file():
        info["extension"] = p.suffix or "(none)"
        info["lines"] = _count_lines(p)

    lines = [f"{k}: {v}" for k, v in info.items()]
    return "\n".join(lines)


@tool
def copy_path(src: str, dst: str) -> str:
    """复制文件或目录。

    Args:
        src: 源路径
        dst: 目标路径
    """
    src_p = Path(src).expanduser().resolve()
    dst_p = Path(dst).expanduser().resolve()
    if not src_p.exists():
        return f"[Error] 源路径不存在: {src_p}"
    try:
        if src_p.is_dir():
            shutil.copytree(src_p, dst_p)
        else:
            dst_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_p, dst_p)
        return f"[OK] 已复制 {src_p} → {dst_p}"
    except Exception as e:
        return f"[Error] 复制失败: {e}"


@tool
def move_path(src: str, dst: str) -> str:
    """移动/重命名文件或目录。

    Args:
        src: 源路径
        dst: 目标路径
    """
    src_p = Path(src).expanduser().resolve()
    dst_p = Path(dst).expanduser().resolve()
    if not src_p.exists():
        return f"[Error] 源路径不存在: {src_p}"
    try:
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        return f"[OK] 已移动 {src_p} → {dst_p}"
    except Exception as e:
        return f"[Error] 移动失败: {e}"


@tool
def delete_path(path: str) -> str:
    """删除文件或目录（目录会递归删除）。

    Args:
        path: 要删除的路径
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[Error] 路径不存在: {p}"
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"[OK] 已删除 {p}"
    except Exception as e:
        return f"[Error] 删除失败: {e}"


# ── 内部辅助 ──────────────────────────────────────────────────

def _fmt_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def _count_lines(p: Path) -> int | str:
    try:
        return sum(1 for _ in open(p, "r", encoding="utf-8"))
    except Exception:
        return "N/A (binary)"