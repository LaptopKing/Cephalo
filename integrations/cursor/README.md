# Cephalo Integration for Cursor IDE

Connect **Cursor** (Cursor AI, Composer, and Chat) to Cephalo.

---

## 1. Setup MCP Server in Cursor

1. Open Cursor Settings (`Ctrl + Shift + J` or gear icon).
2. Navigate to **Features** -> **MCP**.
3. Click **Add New MCP Server**:
   - **Name:** `cephalo`
   - **Type:** `command`
   - **Command:** `python C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\src\cephalo\services\mcp_server.py`
4. Alternatively, paste [`cursor_mcp.json`](cursor_mcp.json) into your workspace's `.cursor/mcp.json`.

---

## 2. Using Cursor Rules

Copy [`.cursorrules`](.cursorrules) into any project workspace root to enforce Cephalo profile grounding and anti-slop standards automatically.
