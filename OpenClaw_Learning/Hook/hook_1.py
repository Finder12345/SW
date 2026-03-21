# 什么是钩子？
# 就是一个事件，可以注册多个回调函数，当事件触发时，会调用所有注册的回调函数

"""
钩子管理器：
1. 如何注册钩子？
    - 触发事件 关联 钩子handle
2. 如果触发钩子？
    - 拿出事件下的钩子，并进行回调该钩子

(钩子的具体实现不管)


"""

print("=" * 60)
print("阶段 1：最简单的 Hook — 事件 → 回调")
print("=" * 60)

class SimpleHook:
    def __init__(self):
        self.handlers:dict[str,list] = {}

    def register(self, event:str, handler):
        # 将一个hook handler 添加到事件中
        # 显然一个事件可以有多个handler
        # 这里的handler是一个函数,准确地说是一个函数对象
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append(handler)

    def trigger(self, event:str, *args, **kwargs):
        # 触发一个事件
        # 这里的args和kwargs是可选的
        # 触发一个事件会调用所有注册的handler
        # 按照注册顺序调用，先注册的先调用，也就是队列顺序
        # *args，表示函数的参数，准确地说是元组
        # **kwargs，表示函数的参数，准确地说是字典
        if event not in self.handlers:
            return
        # 对注册的handler进行遍历，也就是回 调
        # 一定是是相同的事件
        for handler in self.handlers[event]:
            handler(*args, **kwargs)

def my_logger(*args, **kwargs):
    print(f"  [日志Hook] 命令{args}被执行了")

def my_memory_saver(*args, **kwargs):
    print(f"  [记忆Hook] 保存会话到 memory_{args[0]["session_key"]}/.md")

def my_chat_saver(*args):
    print(f"  [聊天Hook] 聊天内容是{args}")


if __name__ == "__main__":
    hook = SimpleHook()
    # 先按顺序进行注册
    hook.register("command:new", my_logger)
    hook.register("command:new", my_memory_saver)

    hook.register("chat:new", my_chat_saver)
    # 进行触发
    hook.trigger("command:new", {"action": "new","session_key":"agent:main"})

    hook.trigger("chat:new", [1,2,3])
