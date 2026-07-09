#!/usr/bin/env python3
"""Tests for export_job.py — proves the allow-list/redaction/retraction logic
without any live git or GitHub API access (fetch is injected)."""

import unittest
from datetime import datetime, timezone

from export_job import (
    EXTRACTORS,
    allowlist_key,
    build_snapshot,
    diff_retractions,
    extract_creativity_entry,
    extract_ideas_entry,
    extract_memory_entry,
    extract_tension_entry,
    load_allowlist,
    redact,
    render_index_md,
)

FAKE_IDEAS_FILE = """# IDEA REPOSITORY

## [RPG / narrative-design / legendary-transformation / survivorship-bias]

Story: player unlocks a "legendary" transformation seemingly contradicting its status.

## [RPG / progression / archetype-plus-use-skills]

Front-load identity with a data-driven archetype template at character creation.

## [SYSTEM / crowdsource / plant-network / anonymized-aggregation]

A crowdsourced plant-observation layer keyed by species and zip code only.
"""

FAKE_MEMORY_FILE = """# pappydapimp69/chronicles — lessons

## E1 — chronicles state atomicity
- Date: 2026-07-05
- Tags: [coop][state]
- Provenance: Assumed from prior lesson.
- Link: https://claude.ai/code/session_012KNCvEWeDx6jHCwjAZmoCJ

## E2 — some other lesson
- Date: 2026-07-06
- Provenance: Verified first-hand.
- Link: https://claude.ai/code/session_099ZZZ
"""

# Shaped like the real tension/tension-ledger.md (confirmed 2026-07-08):
# "### T<n> · <type> · <title>" under a "## Project: ..." heading.
FAKE_TENSION_FILE = """# TENSION LEDGER

## Project: Echoes of the Shattered Realm — Milestone 0

### T1 · contradiction · systems-over-data vs a real ECS
Poles: a flat world is minimal for one player; a full ECS scales but is
overkill now.
Lean: 🟡 systems-over-data for the slice.
Source: ADR-0001.

### T10 · assumption · greybox-first keeps schedule
Bet: boxy geometry is acceptable interim art.
Lean: 🟡 holds.
Source: docs/05 risk R3.

### T15 · process · shipping cadence vs cognitive-logging cadence
Lean: 🟡 add a second trigger.
Source: this session's patch series.
"""

# Shaped like the real ideas/exploration.md (confirmed 2026-07-08): same
# ledger header shape as tension, but type-prefixed alnum ids that reset per
# type (E1, S1, Sp1 — not a single global counter) and a trailing state.
FAKE_EXPLORATION_FILE = """# EXPLORATION — residue that isn't a kernel

## Project: Echoes of the Shattered Realm — Milestone 0

### E1 · experiment · sim-before-render · **live**
We built the entire game loop as a headless simulation before writing one
line of renderer.

### S1 · synthesis · pull the dormant RPG kernels into this world · **promoted → build**
Staged cross-pollination of filed kernels against the active build.

### Sp1 · speculation · two co-op paths, kept open · **live**
Lockstep vs authoritative server, kept open until co-op is scheduled.
"""

# Shaped like the real (frozen) creativity/creativity-log.md — same header
# shape as exploration.md but no trailing state annotation, proving one
# extractor handles both the live and historical creativity-shaped sources.
FAKE_CREATIVITY_LOG_FILE = """# CREATIVITY LOG (frozen, historical)

## Project: Echoes of the Shattered Realm — Milestone 0

### A1 · alternative · engine paths not taken
Considered before choosing Three.js + Vite + TS: Godot, Unity, Bevy.

### E1 · experiment · sim-before-render (proved the loop in a terminal first)
We built the entire game loop as a headless simulation.
"""


class TestAllowlist(unittest.TestCase):
    def test_loads_from_json(self):
        raw = '[{"repo": "memory", "file": "projects/x.md", "id": "E1"}]'
        entries = load_allowlist(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entry_id, "E1")

    def test_empty_allowlist_by_default(self):
        self.assertEqual(load_allowlist(""), [])
        self.assertEqual(load_allowlist("[]"), [])

    def test_key_disambiguates_same_id_across_files(self):
        k1 = allowlist_key("memory", "projects/a.md", "E1")
        k2 = allowlist_key("memory", "projects/b.md", "E1")
        self.assertNotEqual(k1, k2)

    def test_type_defaults_to_repo_when_omitted(self):
        raw = '[{"repo": "tension", "file": "tension-ledger.md", "id": "T1"}]'
        entries = load_allowlist(raw)
        self.assertEqual(entries[0].type, "tension")

    def test_type_can_diverge_from_repo_for_creativity(self):
        raw = '[{"repo": "ideas", "file": "exploration.md", "id": "E1", "type": "creativity"}]'
        entries = load_allowlist(raw)
        self.assertEqual(entries[0].repo, "ideas")
        self.assertEqual(entries[0].type, "creativity")


