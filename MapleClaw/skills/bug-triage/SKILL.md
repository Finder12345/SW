---
name: bug-triage
description: Triage a bug report by reproducing symptoms, locating the most likely cause, and proposing the smallest safe fix.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
triggers:
  - bug
  - error
  - failing
priority: high
metadata:
  openclaw:
    emoji: "🐞"
    requires:
      tools:
        - Read
        - Grep
        - Bash
---

# bug-triage

Use this skill for debugging requests and failing behavior analysis.

## Workflow

1. Restate the failure clearly.
2. Inspect the code path before proposing a fix.
3. Reproduce with the smallest relevant command or scenario.
4. Identify the root cause, not just the symptom.
5. Prefer the minimum targeted change.
6. Verify with a focused test or rerun.

## Output Expectations

- Explain what broke.
- Point to the most relevant file locations.
- Describe the fix and how it was validated.
