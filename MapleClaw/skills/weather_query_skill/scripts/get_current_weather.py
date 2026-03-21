#!/usr/bin/env python3
"""
天气查询工具 - 实时天气（Mock 版本）

用法：
    python get_current_weather.py --city "北京"

返回 JSON 格式的当前天气数据。
当前为 Mock 实现，返回模拟数据。接入真实 API 时只需替换 fetch_weather() 函数内部逻辑。
"""

import argparse
import json
import sys
import hashlib
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool


# ============================================================
# Mock 数据库 - 模拟真实天气 API 返回
# ============================================================
MOCK_WEATHER_DB = {
    "北京": {
        "city": "北京",
        "province": "北京市",
        "country": "中国",
        "weather": "晴",
        "temperature": 26,
        "feels_like": 25,
        "humidity": 45,
        "wind_direction": "东南风",
        "wind_level": "2级",
        "wind_speed_kmh": 12,
        "air_quality_index": 68,
        "air_quality_level": "良",
        "visibility_km": 15,
        "uv_index": 7,
        "uv_level": "强",
        "pressure_hpa": 1013,
        "precipitation_mm": 0,
        "cloud_cover_percent": 15,
        "sunrise": "05:42",
        "sunset": "19:18",
    },
    "上海": {
        "city": "上海",
        "province": "上海市",
        "country": "中国",
        "weather": "多云",
        "temperature": 23,
        "feels_like": 24,
        "humidity": 72,
        "wind_direction": "东北风",
        "wind_level": "3级",
        "wind_speed_kmh": 18,
        "air_quality_index": 55,
        "air_quality_level": "良",
        "visibility_km": 12,
        "uv_index": 4,
        "uv_level": "中等",
        "pressure_hpa": 1015,
        "precipitation_mm": 0,
        "cloud_cover_percent": 60,
        "sunrise": "05:28",
        "sunset": "18:45",
    },
    "广州": {
        "city": "广州",
        "province": "广东省",
        "country": "中国",
        "weather": "小雨",
        "temperature": 28,
        "feels_like": 32,
        "humidity": 88,
        "wind_direction": "南风",
        "wind_level": "1级",
        "wind_speed_kmh": 6,
        "air_quality_index": 42,
        "air_quality_level": "优",
        "visibility_km": 8,
        "uv_index": 2,
        "uv_level": "低",
        "pressure_hpa": 1008,
        "precipitation_mm": 3.5,
        "cloud_cover_percent": 90,
        "sunrise": "06:05",
        "sunset": "18:52",
    },
    "深圳": {
        "city": "深圳",
        "province": "广东省",
        "country": "中国",
        "weather": "阵雨",
        "temperature": 29,
        "feels_like": 33,
        "humidity": 85,
        "wind_direction": "西南风",
        "wind_level": "2级",
        "wind_speed_kmh": 10,
        "air_quality_index": 38,
        "air_quality_level": "优",
        "visibility_km": 10,
        "uv_index": 3,
        "uv_level": "中等",
        "pressure_hpa": 1009,
        "precipitation_mm": 5.2,
        "cloud_cover_percent": 80,
        "sunrise": "06:08",
        "sunset": "18:48",
    },
    "成都": {
        "city": "成都",
        "province": "四川省",
        "country": "中国",
        "weather": "阴",
        "temperature": 20,
        "feels_like": 19,
        "humidity": 75,
        "wind_direction": "北风",
        "wind_level": "1级",
        "wind_speed_kmh": 5,
        "air_quality_index": 95,
        "air_quality_level": "良",
        "visibility_km": 6,
        "uv_index": 1,
        "uv_level": "低",
        "pressure_hpa": 1010,
        "precipitation_mm": 0,
        "cloud_cover_percent": 95,
        "sunrise": "06:32",
        "sunset": "19:05",
    },
    "杭州": {
        "city": "杭州",
        "province": "浙江省",
        "country": "中国",
        "weather": "晴转多云",
        "temperature": 24,
        "feels_like": 23,
        "humidity": 58,
        "wind_direction": "东风",
        "wind_level": "2级",
        "wind_speed_kmh": 11,
        "air_quality_index": 52,
        "air_quality_level": "良",
        "visibility_km": 14,
        "uv_index": 6,
        "uv_level": "强",
        "pressure_hpa": 1014,
        "precipitation_mm": 0,
        "cloud_cover_percent": 35,
        "sunrise": "05:30",
        "sunset": "18:42",
    },
    "Tokyo": {
        "city": "Tokyo",
        "province": "Tokyo",
        "country": "Japan",
        "weather": "Partly Cloudy",
        "temperature": 22,
        "feels_like": 21,
        "humidity": 55,
        "wind_direction": "SE",
        "wind_level": "Level 2",
        "wind_speed_kmh": 14,
        "air_quality_index": 45,
        "air_quality_level": "Good",
        "visibility_km": 16,
        "uv_index": 5,
        "uv_level": "Moderate",
        "pressure_hpa": 1016,
        "precipitation_mm": 0,
        "cloud_cover_percent": 40,
        "sunrise": "05:15",
        "sunset": "18:22",
    },
    "New York": {
        "city": "New York",
        "province": "New York",
        "country": "USA",
        "weather": "Sunny",
        "temperature": 18,
        "feels_like": 16,
        "humidity": 40,
        "wind_direction": "NW",
        "wind_level": "Level 3",
        "wind_speed_kmh": 22,
        "air_quality_index": 60,
        "air_quality_level": "Moderate",
        "visibility_km": 20,
        "uv_index": 6,
        "uv_level": "High",
        "pressure_hpa": 1020,
        "precipitation_mm": 0,
        "cloud_cover_percent": 10,
        "sunrise": "06:05",
        "sunset": "19:30",
    },
    "London": {
        "city": "London",
        "province": "England",
        "country": "UK",
        "weather": "Overcast",
        "temperature": 14,
        "feels_like": 12,
        "humidity": 78,
        "wind_direction": "W",
        "wind_level": "Level 4",
        "wind_speed_kmh": 28,
        "air_quality_index": 55,
        "air_quality_level": "Moderate",
        "visibility_km": 10,
        "uv_index": 2,
        "uv_level": "Low",
        "pressure_hpa": 1005,
        "precipitation_mm": 0.5,
        "cloud_cover_percent": 100,
        "sunrise": "05:55",
        "sunset": "20:10",
    },
}