class TestRedaction(unittest.TestCase):
    def test_strips_session_link(self):
        out = redact("Link: https://claude.ai/code/session_012KNCvEWeDx6jHCwjAZmoCJ")
        self.assertNotIn("012KNCvEWeDx6jHCwjAZmoCJ", out)
        self.assertIn("[redacted]", out)

    def test_coarsens_provenance(self):
        out = redact("- Provenance (verified/assumed): Assumed from prior lesson.")
        self.assertIn("assumed", out.lower())
        self.assertNotIn("prior lesson", out)

    def test_leaves_normal_text_alone(self):
        text = "Resolve overlap participants by type, not argument order."
        self.assertEqual(redact(text), text)

    def test_does_not_eat_cross_link_field(self):
        # Regression: a dry run against real tension-ledger.md content found
        # the original "Link:" regex matching as a bare substring, so
        # "Cross-link:" (tension/creativity's wanted cross-reference field)
        # was being silently redacted along with memory's actual internal
        # "Link:" field — two different fields that happen to share three
        # letters, not the same thing.
        text = "Source: ADR-0005. Cross-link: `ideas` -> [NPC-SIM / emergent-traits]."
        self.assertEqual(redact(text), text)

    def test_still_strips_a_real_link_field_next_to_other_bullets(self):
        # Realistic shape: the real entries are bullet lists, so "the next
        # field" is signaled by a new "- " bullet, not just any newline.
        text = "- Notes: Notes here.\n- Link: https://claude.ai/code/session_ABC123\n- More: More notes."
        out = redact(text)
        self.assertNotIn("ABC123", out)
        self.assertIn("[redacted]", out)
        self.assertIn("Notes here.", out)
        self.assertIn("More notes.", out)

    def test_strips_link_field_wrapped_onto_a_continuation_line(self):
        # Regression: a dry run against the REAL projects/pappydapimp69__brain.md#E1
        # entry found the Link field's value wrapped onto an indented
        # continuation line (no "- " prefix, plain markdown line-wrap) — the
        # old same-line-only regex left that continuation line, including a
        # session date, sitting untouched right after "[redacted]".
        text = (
            "- Link: Brain commits (Windows install + hook), encoding-safety commit 4c1f147;\n"
            "  session 2026-07-04.\n"
            "- Next: unrelated field."
        )
        out = redact(text)
        self.assertNotIn("4c1f147", out)
        self.assertNotIn("2026-07-04", out)
        self.assertIn("[redacted]", out)
        self.assertIn("unrelated field.", out)

    def test_coarsens_provenance_wrapped_onto_continuation_lines(self):
        # Same bug, worse consequence: on the real entry, Provenance's detail
        # wrapped onto TWO continuation lines and survived in full — defeating
        # the entire point of coarsening it to just "verified"/"assumed".
        text = (
            "- Provenance (verified/assumed): VERIFIED first-hand — all three failures were\n"
            "  observed in a real Codex/Windows session this day, and each fix was made and\n"
            "  the Unix path regression-tested.\n"
            "- Link: https://claude.ai/code/session_ABC123"
        )
        out = redact(text)
        self.assertIn("verified", out.lower())
        self.assertNotIn("Codex/Windows session", out)
        self.assertNotIn("regression-tested", out)
        self.assertNotIn("ABC123", out)  # the following Link field still redacts too


class TestExtractMemoryEntry(unittest.TestCase):
    def test_extracts_correct_block_only(self):
        block = extract_memory_entry(FAKE_MEMORY_FILE, "E1")
        self.assertIn("chronicles state atomicity", block)
        self.assertNotIn("some other lesson", block)

    def test_missing_id_returns_empty(self):
        self.assertEqual(extract_memory_entry(FAKE_MEMORY_FILE, "E99"), "")


class TestExtractIdeasEntry(unittest.TestCase):
    def test_extracts_correct_fragment_by_domain_substring(self):
        block = extract_ideas_entry(FAKE_IDEAS_FILE, "archetype-plus-use-skills")
        self.assertIn("Front-load identity", block)
        self.assertNotIn("legendary-transformation", block)
        self.assertNotIn("crowdsourced plant-observation", block)

    def test_missing_id_returns_empty(self):
        self.assertEqual(extract_ideas_entry(FAKE_IDEAS_FILE, "no-such-domain"), "")

    def test_memory_extractor_cannot_be_reused_for_ideas(self):
        # Regression guard for the bug this was written to catch: memory's
        # '## E<n>' pattern simply never matches ideas' '## [DOMAIN / ...]'
        # headers, so silently reusing one extractor for both repos would
        # export nothing for ideas rather than erroring loudly.
        self.assertEqual(extract_memory_entry(FAKE_IDEAS_FILE, "archetype-plus-use-skills"), "")


