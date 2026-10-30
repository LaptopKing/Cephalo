#!/usr/bin/env python3
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "tests" else SCRIPT_DIR
MCP_SERVER = ROOT_DIR / "src" / "cephalo" / "services" / "mcp_server.py"


class TestMcpServer(unittest.TestCase):
    """Integration test suite for the Cephalo Model Context Protocol (MCP) server."""

    def test_mcp_protocol(self):
        proc = subprocess.Popen(
            [sys.executable, str(MCP_SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            # 1. Test initialize
            init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            init_res = json.loads(line)
            self.assertEqual(init_res["id"], 1)
            self.assertIn("capabilities", init_res["result"])
            server_name = init_res["result"]["serverInfo"]["name"]
            self.assertTrue(server_name == "cephalo-mcp" or "cephalo" in server_name)

            # 2. Test tools/list
            tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            proc.stdin.write(json.dumps(tools_req) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            tools_res = json.loads(line)
            self.assertEqual(tools_res["id"], 2)
            tool_names = [t["name"] for t in tools_res["result"]["tools"]]
            self.assertIn("cephalo_search", tool_names)
            self.assertIn("cephalo_record", tool_names)
            self.assertIn("cephalo_get_profile", tool_names)
            self.assertIn("cephalo_continuous_learn", tool_names)
            self.assertIn("cephalo_deep_research", tool_names)
            self.assertIn("cephalo_web_search", tool_names)
            self.assertIn("cephalo_web_fetch", tool_names)

            # 3. Test tools/call cephalo_web_search
            web_call_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "cephalo_web_search",
                    "arguments": {"query": "FastAPI python", "limit": 2},
                },
            }
            proc.stdin.write(json.dumps(web_call_req) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            web_res = json.loads(line)
            self.assertEqual(web_res["id"], 3)
            web_data = json.loads(web_res["result"]["content"][0]["text"])
            self.assertIn("quick_summary", web_data)
            self.assertIn("organic_results", web_data)

            # 4. Test tools/call cephalo_learning_status
            call_req = {
                "jsonrpc": "2.0",
                "id": 4,
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
            self.assertEqual(call_res["id"], 4)
            content_text = call_res["result"]["content"][0]["text"]
            data = json.loads(content_text)
            self.assertEqual(data["status"], "success")
            self.assertIn("tracked_projects", data["state"])

        finally:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
            if proc.stderr and not proc.stderr.closed:
                proc.stderr.close()
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()