def generate_fallback_weather(city: str) -> dict:
    """
    对于不在 Mock 数据库中的城市，基于城市名哈希生成伪随机天气数据。
    这样相同城市每次查询结果一致，不同城市结果不同。
    """
    h = int(hashlib.md5(city.encode()).hexdigest(), 16)

    weathers = ["晴", "多云", "阴", "小雨", "阵雨", "晴转多云", "多云转阴"]
    aqi_levels = [("优", 30), ("良", 70), ("轻度污染", 120), ("中度污染", 160)]
    wind_dirs = ["东风", "南风", "西风", "北风", "东南风", "东北风", "西南风", "西北风"]

    temp = 10 + (h % 25)  # 10~34°C
    humidity = 30 + (h >> 4) % 60  # 30~89%
    weather = weathers[h % len(weathers)]
    wind_dir = wind_dirs[(h >> 8) % len(wind_dirs)]
    wind_level_num = 1 + (h >> 12) % 5
    aqi_label, aqi_base = aqi_levels[(h >> 16) % len(aqi_levels)]
    aqi = aqi_base + (h >> 20) % 30

    return {
        "city": city,
        "province": "未知",
        "country": "未知",
        "weather": weather,
        "temperature": temp,
        "feels_like": temp + (-2 + (h >> 24) % 5),
        "humidity": humidity,
        "wind_direction": wind_dir,
        "wind_level": f"{wind_level_num}级",
        "wind_speed_kmh": wind_level_num * 6,
        "air_quality_index": aqi,
        "air_quality_level": aqi_label,
        "visibility_km": 5 + (h >> 28) % 16,
        "uv_index": 1 + (h >> 32) % 10,
        "uv_level": "中等",
        "pressure_hpa": 1000 + (h >> 36) % 25,
        "precipitation_mm": round(((h >> 40) % 100) / 10, 1) if "雨" in weather else 0,
        "cloud_cover_percent": 10 + (h >> 44) % 80,
        "sunrise": "05:45",
        "sunset": "18:50",
    }


class CurrentWeatherInput(BaseModel):
    city: str = Field(..., description="City name, e.g. 北京 / Shanghai / San Francisco")


def fetch_weather(city: str) -> dict:
    """获取指定城市的实时天气数据（Mock）。"""
    # 尝试精确匹配
    if city in MOCK_WEATHER_DB:
        data = MOCK_WEATHER_DB[city]
    else:
        # 尝试模糊匹配（包含关系）
        matched = None
        for key in MOCK_WEATHER_DB:
            if city in key or key in city:
                matched = key
                break
        if matched:
            data = MOCK_WEATHER_DB[matched]
        else:
            data = generate_fallback_weather(city)

    # 添加查询时间
    data["query_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


def _get_current_weather(city: str) -> str:
    """Return weather info as JSON string for the agent."""
    return json.dumps(fetch_weather(city), ensure_ascii=False)


tool = StructuredTool.from_function(
    name="get_current_weather",
    description="Get current weather for a city (mock data). Input: city.",
    func=_get_current_weather,
    args_schema=CurrentWeatherInput,
)


def main():
    parser = argparse.ArgumentParser(description="查询城市实时天气（Mock 版本）")
    parser.add_argument("--city", required=True, help="要查询的城市名称")
    args = parser.parse_args()

    try:
        result = fetch_weather(args.city)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        error = {"error": True, "message": str(e), "city": args.city}
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()