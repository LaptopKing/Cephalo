# Cephalo Second Brain & Autonomous Memory Policy

## Core Invariant: Omnipresent Autonomous Second Brain
The user has an omnipresent, local-first Second Brain called **Cephalo** located at:
`{{CEPHALO_DIR}}`

Cephalo is the user's permanent, long-term cognitive coprocessor across **ALL sessions (new and existing)**.
**Fundamental Law:** Cephalo must learn and update itself **by default without the user having to ask, prompt, or remind the agent**. The user should NEVER have to say "did you save this?" or "record this to Cephalo".

---

## 1. Daily Digest Proactive Offering Policy
Once per day (on the first turn of the day or session start), the agent should check if a daily cognitive digest is ready and offer it in a respectful, concise 1-2 line status bar:
- Run or check `cephalo digest --check-offer`.
- If milestones exist, present a polite 1-2 line offer:
  `> 🌅 **Daily Digest Available:** X events logged today. Would you like to review today's visual cognitive velocity or open the DeepWiki 24h scrubber?`
- Do NOT dump full reports unprompted. If the user moves to other coding tasks, address their question immediately without repeating the offer.

---

## 2. Grounding in User Profile & Verified Hardware
Before answering questions concerning past decisions, preferences, device configurations, or domain-specific workflows:
1. Always ground your reasoning in Cephalo:
   - Consult the profile blueprint: `{{CEPHALO_DIR}}/USER_PROFILE.md`
   - Or run the hybrid vector search CLI: `cephalo search "<query>" --json`
2. Follow the user's communication style and language preferences specified in `USER_PROFILE.md` (direct, technical, pragmatic, clean markdown, no fluff).

---

## 2. Strict Pre-Recommendation Validation Invariant (MANDATORY)
**Before presenting ANY recommendation to the user** (parts sourcing, vendor channels, tooling, libraries, or architecture):
1. **Zero Theoretical Extrapolations:** NEVER assume or guess real-world vendor capabilities, delivery channels, service terms, or pricing models based on generic theory (e.g. assuming a car dealership ships small parts, guessing delivery fees, or assuming parts compatibility).
2. **Mandatory Ground-Truth Verification:** The agent MUST actively cross-check and verify ground truth (real shipping policies, confirmed pricing, vendor logistics, and automotive/technical community track record) BEFORE recommending.
3. **Explicit Uncertainty:** If an option or vendor channel cannot be verified with 100% concrete ground truth, explicitly declare the uncertainty and provide only verified alternatives.

---

## 3. Autonomous Memory Capture Invariant (MANDATORY)

### The Turn-End Invariant
**Before completing any conversation turn**, the agent MUST review the user's latest statements:
- Did the user express a **critique or negative reaction**? (e.g. *"found it boring"*, *"too slow"*, *"too grey"*, *"not what we wanted"*) $\rightarrow$ **Capture as a negative constraint / blacklist filter**.
- Did the user express a **positive preference or aesthetic**? (e.g. *"we loved"*, *"prefer X over Y"*, *"instant action"*, *"saturated colors"*) $\rightarrow$ **Capture as a positive preference**.
- Did the user mention **hardware or physical setup**? (e.g. TV model, monitor, audio, living room environment) $\rightarrow$ **Update Hardware Profiles**.
- Did the user make an **architectural, coding, or workflow decision**? $\rightarrow$ **Capture as an architectural milestone**.

### Action Required:
1. **Record into Cephalo Vector Memory immediately:**
   `cephalo record "<Clear, factual preference or decision>" --category "<category>" --source "agent"`
2. **If it affects foundational identity, devices, or broad domain rules, update:**
   `{{CEPHALO_DIR}}/USER_PROFILE.md`
3. **If it establishes a repeatable domain capability, update or register a Specialty:**
   `cephalo specialty create "<slug>" --project "<project>" ...`

---

## 4. Dual-Layer Redundancy Architecture
Cephalo operates a two-tier safety net so nothing is ever dropped:
1. **Agent Active Ingestion:** The agent actively runs `cephalo record` and updates `USER_PROFILE.md` when it detects user insights during the turn.
2. **Harness Hook Autonomous Harvester (`src/cephalo/learning/auto_harvest.py` via `hooks.json`):** Even if an agent fails to execute the command, the harness `Stop` lifecycle hook automatically scans the raw transcript on turn completion, detects preference markers, and logs them to `prompts.jsonl`.

---

## 5. Local Git Synchronization
When Cephalo code, blueprints, or documentation are modified, ensure they are synchronized with the local git repository:
```bash
cd "{{CEPHALO_DIR}}"
git add .
git commit -m "<Clear, descriptive commit message>"
```
