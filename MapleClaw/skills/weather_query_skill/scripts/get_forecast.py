#!/usr/bin/env python3
"""
天气查询工具 - 未来天气预报（Mock 版本）

用法：
    python get_forecast.py --city "北京" --days 3

返回 JSON 格式的未来 N 天天气预报数据。
当前为 Mock 实现，返回模拟数据。接入真实 API 时只需替换 fetch_forecast() 函数内部逻辑。
"""

import argparse
import json
import sys
import hashlib
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool


# ============================================================
# 预报生成器 - 基于城市名+日期偏移生成伪随机但一致的预报
# ============================================================

WEATHER_PATTERNS = {
    "北京": [
        {"weather_day": "晴", "weather_night": "晴", "temp_high": 28, "temp_low": 16},
        {"weather_day": "晴转多云", "weather_night": "多云", "temp_high": 27, "temp_low": 17},
        {"weather_day": "多云", "weather_night": "阴", "temp_high": 25, "temp_low": 15},
        {"weather_day": "阴转小雨", "weather_night": "小雨", "temp_high": 22, "temp_low": 14},
        {"weather_day": "小雨转多云", "weather_night": "多云", "temp_high": 23, "temp_low": 13},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 26, "temp_low": 15},
        {"weather_day": "晴", "weather_night": "晴", "temp_high": 29, "temp_low": 17},
    ],
    "上海": [
        {"weather_day": "阴转小雨", "weather_night": "小雨", "temp_high": 23, "temp_low": 18},
        {"weather_day": "小雨", "weather_night": "中雨", "temp_high": 21, "temp_low": 17},
        {"weather_day": "中雨转小雨", "weather_night": "阴", "temp_high": 20, "temp_low": 16},
        {"weather_day": "多云", "weather_night": "多云", "temp_high": 24, "temp_low": 18},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 26, "temp_low": 19},
        {"weather_day": "晴", "weather_night": "晴转多云", "temp_high": 27, "temp_low": 20},
        {"weather_day": "多云", "weather_night": "阴", "temp_high": 25, "temp_low": 19},
    ],
    "广州": [
        {"weather_day": "雷阵雨", "weather_night": "阵雨", "temp_high": 30, "temp_low": 24},
        {"weather_day": "阵雨转多云", "weather_night": "多云", "temp_high": 31, "temp_low": 25},
        {"weather_day": "多云", "weather_night": "多云", "temp_high": 33, "temp_low": 26},
        {"weather_day": "晴转多云", "weather_night": "雷阵雨", "temp_high": 34, "temp_low": 26},
        {"weather_day": "雷阵雨", "weather_night": "中雨", "temp_high": 29, "temp_low": 24},
        {"weather_day": "小雨转阴", "weather_night": "多云", "temp_high": 30, "temp_low": 24},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 32, "temp_low": 25},
    ],
    "深圳": [
        {"weather_day": "阵雨", "weather_night": "多云", "temp_high": 30, "temp_low": 25},
        {"weather_day": "多云", "weather_night": "晴", "temp_high": 31, "temp_low": 26},
        {"weather_day": "晴转雷阵雨", "weather_night": "雷阵雨", "temp_high": 32, "temp_low": 26},
        {"weather_day": "大雨", "weather_night": "中雨", "temp_high": 28, "temp_low": 24},
        {"weather_day": "阴转多云", "weather_night": "多云", "temp_high": 29, "temp_low": 25},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 31, "temp_low": 26},
        {"weather_day": "晴", "weather_night": "晴", "temp_high": 33, "temp_low": 27},
    ],
    "成都": [
        {"weather_day": "阴", "weather_night": "阴", "temp_high": 21, "temp_low": 15},
        {"weather_day": "阴转小雨", "weather_night": "小雨", "temp_high": 19, "temp_low": 14},
        {"weather_day": "小雨", "weather_night": "小雨", "temp_high": 18, "temp_low": 13},
        {"weather_day": "阴", "weather_night": "多云", "temp_high": 20, "temp_low": 14},
        {"weather_day": "多云", "weather_night": "多云", "temp_high": 22, "temp_low": 15},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 24, "temp_low": 16},
        {"weather_day": "晴转多云", "weather_night": "阴", "temp_high": 23, "temp_low": 15},
    ],
    "杭州": [
        {"weather_day": "多云", "weather_night": "阴", "temp_high": 25, "temp_low": 17},
        {"weather_day": "阴转小雨", "weather_night": "小雨", "temp_high": 22, "temp_low": 16},
        {"weather_day": "小雨转阴", "weather_night": "多云", "temp_high": 21, "temp_low": 15},
        {"weather_day": "多云转晴", "weather_night": "晴", "temp_high": 25, "temp_low": 17},
        {"weather_day": "晴", "weather_night": "晴", "temp_high": 27, "temp_low": 18},
        {"weather_day": "晴转多云", "weather_night": "多云", "temp_high": 26, "temp_low": 18},
        {"weather_day": "多云", "weather_night": "阴", "temp_high": 24, "temp_low": 17},
    ],
}


