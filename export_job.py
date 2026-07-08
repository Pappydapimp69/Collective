#!/usr/bin/env python3
"""Core -> public export job. Runs entirely INSIDE `collective` — this file is
never installed into Brain/memory/ideas/tension/creativity. It only ever READS
those repos (same access level anyone with read permission already has) and
writes exclusively into collective's own tree.

Zero-touch-to-core invariant: nothing in this module has a write path back
into a private repo. `fetch_private_entry` is injected so this is fully unit
testable without a live GitHub credential.

Allow-list is external to core: allowlist.json lives in `collective`, keyed by
(file, id) pairs, not a tag inside the private entry itself — see the plan's
"latest revision" section for why.

Note on `type` vs `repo` in AllowlistEntry (added 2026-07-08, after tension/
creativity access was confirmed): `repo` is which PRIVATE repo to fetch from;
`type` is which of collective's four public folders the entry belongs to.
These used to always match 1:1, but they no longer do for creativity — the
private `creativity` repo is FROZEN (see its README), so live
creativity-shaped entries are sourced from `ideas/exploration.md` instead
(repo="ideas", type="creativity"). Historical entries from the frozen
`creativity/creativity-log.md` can still be allow-listed too (repo="creativity",
type="creativity") as read-only legacy — both route through the same
extractor since they share the same ledger-style entry shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

# --------------------------------------------------------------------------- allowlist

@dataclass(frozen=True)
class AllowlistEntry:
    repo: str          # source private repo: "memory" | "ideas" | "tension" | "creativity"
    file: str          # e.g. "projects/pappydapimp69__chronicles.md"
    entry_id: str       # e.g. "E1" — NOT globally unique alone, hence the (file, id) pair
    type: str          # target collective folder/extractor: "memory" | "ideas" | "tension" | "creativity"
                        # usually == repo, EXCEPT creativity entries sourced from
                        # ideas/exploration.md (repo="ideas", type="creativity")


def load_allowlist(raw_json: str) -> list[AllowlistEntry]:
    data = json.loads(raw_json) if raw_json else []
    return [
        AllowlistEntry(repo=d["repo"], file=d["file"], entry_id=d["id"], type=d.get("type", d["repo"]))
        for d in data
    ]


def allowlist_key(repo: str, file: str, entry_id: str) -> str:
    return f"{repo}:{file}#{entry_id}"


# --------------------------------------------------------------------------- redaction
# Allow-listing controls WHICH entries export; redaction controls WHAT INSIDE
# them exports — applied even to entries that were explicitly opted in.

_SESSION_LINK_RE = re.compile(r"(Link:\s*).*", re.I)
# Consume the WHOLE rest of the line after the verified/assumed token, not
# just the token itself — otherwise trailing detail ("...from prior lesson.")
# survives redaction untouched (caught by test_coarsens_provenance).
_PROVENANCE_DETAIL_RE = re.compile(
    r"(Provenance[^:]*:\s*)(verified first-hand|assumed)[^\n]*", re.I
)


def redact(entry_text: str) -> str:
    """Strip session IDs / internal links and collapse provenance to a coarse
    label, dropping any trailing detail on that line. Applied on top of
    allow-listing, not instead of it."""
    out = _SESSION_LINK_RE.sub(r"\1[redacted]", entry_text)
    out = _PROVENANCE_DETAIL_RE.sub(lambda m: m.group(1) + m.group(2).split()[0].lower(), out)
    return out


# --------------------------------------------------------------------------- snapshot generation

FetchFn = Callable[[str, str], str]  # (repo, file) -> raw file text, read-only


def build_snapshot(
    allowlist: Iterable[AllowlistEntry],
    fetch_private_entry: FetchFn,
    extractors: dict[str, Callable[[str, str], str]],
    source_commits: dict[str, str],
    now: datetime | None = None,
) -> dict:
    """Read-only: fetch each allow-listed entry's raw text (via the injected
    fetcher), extract just that entry, redact it, and assemble the exportable
    snapshot. Never writes to the source repo.

    `extractors` is keyed by AllowlistEntry.type (the target collective
    folder), NOT by AllowlistEntry.repo — the two diverge for creativity
    entries sourced from ideas/exploration.md (repo="ideas", type="creativity"),
    so dispatch must go by type, not by source repo."""
    now = now or datetime.now(timezone.utc)
    entries = []
    for a in allowlist:
        raw_file_text = fetch_private_entry(a.repo, a.file)
        raw_entry_text = extractors[a.type](raw_file_text, a.entry_id)
        entries.append({
            "repo": a.repo,
            "file": a.file,
            "id": a.entry_id,
            "type": a.type,
            "text": redact(raw_entry_text),
        })
    return {
        "generated": now.isoformat(),
        "source_commits": source_commits,  # {repo: sha} at fetch time
        "entries": entries,
    }


def extract_memory_entry(file_text: str, entry_id: str) -> str:
    """Pull a single '## E<n> — ...' block out of a memory projects/*.md file."""
    pattern = re.compile(
        rf"^## {re.escape(entry_id)}\b.*?(?=^## E\d+\b|\Z)", re.M | re.S
    )
    m = pattern.search(file_text)
    return m.group(0).strip() if m else ""


def extract_ideas_entry(file_text: str, entry_id: str) -> str:
    """Pull a single '## [DOMAIN / ...]' fragment out of idea-repository.md.
    Unlike memory, ideas entries have no numeric ID — the allowlist's `id`
    field for an ideas entry IS the domain header text (or a unique substring
    of it), since that's the only stable identifier ideas' own convention
    provides. A DIFFERENT extractor from memory's, deliberately — the two
    repos don't share an entry-identity scheme, so one function can't serve
    both (an earlier draft of this export job assumed it could)."""
    pattern = re.compile(
        rf"^## \[[^\]]*{re.escape(entry_id)}[^\]]*\].*?(?=^## \[|\Z)", re.M | re.S
    )
    m = pattern.search(file_text)
    return m.group(0).strip() if m else ""


def _extract_ledger_style_entry(file_text: str, entry_id: str) -> str:
    """Shared implementation for the ledger-style entry shape confirmed
    (2026-07-08) in tension-ledger.md, creativity-log.md, AND
    ideas/exploration.md: '### <id> · <type> · <title>[ · **<state>**]' at
    `###` level (one level under a '## Project: ...' section heading), block
    runs to the next '### ' or EOF. IDs are alnum with a numeric tail (T1,
    A1, E1, S1, Sp1, ...) — `\\b` after the id prevents T1 matching inside T10."""
    pattern = re.compile(
        rf"^### {re.escape(entry_id)}\b.*?(?=^### |\Z)", re.M | re.S
    )
    m = pattern.search(file_text)
    return m.group(0).strip() if m else ""


def extract_tension_entry(file_text: str, entry_id: str) -> str:
    """Pull a single '### T<n> · <type> · <title>' block out of
    tension-ledger.md. A third entry-identity scheme, distinct from both
    memory's (bare numeric '## E<n>') and ideas' (domain-bracketed '## [...]',
    no numeric id): tension's id IS numeric like memory's, but the header
    line also carries type+title inline, and entries sit one heading level
    deeper (### under a ## Project: section)."""
    return _extract_ledger_style_entry(file_text, entry_id)


def extract_creativity_entry(file_text: str, entry_id: str) -> str:
    """Pull a single ledger-style block out of EITHER ideas/exploration.md
    (live creativity-shaped content: experiment/synthesis/speculation, ids
    like E1/S1/Sp1 that reset per type prefix) or the frozen
    creativity/creativity-log.md (historical, read-only legacy entries, same
    header shape). Kept as its own function rather than reused as an alias
    for extract_tension_entry: the two repos' entry-identity schemes match
    today only because of the 2026-07-02 migration that gave them the same
    shape — that's a fact about current content, not a guaranteed invariant,
    so a future divergence in either format won't silently break the other's
    export (same reasoning as keeping memory/ideas separate)."""
    return _extract_ledger_style_entry(file_text, entry_id)


# Dispatch by TARGET TYPE (the collective public folder), not by source repo
# — see AllowlistEntry.type and build_snapshot's docstring for why creativity
# breaks the repo==type assumption the other three still hold.
EXTRACTORS = {
    "memory": extract_memory_entry,
    "ideas": extract_ideas_entry,
    "tension": extract_tension_entry,
    "creativity": extract_creativity_entry,
}


def render_index_md(snapshot: dict) -> str:
    """Human-readable index, DERIVED from the JSON snapshot — never hand-edited."""
    lines = [f"# collective index — generated {snapshot['generated']}", ""]
    for e in snapshot["entries"]:
        first_line = e["text"].splitlines()[0] if e["text"] else "(empty)"
        lines.append(f"- `{e['repo']}:{e['file']}#{e['id']}` — {first_line}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- retraction diffing
# Populated when an id present in a PREVIOUS export's allowlist is absent from
# the CURRENT one (a human untagged it — canon itself is append-only so the
# private entry was never deleted, just made public-ineligible). Pure
# core->public logic — no read-back from collective required.

def diff_retractions(previous_keys: set[str], current_keys: set[str], reason: str,
                      now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    removed = previous_keys - current_keys
    return [{"key": k, "reason": reason, "date": now.date().isoformat()} for k in sorted(removed)]
