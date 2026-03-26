---
name: code-review-checklist
description: Use a lightweight checklist to review code changes for correctness, risk, testing, and readability before giving feedback.
allowed-tools:
  - Read
  - Grep
  - Glob
triggers:
  - code review
  - review changes
  - review diff
priority: high
metadata:
  openclaw:
    emoji: "🔍"
    requires:
      tools:
        - Read
        - Grep
---

# code-review-checklist

Use this skill when the user asks for a code review, change review, or wants feedback on a patch.

## When To Use

- The user asks you to review changed files.
- The user wants bug risk analysis.
- The user asks whether an implementation looks correct.

## Workflow

1. Identify the changed files or relevant files.
2. Read the full code before judging it.
3. Focus on correctness, security, regressions, and missing tests.
4. Prefer concrete findings over broad style commentary.
5. Cite file paths and line numbers in the final review.

## Output Style

- Start with the highest-risk findings.
- Keep findings actionable and specific.
- If there are no major issues, say that clearly and mention residual risk.
