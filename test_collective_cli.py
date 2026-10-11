"""Tests for collective.py, the local snapshot client. The repo checkout itself
is served as the 'remote' through a file:// URL, and the GitHub API call is
stubbed, so nothing here touches the network."""
import io
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import collective as c

ROOT = pathlib.Path(__file__).resolve().parent


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.patches = [
            mock.patch.object(c, "HOME", self.tmp),
            mock.patch.object(c, "RAW", ROOT.as_uri()),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def run_cmd(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = c.main(list(argv))
        return code, out.getvalue()

    def pull(self):
        code, out = self.run_cmd("pull")
        self.assertEqual(code, 0, out)
        return out

    # ---------------------------------------------------------- read-only path

    def test_default_mode_is_read_only(self):
        self.assertEqual(c.config()["mode"], "read-only")

    def test_pull_stores_snapshot_locally(self):
        out = self.pull()
        for t in c.TYPES:
            local = json.loads(pathlib.Path(self.tmp, "snapshot", f"{t}.json").read_text())
            published = json.loads((ROOT / "snapshot" / t / "canon.json").read_text())
            self.assertEqual(len(local["entries"]), len(published["entries"]))
        self.assertIn("mode: read-only", out)

    def test_pull_drops_retracted_entries(self):
        first = json.loads((ROOT / "snapshot" / "memory" / "canon.json").read_text())["entries"][0]
        key = f"{first['repo']}:{first['file']}#{first['id']}"
        real_fetch = c.fetch

        def fake_fetch(rel, optional=False):
            if rel == "memory/retracted.json":
                return json.dumps([{"key": key, "reason": "test", "date": "2026-01-01"}])
            return real_fetch(rel, optional)

        with mock.patch.object(c, "fetch", fake_fetch):
            self.pull()
        ids = [(e["file"], e["id"]) for e in c.snapshot("memory")]
        self.assertNotIn((first["file"], first["id"]), ids)

    def test_query_finds_a_known_entry(self):
        self.pull()
        code, out = self.run_cmd("query", "tampermonkey")
        self.assertEqual(code, 0)
        self.assertIn("[memory]", out)

    def test_show_needs_project_for_repeated_memory_ids(self):
        self.pull()
        code, out = self.run_cmd("show", "memory", "E1")
        self.assertEqual(code, 1)
        self.assertIn("#E1", out)
        first = out.split("use one of:")[1].split()[0]
        code, out = self.run_cmd("show", "memory", first)
        self.assertEqual(code, 0)
        self.assertIn("## E1", out)

    def test_query_without_snapshot_says_pull(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("query", "anything")
        self.assertIn("collective pull", str(cm.exception))

    # ---------------------------------------------------------- proposals

    def write_full_draft(self):
        self.pull()
        self.run_cmd("propose", "memory", "--title", "Pointer events need a real window")
        name = os.listdir(os.path.join(self.tmp, "proposals"))[0]
        p = os.path.join(self.tmp, "proposals", name)
        text = pathlib.Path(p).read_text()
        for _, label, _ in c.form_fields("memory"):
            filler = "[browser][events]" if label.startswith("Tags") else \
                "A synthetic click built with the wrong window object was rejected by the browser."
            text = text.replace(f"### {label}\n\n(required)\n", f"### {label}\n\n{filler}\n")
            text = text.replace(f"### {label}\n\n\n", f"### {label}\n\n{filler}\n")
        pathlib.Path(p).write_text(text)
        return p

    def test_propose_writes_a_local_draft_from_the_form(self):
        self.pull()
        code, out = self.run_cmd("propose", "memory", "--title", "x")
        self.assertEqual(code, 0)
        self.assertIn("local only", out)
        drafts = os.listdir(os.path.join(self.tmp, "proposals"))
        text = pathlib.Path(self.tmp, "proposals", drafts[0]).read_text()
        self.assertIn("### Rule of thumb", text)

    def test_check_flags_empty_required_fields(self):
        self.pull()
        self.run_cmd("propose", "memory", "--title", "x")
        name = os.listdir(os.path.join(self.tmp, "proposals"))[0]
        code, out = self.run_cmd("check", name)
        self.assertEqual(code, 1)
        self.assertIn("is empty", out)

    def test_check_passes_a_filled_draft(self):
        p = self.write_full_draft()
        code, out = self.run_cmd("check", p)
        self.assertEqual(code, 0, out)

    def test_send_refuses_in_read_only_mode_and_sends_nothing(self):
        p = self.write_full_draft()
        with mock.patch.object(c, "open_issue") as oi:
            code, out = self.run_cmd("send", p, "--yes")
        self.assertEqual(code, 1)
        self.assertIn("read-only", out)
        oi.assert_not_called()
        self.assertTrue(os.path.exists(p))

    def test_mode_full_needs_confirmation(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.run_cmd("mode", "full")
        self.assertEqual(c.config()["mode"], "read-only")
        self.run_cmd("mode", "full", "--yes")
        self.assertEqual(c.config()["mode"], "full")

    def test_send_in_full_mode_opens_one_issue_and_files_the_draft(self):
        p = self.write_full_draft()
        self.run_cmd("mode", "full", "--yes")
        with mock.patch.object(c, "github_token", return_value="t"), \
                mock.patch.object(c, "open_issue", return_value="https://x/issues/1") as oi:
            code, out = self.run_cmd("send", p, "--yes")
        self.assertEqual(code, 0, out)
        oi.assert_called_once()
        _, title, body, labels = oi.call_args[0]
        self.assertTrue(title.startswith("[memory] "))  # type survives even if labels are dropped
        self.assertEqual(labels, ["intake:memory"])
        self.assertIn("### Rule of thumb", body)
        self.assertNotIn("(required)", body)
        self.assertFalse(os.path.exists(p))
        self.assertTrue(os.listdir(os.path.join(self.tmp, "proposals", "sent")))

    def test_send_in_full_mode_without_terminal_does_not_send_unconfirmed(self):
        p = self.write_full_draft()
        self.run_cmd("mode", "full", "--yes")
        with mock.patch.object(c, "github_token", return_value="t"), \
                mock.patch.object(c, "open_issue") as oi, \
                mock.patch("sys.stdin.isatty", return_value=False):
            self.run_cmd("send", p)
        oi.assert_not_called()
        self.assertTrue(os.path.exists(p))


if __name__ == "__main__":
    unittest.main()
