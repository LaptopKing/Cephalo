# Cephalo Universal MCP Server Integration

Cephalo provides a native, zero-dependency **Model Context Protocol (MCP)** server over standard input/output (stdio JSON-RPC 2.0).

This allows any MCP-compatible AI agent harness to directly query, record, synthesize specialties, and trigger continuous learning.

---

## 1. Compatible Harvesters & Environments

- **Claude Desktop** (`claude_desktop_config.json`)
- **Claude Code** (`claude mcp add ...`)
- **Cursor IDE** (`.cursor/mcp.json` or Settings -> Features -> MCP)
- **Windsurf IDE** (`~/.codeium/windsurf/mcp_config.json`)
- **Zed Editor** (`~/.config/zed/settings.json`)
- **Continue.dev** (`config.json` in `.continue`)
- **Google Antigravity**
- **GitHub Copilot / OpenAI Codex**

---

## 2. Server Configuration

Add the following block to your client's MCP configuration:

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

## 3. Exposed Tools Catalog

| Tool Name | Purpose |
| :--- | :--- |
| `cephalo_search` | Hybrid (dense Qwen 1024d vector + BM25 keyword) search across LanceDB memory. |
| `cephalo_record` | Sanitizes and permanently stores decisions, preferences, and architectural constraints. |
| `cephalo_get_profile` | Retrieves `USER_PROFILE.md` (hardware profiles, language, principles). |
| `cephalo_list_specialties` | Lists all active engineering and project specialties. |
| `cephalo_get_specialty` | Fetches verified fundamentals, key takeaways, and anti-slop rules for a specialty. |
| `cephalo_auto_create_specialty` | Autonomously synthesizes a specialty for any novel technology or framework. |
| `cephalo_continuous_learn` | Triggers a continuous learning cycle across workspaces and manifests. |
| `cephalo_learning_status` | Inspects continuous learning health, tracked stacks, and cycle stats. |