def generate_fallback_forecast(city: str, day_offset: int) -> dict:
    """对于不在预设库中的城市，基于哈希生成伪随机预报。"""
    seed = f"{city}_{day_offset}"
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)

    day_weathers = ["晴", "多云", "阴", "小雨", "阵雨", "晴转多云", "多云转阴", "雷阵雨"]
    night_weathers = ["晴", "多云", "阴", "小雨", "多云转晴"]
    wind_dirs = ["东风", "南风", "西风", "北风", "东南风", "东北风", "西南风", "西北风"]

    temp_high = 15 + (h % 20)
    temp_low = temp_high - 5 - (h >> 4) % 8

    return {
        "weather_day": day_weathers[h % len(day_weathers)],
        "weather_night": night_weathers[(h >> 8) % len(night_weathers)],
        "temp_high": temp_high,
        "temp_low": temp_low,
        "humidity": 30 + (h >> 12) % 60,
        "wind_direction": wind_dirs[(h >> 16) % len(wind_dirs)],
        "wind_level": f"{1 + (h >> 20) % 5}级",
        "precipitation_prob": (h >> 24) % 100,
        "uv_index": 1 + (h >> 28) % 10,
    }


class ForecastInput(BaseModel):
    city: str = Field(..., description="City name")
    days: int = Field(3, ge=1, le=7, description="Forecast days (1-7)")


def fetch_forecast(city: str, days: int) -> dict:
    """获取指定城市未来 N 天的天气预报（Mock）。"""
    today = datetime.now()
    forecasts = []

    for i in range(1, days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[target_date.weekday()]

        if city in WEATHER_PATTERNS:
            pattern = WEATHER_PATTERNS[city]
            day_data = pattern[(i - 1) % len(pattern)]
            forecast = {
                "date": date_str,
                "weekday": weekday,
                "weather_day": day_data["weather_day"],
                "weather_night": day_data["weather_night"],
                "temp_high": day_data["temp_high"],
                "temp_low": day_data["temp_low"],
                "humidity": 40 + (i * 7) % 50,
                "wind_direction": "东南风",
                "wind_level": f"{1 + i % 3}级",
                "precipitation_prob": 80 if "雨" in day_data["weather_day"] else 15,
                "uv_index": 3 + i % 5,
            }
        else:
            fb = generate_fallback_forecast(city, i)
            forecast = {
                "date": date_str,
                "weekday": weekday,
                **fb,
            }

        forecasts.append(forecast)

    return {
        "city": city,
        "query_time": today.strftime("%Y-%m-%d %H:%M:%S"),
        "forecast_days": days,
        "forecasts": forecasts,
    }


def _get_weather_forecast(city: str, days: int = 3) -> str:
    """Return forecast as JSON string for the agent."""
    return json.dumps(fetch_forecast(city, days), ensure_ascii=False)


tool = StructuredTool.from_function(
    name="get_weather_forecast",
    description="Get weather forecast for a city (mock data). Inputs: city, days(1-7).",
    func=_get_weather_forecast,
    args_schema=ForecastInput,
)


def main():
    parser = argparse.ArgumentParser(description="查询城市未来天气预报（Mock 版本）")
    parser.add_argument("--city", required=True, help="要查询的城市名称")
    parser.add_argument("--days", type=int, default=3, choices=range(1, 8),
                        help="预报天数，1-7 天（默认 3 天）")
    args = parser.parse_args()

    try:
        result = fetch_forecast(args.city, args.days)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        error = {"error": True, "message": str(e), "city": args.city}
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()