class TestExtractorDispatchTable(unittest.TestCase):
    def test_dispatch_table_has_all_four_types(self):
        self.assertIn("memory", EXTRACTORS)
        self.assertIn("ideas", EXTRACTORS)
        self.assertIn("tension", EXTRACTORS)
        self.assertIn("creativity", EXTRACTORS)
        self.assertIs(EXTRACTORS["memory"], extract_memory_entry)
        self.assertIs(EXTRACTORS["ideas"], extract_ideas_entry)
        self.assertIs(EXTRACTORS["tension"], extract_tension_entry)
        self.assertIs(EXTRACTORS["creativity"], extract_creativity_entry)


class TestExtractTensionEntry(unittest.TestCase):
    def test_extracts_correct_block_only(self):
        block = extract_tension_entry(FAKE_TENSION_FILE, "T1")
        self.assertIn("systems-over-data vs a real ECS", block)
        self.assertNotIn("greybox-first", block)
        self.assertNotIn("shipping cadence", block)

    def test_numeric_prefix_collision_does_not_bleed(self):
        # T1 must not accidentally match inside T10 or vice versa.
        block = extract_tension_entry(FAKE_TENSION_FILE, "T1")
        self.assertNotIn("greybox-first", block)
        block10 = extract_tension_entry(FAKE_TENSION_FILE, "T10")
        self.assertIn("greybox-first", block10)
        self.assertNotIn("systems-over-data", block10)

    def test_undocumented_process_type_entry_still_extractable(self):
        # T15 uses the ledger's undocumented "process" type — the extractor
        # doesn't validate type, it just pulls the block by id.
        block = extract_tension_entry(FAKE_TENSION_FILE, "T15")
        self.assertIn("shipping cadence", block)

    def test_missing_id_returns_empty(self):
        self.assertEqual(extract_tension_entry(FAKE_TENSION_FILE, "T99"), "")

    def test_memory_and_ideas_extractors_cannot_be_reused_for_tension(self):
        # tension's "### T<n> · type · title" shape matches neither memory's
        # bare "## E<n>" nor ideas' "## [DOMAIN / ...]" — a third scheme.
        self.assertEqual(extract_memory_entry(FAKE_TENSION_FILE, "T1"), "")
        self.assertEqual(extract_ideas_entry(FAKE_TENSION_FILE, "T1"), "")


class TestExtractCreativityEntry(unittest.TestCase):
    def test_extracts_from_live_exploration_file(self):
        block = extract_creativity_entry(FAKE_EXPLORATION_FILE, "E1")
        self.assertIn("sim-before-render", block)
        self.assertNotIn("dormant RPG kernels", block)

    def test_type_prefixed_ids_do_not_collide_across_prefixes(self):
        # exploration.md resets numbering PER TYPE PREFIX (E1/S1/Sp1 can all
        # exist at once) — unlike tension's single global T<n> counter.
        e1 = extract_creativity_entry(FAKE_EXPLORATION_FILE, "E1")
        s1 = extract_creativity_entry(FAKE_EXPLORATION_FILE, "S1")
        sp1 = extract_creativity_entry(FAKE_EXPLORATION_FILE, "Sp1")
        self.assertIn("sim-before-render", e1)
        self.assertIn("dormant RPG kernels", s1)
        self.assertIn("two co-op paths", sp1)
        # S1 must not bleed into an Sp1 lookup or vice versa despite the
        # shared "S" prefix character.
        self.assertNotIn("co-op paths", s1)
        self.assertNotIn("dormant RPG kernels", sp1)

    def test_also_extracts_from_frozen_historical_creativity_log(self):
        # Same extractor serves the frozen creativity-log.md too — it shares
        # the ledger header shape, just without the trailing state marker.
        block = extract_creativity_entry(FAKE_CREATIVITY_LOG_FILE, "A1")
        self.assertIn("engine paths not taken", block)
        self.assertNotIn("sim-before-render (proved", block)

    def test_missing_id_returns_empty(self):
        self.assertEqual(extract_creativity_entry(FAKE_EXPLORATION_FILE, "E99"), "")

    def test_memory_and_ideas_extractors_cannot_be_reused_for_creativity(self):
        self.assertEqual(extract_memory_entry(FAKE_EXPLORATION_FILE, "E1"), "")
        self.assertEqual(extract_ideas_entry(FAKE_EXPLORATION_FILE, "E1"), "")


