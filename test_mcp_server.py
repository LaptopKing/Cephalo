#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MCP_SERVER = SCRIPT_DIR / "mcp_server.py"

def test_mcp_protocol():
    proc = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    # 1. Test initialize
    init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    init_res = json.loads(line)
    assert init_res["id"] == 1
    assert "capabilities" in init_res["result"]
    assert init_res["result"]["serverInfo"]["name"] == "cephalo-mcp" or "cephalo" in init_res["result"]["serverInfo"]["name"]

    # 2. Test tools/list
    tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    proc.stdin.write(json.dumps(tools_req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    tools_res = json.loads(line)
    assert tools_res["id"] == 2
    tool_names = [t["name"] for t in tools_res["result"]["tools"]]
    assert "cephalo_search" in tool_names
    assert "cephalo_record" in tool_names
    assert "cephalo_get_profile" in tool_names
    assert "cephalo_continuous_learn" in tool_names
    assert "cephalo_deep_research" in tool_names

    # 3. Test tools/call cephalo_learning_status
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "cephalo_learning_status",
            "arguments": {},
        },
    }
    proc.stdin.write(json.dumps(call_req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    call_res = json.loads(line)
    assert call_res["id"] == 3
    content_text = call_res["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert data["status"] == "success"
    assert "tracked_projects" in data["state"]

    proc.stdin.close()
    proc.terminate()
    print("All MCP protocol tests passed successfully!")

if __name__ == "__main__":
    test_mcp_protocol()
