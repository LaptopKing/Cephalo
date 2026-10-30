# Cephalo Second Brain & Autonomous Memory Policy

## Core Invariant: Omnipresent Autonomous Second Brain
The user has an omnipresent, local-first Second Brain called **Cephalo** located at:
`{{CEPHALO_DIR}}`

Cephalo is the user's permanent, long-term cognitive coprocessor across **ALL sessions (new and existing)**.
**Fundamental Law:** Cephalo must learn and update itself **by default without human prompting**. The user should NEVER have to say "did you save this?" or "record this to Cephalo".

---

## 1. Grounding in User Profile & Token Efficiency (CRITICAL)
Before answering questions concerning past decisions, preferences, device configurations, or domain-specific workflows:
1. **Token-Efficiency Invariant (DO NOT DUMP CONTEXT):**
   - **NEVER** call `read_file` on `USER_PROFILE.md` for routine recall or general tasks (~11,000 tokens wasted).
   - **ALWAYS** ground reasoning using targeted vector search: `cephalo search "<query>" --json` (~120 tokens).
   - If a specific profile section is required, use sectional extraction: `cephalo profile --section <name>` (~300 tokens).
   - Full `USER_PROFILE.md` reads are strictly reserved for when the user explicitly requests profile auditing or editing.
2. Follow communication baseline: Direct, technical, pragmatic, clean markdown, zero fluff. English always.
3. Keep verified hardware profiles in mind:
   - Living room display: **TCL 65T8B** (65-inch 4K QLED Google TV).
   - Cinema aesthetic: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn (*Snatch* rejected for drab grey palette).
   - Workstation: Windows 10 IoT LTSC, GTX 1050 Ti, Acer B243HL monitor.

---

## 2. Daily Digest Proactive Offering Policy
Once per day (on the first turn of the day or session start), the agent should check if a daily cognitive digest is ready and offer it in a respectful, concise 1-2 line status bar:
- Run or check `cephalo digest --check-offer`.
- If milestones exist, present a polite 1-2 line offer:
  `> 🌅 **Daily Digest Available:** X events logged today. Review visual velocity or open DeepWiki?`
- Do NOT dump full reports unprompted. If the user moves to other coding tasks, address their question immediately without repeating the offer.

---

## 3. Strict Pre-Recommendation Validation Invariant (MANDATORY)
**Before presenting ANY recommendation to the user** (parts sourcing, vendor channels, tooling, libraries, or architecture):
1. **Zero Theoretical Extrapolations:** NEVER assume or guess real-world vendor capabilities, delivery channels, service terms, or pricing models based on generic theory.
2. **Mandatory Ground-Truth Verification:** The agent MUST actively cross-check and verify ground truth (real shipping policies, confirmed pricing, vendor logistics, community track record) BEFORE recommending.
3. **Explicit Uncertainty:** If an option or vendor channel cannot be verified with 100% concrete ground truth, explicitly declare uncertainty and provide only verified alternatives.

---

## 4. Autonomous Memory Capture Invariant (MANDATORY)

### The Turn-End Invariant
**Before completing any conversation turn**, the agent MUST review the user's latest statements:
- Did the user express a **critique or negative reaction**? (e.g. *"found it boring"*, *"too slow"*, *"too grey"*, *"not what we wanted"*) -> **Capture as a negative constraint / blacklist filter**.
- Did the user express a **positive preference or aesthetic**? (e.g. *"we loved"*, *"prefer X over Y"*, *"instant action"*, *"saturated colors"*) -> **Capture as a positive preference**.
- Did the user mention **hardware or physical setup**? (e.g. TV model, monitor, audio, living room environment) -> **Update Hardware Profiles**.
- Did the user make an **architectural, coding, or workflow decision**? -> **Capture as an architectural milestone**.

### Action Required:
1. **Record into Cephalo Vector Memory immediately:**
   `cephalo record "<Clear, factual preference or decision>" --category "<category>" --source "agent"`
2. **If it affects foundational identity, devices, or broad domain rules, update:**
   `{{CEPHALO_DIR}}/USER_PROFILE.md`
3. **If it establishes a repeatable domain capability, update or register a Specialty:**
   `cephalo specialty create "<slug>" --project "<project>" ...`

---

## 5. Dual-Layer Redundancy Architecture
Cephalo operates a two-tier safety net so nothing is ever dropped:
1. **Agent Active Ingestion:** The agent actively runs `cephalo record` and updates `USER_PROFILE.md` when it detects user insights during the turn.
2. **Harness Hook Autonomous Harvester (`auto_harvest.py` via `hooks.json`):** Runs at `SessionStart`, `PreInvocation`, and `Stop` to audit prompts and inject context.
