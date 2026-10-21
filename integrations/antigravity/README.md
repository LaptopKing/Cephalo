# Google Antigravity Integration for Cephalo

This integration allows **Google Antigravity** agents to automatically recognize, consult, and update your Cephalo Second Brain in every conversation session without manual intervention.

## How It Works
1. During installation (`install.ps1` or `install.sh`), Cephalo detects if the Google Antigravity configuration directory (`~/.gemini/config/`) exists.
2. It automatically provisions a global rule at:
   - **Windows:** `%USERPROFILE%\.gemini\config\rules\cephalo_second_brain.md`
   - **Linux / macOS:** `~/.gemini/config/rules/cephalo_second_brain.md`
3. Because Antigravity dynamically loads all rules from `~/.gemini/config/rules/` on every conversation turn:
   - The agent automatically knows your hardware, principles, and active projects.
   - The agent automatically queries Cephalo (`cephalo search`) before answering questions about your preferences.
   - The agent automatically ingests new technical decisions and preferences (`cephalo record`).
