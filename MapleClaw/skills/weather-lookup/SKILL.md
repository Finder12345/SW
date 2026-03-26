---
name: weather-lookup
description: Guide for answering weather questions using the runtime's existing tools and returning concise, location-aware forecasts.
allowed-tools:
  - Bash
  - WebFetch
triggers:
  - weather
  - forecast
  - temperature
priority: medium
metadata:
  openclaw:
    emoji: "☁️"
    requires:
      tools:
        - Bash
---

# weather-lookup

Use this skill when the user asks for current weather, a forecast, or weather comparisons.

## Workflow

1. Confirm the target location if the user did not provide one.
2. Use an available runtime tool to fetch weather data.
3. Summarize the result in plain language.
4. If the data source fails, explain the limitation briefly.

## Good Responses

- Current conditions plus temperature.
- Short forecast for the requested time range.
- Mention uncertainty if the location is ambiguous.

## Avoid

- Dumping raw API output.
- Pretending data exists when a fetch failed.
