# MapleClaw

基于 LangChain v1 构建的可扩展 Agent 框架，支持技能热加载与中间件机制。

## 快速开始

### 1. 安装依赖

```bash
pip install langchain langchain-openai langgraph pyyaml
```

### 2. 配置

编辑 `src/config/global_config.yaml`，填入你的 OpenAI API Key 和 Base URL。

### 3. 运行

```bash
cd src
python -m agent.claw
```

## 架构

- **agent/** — Agent 核心，状态定义与运行入口
- **middleware/** — 中间件层（技能加载、提示词注入）
- **skills/** — 独立技能目录，每个技能包含 SKILL.md 描述 + scripts/ 实现
- **model/** — LLM 实例化（基于 `init_chat_model`）
- **config/** — 全局配置（API Key、URL、模型参数）
- **prompts/** — 系统提示词

## 技能开发

在 `skills/` 下创建新目录，包含：
- `SKILL.md` — 技能描述（name、description、tools 列表）
- `scripts/` — Python 脚本，每个导出一个 `tool` 变量（`@tool` 装饰器）
