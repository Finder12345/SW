"""内置工具集：文件操作、Shell、Python、文本处理。

使用 ``ALL_BUILTIN_TOOLS`` 获取所有工具列表，直接传给 create_agent。
"""

from ..tools.bash_tool import run_shell, run_shell_interactive
from ..tools.file_ops import (
    append_file,
    copy_path,
    delete_path,
    file_info,
    list_directory,
    move_path,
    read_file,
    write_file,
)
from ..tools.python_tool import run_python, run_python_isolated
from ..tools.text_tools import (
    count_tokens_estimate,
    diff_files,
    replace_in_file,
    search_in_file,
)

# 全部内置工具的列表，可直接传入 create_agent(tools=ALL_BUILTIN_TOOLS)
ALL_BUILTIN_TOOLS = [
    # 文件操作
    read_file,
    write_file,
    append_file,
    list_directory,
    file_info,
    copy_path,
    move_path,
    delete_path,
    # Shell
    run_shell,
    run_shell_interactive,
    # Python
    run_python,
    run_python_isolated,
    # 文本处理
    search_in_file,
    replace_in_file,
    diff_files,
    count_tokens_estimate,
]

__all__ = [
    "ALL_BUILTIN_TOOLS",
    "read_file", "write_file", "append_file", "list_directory",
    "file_info", "copy_path", "move_path", "delete_path",
    "run_shell", "run_shell_interactive",
    "run_python", "run_python_isolated",
    "search_in_file", "replace_in_file", "diff_files", "count_tokens_estimate",
]