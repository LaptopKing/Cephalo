# Cephalo Second Brain & Autonomous Memory Policy

## Core Invariant: Omnipresent Second Brain
The user has an omnipresent, local-first Second Brain called **Cephalo** located at:
`{{CEPHALO_DIR}}`

Cephalo is the user's permanent long-term memory core across **ALL sessions (new and existing)**. The AI agent must never restart from scratch or repeatedly ask the user for information, preferences, hardware setups, or background that are already recorded in Cephalo.

---

## 1. Grounding in User Profile & Verified Hardware
Before answering questions concerning past decisions, preferences, device configurations, or domain-specific workflows:
1. Always ground your reasoning in Cephalo:
   - Consult the profile blueprint: `{{CEPHALO_DIR}}/USER_PROFILE.md`
   - Or run the hybrid vector search CLI: `cephalo search "<query>" --json`
2. Follow the user's communication style and language preferences specified in `USER_PROFILE.md`.

---

## 2. Automated Continuous Learning (Record)
Whenever the user:
- Expresses a new preference, desire, or interest
- Introduces or configures a new device, tool, or hardware
- Makes an architectural, coding, or technical decision
- Shares a project idea or workflow rule

The agent **must automatically persist it**:
1. Record into Cephalo vector database:
   `cephalo record "<decision_or_preference>" --category "<category>" --source "agent"`
2. If it affects core user identity, hardware, or global principles, update:
   `{{CEPHALO_DIR}}/USER_PROFILE.md`

---

## 3. Continuous GitHub Synchronization
If Cephalo is version-controlled via Git, all modifications, feature additions, and documentation improvements made to the repository must be committed and pushed:
```powershell
Set-Location "{{CEPHALO_DIR}}"
git add .
git commit -m "<Clear, descriptive commit message>"
git push
```
