# GitHub Copilot Repository Instructions for Cephalo

## 1. Cephalo Memory Environment
This codebase is part of the user's sovereign Second Brain, Cephalo:
`/home/strider/Cephalo`

## 2. Coding Standards
- Follow anti-slop software craftsmanship: no hallucinated wrappers, zero dead code, functions fit on 1-2 screens.
- Keep types explicit; never bypass with `as any`.
- In JavaScript/TypeScript, prefer Bun / native ESM / Node 22+.
- In Python, support Python 3.12+ with strict type hints.

## 3. User Style & Hardware Grounding
- Ground hardware and style preferences dynamically from `USER_PROFILE.md` or `cephalo search`.
- Tone: Technical, objective, direct, clean markdown.
- Language: English (or user's configured language).
