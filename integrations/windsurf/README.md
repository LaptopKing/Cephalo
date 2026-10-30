# Cephalo Integration for Windsurf (Codeium)

Connect **Windsurf IDE** (Cascade agent) to Cephalo.

---

## 1. Setup MCP in Windsurf

Add the following to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "cephalo": {
      "command": "python",
      "args": [
        "C:\\Users\\strider-desktop\\.gemini\\antigravity\\scratch\\second-brain\\src\\cephalo\\services\\src\cephalo\services\mcp_server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

## 2. Cascade Rules

Copy [`.windsurfrules`](.windsurfrules) into any project workspace root.
