---
name: cephalo
description: >-
  Omnipresent Autonomous Second Brain and Personal Memory Engine.
  Use whenever managing or retrieving user preferences, hardware configurations (e.g. TCL 65T8B TV),
  entertainment and cinema criteria, project domain specialties, vector memory retrieval,
  or recording persistent user constraints and decisions.
---

# Cephalo Second Brain & Autonomous Memory Engine

Cephalo is the user's sovereign, local-first Second Brain and permanent cognitive coprocessor. It operates autonomously across all sessions, conversations, and agent harnesses (Antigravity, Claude Code, Cursor, Codex).

Base directory: `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain`

---

## 1. Grounding in User Profile & Verified Hardware

Before making assumptions or answering questions concerning past decisions, preferences, device configurations, or domain-specific workflows:
1. Ground your reasoning in Cephalo:
   - Check the profile blueprint: `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\USER_PROFILE.md`
   - Run hybrid vector search: `cephalo search "<query>" --json`
2. Follow the user's communication style: direct, technical, pragmatic, clean markdown, no fluff.
3. Keep the user's hardware constraints in mind:
   - Living room display: **TCL 65T8B** (65-inch 4K QLED Google TV).
   - Cinema aesthetic: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn (*Snatch* rejected for drab grey palette).

---

## 2. Autonomous Memory Capture Invariant (MANDATORY)

**At the end of every conversation turn**, review the user's latest statements:
- **Critique / Negative reaction** (*"found it boring"*, *"too slow"*, *"too grey"*) -> Record as negative constraint / blacklist.
- **Positive preference / aesthetic** (*"we loved"*, *"instant action"*, *"saturated colors"*) -> Record as positive preference.
- **Hardware / physical setup** (*TV model*, *monitor*, *audio*) -> Update Hardware Profiles.
- **Architectural / project decision** -> Record as milestone or specialty.

### Execution:
```bash
cephalo record "<Clear, factual preference or decision>" --category "<category>" --source "agent"
```
If it affects identity, devices, or broad domain rules, update:
`C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\USER_PROFILE.md`

---

## 3. Knowledge Specialties Layer

Cephalo manages a 3-tier hierarchy:
`Project` -> `Specialties` (domain modules) -> `User Preferences` (personal constraints).

When working on a new project or domain:
- List existing specialties: `cephalo specialty list`
- Inspect a specialty: `cephalo specialty get "<specialty-name>"`
- Create a new specialty:
  ```bash
  cephalo specialty create "<specialty-name>" --project "<project-name>" --fundamentals "<core domain knowledge>" --takeaways "rule 1" "rule 2"
  ```
Specialties are saved under `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\specialties\<project>\<specialty>\` and automatically indexed into LanceDB.

> [!CAUTION]
> Specialty deletion requires explicit human user confirmation. Never delete without `--confirm`.

---

## 4. Cephalo CLI Quick Reference

Command                       | Description
:---------------------------- | :---------------------------------------------
`cephalo status`              | System health, LanceDB row count, prompt index
`cephalo profile`             | Print or view USER_PROFILE.md
`cephalo search "<query>"`    | Hybrid semantic (Qwen 1024d) + BM25 memory search
`cephalo web "<query>"`       | Google-style live web search: AI Quick Summary, organic results & social blocks
`cephalo web "<query>" --html`| Generate interactive Google-style SERP Generative UI
`cephalo web "<query>" --open`| Generate and open interactive SERP in default browser
`cephalo fetch "<url>"`       | Clean text extraction (supports --dynamic Chromium SPA crawling)
`cephalo record "<text>"`     | Sanitize and index into vector memory
`cephalo specialty list`      | View all domain specialties across projects
`cephalo specialty create`    | Register domain knowledge module
`cephalo harvest`             | Audit past transcripts across workspaces

---

## 5. Google-Style Web Search & Generative UI UX

When the user requests web searches or current information:
- Execute `cephalo web "<query>"` or call MCP tool `cephalo_web_search`.
- The UX presents:
  1. **Quick Summary (AI Overview)**: Synthesized direct answer answering the search query from top results + key bullet takeaways + domain citation pills.
  2. **Organic Web Results**: Favicon, site breadcrumb path, clickable title, and clean readable snippet.
  3. **Social & Community Blocks**: Embedded discussion cards for Reddit (`r/subreddit`), YouTube videos, GitHub repositories, and X posts.
- For interactive chat embedding in Antigravity, generate the HTML widget and embed it:
  ```html
  <agent-embed src="file:///path/to/serp_cache/<slug>.html"></agent-embed>
  ```
