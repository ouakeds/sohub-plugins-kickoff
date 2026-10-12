"""Tests de hooks/confluence_guard.py (garde-fou Confluence de /confluence-sync)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hooks", "confluence_guard.py")
P = "mcp__claude_ai_Atlassian_MCP__"


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.projet = os.path.join(self.tmp.name, "projet")
        os.makedirs(os.path.join(self.projet, ".sohub-plugin"))
        with open(os.path.join(self.projet, ".sohub-plugin", "confluence.json"), "w", encoding="utf-8") as f:
            json.dump({"parent": {"spaceId": "9", "parentContentId": "100"}, "racine": {"id": "200"},
                       "pages": {"glossaire": {"id": "300"}}}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, args, stdin=""):
        env = dict(os.environ, HOME=self.home, USERPROFILE=self.home)
        return subprocess.run([sys.executable, "-I", SCRIPT] + args, input=stdin, capture_output=True,
                              text=True, env=env)

    def call(self, tool, tool_input):
        r = self.run_script(["hook"], json.dumps({"tool_name": tool, "tool_input": tool_input}))
        self.assertEqual(r.returncode, 0, r.stderr)
        if not r.stdout.strip():
            return None
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        return out["permissionDecisionReason"]

    def test_inactive_guard_lets_everything_through(self):
        self.assertIsNone(self.call(P + "getConfluenceContent", {"content_id": "999"}))
        self.assertIsNone(self.call(P + "search", {"query": "salaires"}))

    def test_project_pages_allowed(self):
        self.run_script(["on", self.projet])
        self.assertIsNone(self.call(P + "getConfluenceContent", {"cloudId": "c", "content_id": "200"}))
        self.assertIsNone(self.call(P + "getConfluenceContent",
                                    {"cloudId": "c", "content_url": "https://x.atlassian.net/wiki/spaces/S/pages/100/Parent"}))
        self.assertIsNone(self.call(P + "createConfluenceContent", {"cloudId": "c", "parent": {"spaceId": "9", "parentContentId": "200"},
                                                                     "contentType": "page", "title": "T"}))
        self.assertIsNone(self.call(P + "updateConfluenceContent", {"cloudId": "c", "contentId": "300"}))
        self.assertIsNone(self.call(P + "executeRead", {"name": "getConfluenceContentDescendants", "inputs": {"id": "200"}}))
        self.assertIsNone(self.call(P + "executeWrite", {"name": "moveConfluenceContent",
                                                         "inputs": {"id": "300", "position": "before", "targetId": "200"}}))
        self.assertIsNone(self.call(P + "executeWrite", {"name": "setConfluenceContentStatus", "inputs": {"contentId": "300"}}))
        self.assertIsNone(self.call(P + "executeRead", {"name": "getContentFormatGuide", "inputs": {"toolName": "x"}}))

    def test_outside_pages_refused(self):
        self.run_script(["on", self.projet])
        self.assertIn("999", self.call(P + "getConfluenceContent", {"cloudId": "c", "content_id": "999"}))
        self.assertIsNotNone(self.call(P + "getConfluenceContent", {"cloudId": "c", "content_id": "4_sXAQ"}))
        self.assertIsNotNone(self.call(P + "createConfluenceContent", {"cloudId": "c", "parent": {"spaceId": "9"},
                                                                        "contentType": "page", "title": "T"}))
        self.assertIsNotNone(self.call(P + "executeWrite", {"name": "moveConfluenceContent",
                                                            "inputs": {"id": "300", "targetId": "555"}}))
        self.assertIsNotNone(self.call(P + "executeRead", {"name": "getConfluenceSpace", "inputs": {"spaceIdOrKey": "S"}}))
        self.assertIsNotNone(self.call(P + "executeRead", {"name": "listConfluenceSpaces", "inputs": {}}))
        self.assertIsNotNone(self.call(P + "executeDestructive", {"name": "deleteConfluencePage", "inputs": {"id": "200"}}))
        self.assertIsNotNone(self.call(P + "searchConfluence", {"cql": "text ~ secret"}))
        self.assertIsNotNone(self.call(P + "search", {"query": "secret"}))

    def test_jira_and_metadata_untouched(self):
        self.run_script(["on", self.projet])
        self.assertIsNone(self.call(P + "getJiraIssue", {"cloudId": "c", "issueIdOrKey": "PROJ-1"}))
        self.assertIsNone(self.call(P + "executeRead", {"name": "getJiraIssueTransitions", "inputs": {}}))
        self.assertIsNone(self.call(P + "getAccessibleAtlassianResources", {}))
        self.assertIsNone(self.call("mcp__other__read", {"id": "999"}))

    def test_off_and_expiry(self):
        self.run_script(["on", self.projet])
        self.run_script(["off", self.projet])
        self.assertIsNone(self.call(P + "getConfluenceContent", {"content_id": "999"}))
        self.run_script(["on", self.projet])
        d = os.path.join(self.home, ".claude", "sohub-plugins-spec", "garde-confluence")
        for f in os.listdir(d):
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                json.dump({"projet": self.projet, "expire": 1}, fh)
        self.assertIsNone(self.call(P + "getConfluenceContent", {"content_id": "999"}))
        self.assertEqual(os.listdir(d), [])

    def test_bad_usage(self):
        self.assertEqual(self.run_script(["on", "/nexiste/pas"]).returncode, 2)
        r = self.run_script(["hook"], "pas du json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
