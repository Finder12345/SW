---
name: weather-query
description: 查询天气信息的技能。当用户询问任何与天气相关的问题时触发此技能，包括：查询某个城市/地区的天气、温度、湿度、风力、空气质量、是否需要带伞/穿外套、未来几天天气预报、天气对出行的影响等。触发关键词包括：'天气'、'气温'、'温度'、'下雨'、'下雪'、'刮风'、'湿度'、'空气质量'、'紫外线'、'weather'、'forecast'、'temperature' 等。即使用户没有直接说"查天气"，只要涉及出行建议、穿衣建议、是否带伞等隐含天气需求，也应使用此技能。
metadata:
  openclaw:
    emoji: "🌤"
    max_tokens: 3000
    priority: medium
    requires:
      tools: ["run_python", "run_shell"]
triggers: ["天气", "气温", "温度", "下雨", "下雪", "刮风", "湿度", "空气质量", "紫外线", "weather", "forecast", "temperature"]
allowed-tools: ["run_python", "run_shell", "read_file"]
---

# 天气查询技能 (Weather Query Skill)

## 概述

本技能提供天气信息查询能力，支持国内外主要城市的实时天气和未来天气预报查询。查询脚本位于 `scripts/` 目录下，返回 JSON 格式的天气数据。

## 使用流程

1. **解析用户意图** — 从用户消息中提取：目标城市、查询类型（实时/预报）、关注点（温度/降水/风力等）
2. **优先使用运行时内置工具执行**：
   - 优先使用 `run_python`
   - 如果确实需要 shell，再使用 `run_shell`
3. **格式化输出** — 将 JSON 数据转化为用户友好的自然语言回复

## 查询工具

### 实时天气查询

优先使用 `run_python`，执行类似下面的代码：

```python
import importlib.util
from pathlib import Path

script_path = Path(r"D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_current_weather.py")
spec = importlib.util.spec_from_file_location("weather_current", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.fetch_current_weather("城市名"))
```

如果 `run_python` 不适合当前任务，再退回使用：

```shell
python "D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_current_weather.py" --city "城市名"
```

返回当前天气的 JSON 数据，包括温度、体感温度、天气状况、湿度、风力风向、空气质量等。

### 未来天气预报

优先使用 `run_python`，执行类似下面的代码：

```python
import importlib.util
from pathlib import Path

script_path = Path(r"D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_forecast.py")
spec = importlib.util.spec_from_file_location("weather_forecast", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.fetch_forecast("城市名", 3))
```

如果 `run_python` 不适合当前任务，再退回使用：

```shell
python "D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_forecast.py" --city "城市名" --days 3
```

`--days` 参数支持 1-7 天，默认 3 天。返回每日天气预报数据。

## 输出格式指南

### 实时天气回复模板

回复应简洁友好，包含以下要素（按需选择）：

- **天气概况**：当前天气状况 + 温度
- **体感信息**：体感温度（与实际温差较大时提及）
- **降水信息**：是否有雨/雪，降水概率
- **风力信息**：风向风力（大风时重点提示）
- **空气质量**：AQI 及等级（空气差时重点提示）
- **生活建议**：穿衣、出行、防晒等实用建议

### 回复风格

- 使用自然、口语化的表达，不要机械罗列数据
- 根据天气情况主动给出实用建议
- 极端天气时加强提醒语气
- 温度使用摄氏度（°C），如用户在美国等地区则使用华氏度（°F）
- 不要使用 emoji（除非用户自己使用了）

### 示例回复

**用户问**：北京今天天气怎么样？

**回复**：
北京现在晴天，气温 26°C，体感温度差不多。东南风 2 级，湿度 45%，空气质量良好（AQI 68）。今天挺适合户外活动的，不过紫外线偏强，出门记得做好防晒。

**用户问**：明天上海会下雨吗？我要出门。

**回复**：
根据预报，明天上海是阴转小雨，降水概率 75%，主要集中在下午到晚间。气温 18-23°C，东北风 3 级。建议出门带把伞，穿件薄外套会比较舒服。

## 边界情况处理

| 情况 | 处理方式 |
|------|----------|
| 用户未指定城市 | 根据用户位置信息推断，若无法推断则礼貌询问 |
| 城市名模糊（如"长安"） | 选择最常见的匹配，并说明是哪个城市 |
| 查询不支持的城市 | 告知暂不支持，建议查询附近的大城市 |
| 用户问超过 7 天的预报 | 说明长期预报准确度有限，仅提供 7 天内数据 |
| 用户隐含天气需求 | 如"明天适合跑步吗"，先查天气再结合场景给出建议 |

## 注意事项

- 优先把天气脚本当作运行时可调用的 Python 模块，通过 `run_python` 调用其函数
- 只有在 `run_python` 不适用时，才退回到 `run_shell` 执行命令行脚本
- 实时查询使用：`D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_current_weather.py`
- 预报查询使用：`D:/CODE/MYSELF/SW/MapleClaw/skills/weather_query_skill/scripts/get_forecast.py`
- 这些脚本当前返回的是 mock 数据，可用于演示 skill 工作流，但不代表真实在线天气