class TestBuildSnapshot(unittest.TestCase):
    def test_empty_allowlist_yields_empty_snapshot(self):
        snap = build_snapshot(
            [], lambda repo, f: FAKE_MEMORY_FILE, EXTRACTORS, {},
            now=datetime(2026, 7, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(snap["entries"], [])

    def test_snapshot_only_contains_allowlisted_and_redacted_entry(self):
        allowlist = load_allowlist(
            '[{"repo": "memory", "file": "projects/chronicles.md", "id": "E1", "type": "memory"}]'
        )
        snap = build_snapshot(
            allowlist, lambda repo, f: FAKE_MEMORY_FILE, EXTRACTORS,
            {"memory": "abc123"}, now=datetime(2026, 7, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(len(snap["entries"]), 1)
        self.assertIn("chronicles state atomicity", snap["entries"][0]["text"])
        self.assertNotIn("012KNCvEWeDx6jHCwjAZmoCJ", snap["entries"][0]["text"])
        self.assertNotIn("some other lesson", snap["entries"][0]["text"])
        self.assertEqual(snap["source_commits"], {"memory": "abc123"})

    def test_never_calls_fetcher_for_non_allowlisted_entries(self):
        # E2 exists in the fake file but isn't allow-listed — it must never
        # appear in the snapshot even though the fetcher returns the whole file.
        allowlist = load_allowlist(
            '[{"repo": "memory", "file": "projects/chronicles.md", "id": "E1", "type": "memory"}]'
        )
        snap = build_snapshot(allowlist, lambda r, f: FAKE_MEMORY_FILE, EXTRACTORS, {})
        ids = [e["id"] for e in snap["entries"]]
        self.assertNotIn("E2", ids)

    def test_dispatches_by_type_not_repo_for_creativity(self):
        # The core case this whole `type` field exists for: a creativity
        # entry sourced from repo="ideas" (exploration.md) must be extracted
        # with extract_creativity_entry, NOT extract_ideas_entry — dispatch
        # keys off AllowlistEntry.type, which diverges from .repo here.
        allowlist = load_allowlist(
            '[{"repo": "ideas", "file": "exploration.md", "id": "E1", "type": "creativity"}]'
        )

        def fetch(repo, path):
            self.assertEqual(repo, "ideas")
            self.assertEqual(path, "exploration.md")
            return FAKE_EXPLORATION_FILE

        snap = build_snapshot(allowlist, fetch, EXTRACTORS, {"ideas": "def456"})
        self.assertEqual(len(snap["entries"]), 1)
        self.assertIn("sim-before-render", snap["entries"][0]["text"])
        self.assertEqual(snap["entries"][0]["repo"], "ideas")
        self.assertEqual(snap["entries"][0]["type"], "creativity")

    def test_historical_creativity_repo_entry_also_dispatches_correctly(self):
        allowlist = load_allowlist(
            '[{"repo": "creativity", "file": "creativity-log.md", "id": "A1", "type": "creativity"}]'
        )
        snap = build_snapshot(
            allowlist, lambda r, f: FAKE_CREATIVITY_LOG_FILE, EXTRACTORS, {"creativity": "ghi789"},
        )
        self.assertEqual(len(snap["entries"]), 1)
        self.assertIn("engine paths not taken", snap["entries"][0]["text"])


class TestIndexRendering(unittest.TestCase):
    def test_index_is_derived_not_authoritative(self):
        snap = {
            "generated": "2026-07-08T00:00:00+00:00",
            "entries": [{"repo": "memory", "file": "projects/x.md", "id": "E1", "text": "First line\nmore"}],
        }
        md = render_index_md(snap)
        self.assertIn("memory:projects/x.md#E1", md)
        self.assertIn("First line", md)
        self.assertNotIn("more", md)  # only the first line goes in the index


class TestRetractionDiff(unittest.TestCase):
    def test_removed_id_is_retracted(self):
        prev = {"memory:projects/x.md#E1", "memory:projects/x.md#E2"}
        curr = {"memory:projects/x.md#E1"}
        out = diff_retractions(prev, curr, "no longer public-eligible",
                                now=datetime(2026, 7, 8, tzinfo=timezone.utc))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["key"], "memory:projects/x.md#E2")
        self.assertEqual(out[0]["date"], "2026-07-08")

    def test_no_removals_yields_no_retractions(self):
        keys = {"memory:projects/x.md#E1"}
        self.assertEqual(diff_retractions(keys, keys, "n/a"), [])

    def test_newly_added_id_is_not_a_retraction(self):
        prev = {"memory:projects/x.md#E1"}
        curr = {"memory:projects/x.md#E1", "memory:projects/x.md#E2"}
        self.assertEqual(diff_retractions(prev, curr, "n/a"), [])


if __name__ == "__main__":
    unittest.main()
