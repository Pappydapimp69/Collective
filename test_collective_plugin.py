"""Offline tests for the Collective plugin's read-only CLI, run against this checkout's snapshot."""
import contextlib
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "collective-plugin", "skills", "collective", "scripts"))
import collective  # noqa: E402


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = collective.main(["--local", HERE, *argv])
    return code, out.getvalue()


class CollectivePluginTest(unittest.TestCase):
    def test_manifests_parse_and_point_at_plugin(self):
        mk = json.load(open(os.path.join(HERE, ".claude-plugin", "marketplace.json")))
        src = mk["plugins"][0]["source"]
        pj = json.load(open(os.path.join(HERE, src, ".claude-plugin", "plugin.json")))
        self.assertEqual(pj["name"], mk["plugins"][0]["name"])

    def test_skills_have_frontmatter(self):
        for s in ("collective", "zanegpt"):
            text = open(os.path.join(HERE, "collective-plugin", "skills", s, "SKILL.md")).read()
            self.assertTrue(text.startswith(f"---\nname: {s}\ndescription: "), s)

    def test_status_counts_every_type(self):
        code, out = run("status")
        self.assertEqual(code, 0)
        for t in collective.TYPES:
            self.assertIn(t, out)

    def test_query_finds_and_retries_phrasing(self):
        _, out = run("query", "determinism")
        self.assertIn("T2", out)
        _, out = run("query", "zzz-no-such-thing")
        self.assertIn("no records", out)

    def test_retracted_entries_are_filtered(self):
        canon, _ = collective.load(HERE)
        victim = canon["tension"][0]
        real_fetch = collective.fetch
        retract = json.dumps([{"file": victim["file"], "id": victim["id"]}])
        collective.fetch = lambda p, l: retract if p == "tension/retracted.json" else real_fetch(p, l)
        try:
            canon2, _ = collective.load(HERE)
        finally:
            collective.fetch = real_fetch
        self.assertNotIn(victim, canon2["tension"])
        self.assertEqual(len(canon2["tension"]), len(canon["tension"]) - 1)

    def test_challenge_sections(self):
        code, out = run("challenge", "determinism")
        self.assertEqual(code, 0)
        for section in ("PREMISE", "OBSERVATIONS", "INTERPRETATIONS", "OPEN FORKS", "MISSING VARIABLES", "NEXT MOVE"):
            self.assertIn(section, out)

    def test_not_verified_is_not_tested(self):
        self.assertFalse(collective.tested({"text": "- Provenance (not verified): not verified"}))
        self.assertTrue(collective.tested({"text": "- Provenance (verified/assumed): verified"}))

    def test_gaps_lists_index(self):
        _, out = run("gaps")
        self.assertIn("gap(s)", out)
        self.assertIn("raw.githubusercontent.com", out)


if __name__ == "__main__":
    unittest.main()
