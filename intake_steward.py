#!/usr/bin/env python3
"""Collective intake steward — validates a public proposal before it may become
a mechanical-tier PR in the `collective` repo.

Reference implementation for the "Public collective — full 4-type system, zero
touches to core" plan. Mirrors the private `memory/scripts/validate.py` in
spirit (schema completeness, secret scanning) but is adapted for UNTRUSTED
public input arriving via a GitHub Issue Form, not a trusted contributor's PR.

Pure standard library, no dependencies. Does not touch git or the filesystem
beyond what's passed in — a GitHub Action wrapper is responsible for actually
committing output. See test_intake_steward.py for the adversarial test suite
this must survive before any live Action is wired to it (build order step 1
in the plan: "prototype standalone... nothing else gets built until this
holds").

Tension/creativity field lists are CONFIRMED (2026-07-08) against the real
`tension/tension-ledger.md` + `tension/README.md`, and against
`ideas/exploration.md` for creativity — see the TYPE_SCHEMAS comment below.
The private `creativity` repo itself is FROZEN (its own README says so); this
form deliberately targets the schema of where creativity-shaped content
actually lives today, not the dead repo's historical format.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

# --------------------------------------------------------------------------- limits

MAX_FIELD_LEN = 8_000  # generous for a lesson/idea write-up; guards against payload floods
MAX_TOTAL_LEN = 40_000
NEW_ACCOUNT_DAYS = 30
DAILY_CAP = 5
DAILY_CAP_NEW_ACCOUNT = 1

# --------------------------------------------------------------------------- schemas
# Field lists mirror each private repo's own schema as closely as possible.
# memory: memory/incoming/TEMPLATE.md + memory/INSTRUCTIONS.md "Entry schema".
# ideas: ideas/README.md FORMAT spec.
# tension: CONFIRMED against tension/tension-ledger.md + tension/README.md
#   (2026-07-08). Real entry shape is "### T<n> · <type> · <title>" followed by
#   a Poles:/Bet: line, a Lean: line (status embedded as an emoji, not a
#   separate field), and a Source: citation. `assumption`-typed entries use
#   "Bet:" in place of "Poles:" — see check_schema's tension branch.
# creativity: the private `creativity` repo is FROZEN (its own README says
#   "do not route new entries here" — demoted to a tagged section of `ideas`
#   in the 2026-07-02 Phase 1 ruling). Live creativity-shaped content
#   (experiment/synthesis/speculation) now lives in ideas/exploration.md,
#   using the same "### <id> · <type> · <title> · **<state>**" ledger shape.
#   Parked "alternative" entries migrated to `tension` instead — not accepted
#   here (see check_schema's creativity branch, which redirects them).
TYPE_SCHEMAS = {
    "memory": {
        "required": [
            "tags", "what", "why-built", "design", "got-right",
            "where-why-failed", "fix", "why-this-fix", "rule-of-thumb", "provenance",
        ],
        "optional": ["project", "link"],
    },
    "ideas": {
        "required": ["domain", "description"],
        "optional": ["tags", "artifact-test", "portability-test"],
    },
    "tension": {
        "required": ["type", "title", "lean", "source"],
        "optional": ["poles", "bet", "cross-link", "revisit-condition"],
    },
    "creativity": {
        "required": ["type", "title", "description"],
        "optional": ["state", "cross-link"],
    },
}

ESTABLISHED_DOMAINS = {
    "RPG", "NPC-SIM", "NARRATIVE-DESIGN", "WORLDBUILDING", "SYSTEM", "DATA-TOY", "GARDEN",
}

# tension-ledger.md's documented type vocabulary (tension/README.md). T15/T17
# also use an undocumented "process" type in the private ledger — a drift the
# ledger's own README doesn't sanction, so it's deliberately NOT accepted from
# public submissions here.
TENSION_TYPES = {"tradeoff", "assumption", "open-question", "contradiction", "alternative"}

# ideas/exploration.md's documented type vocabulary (ideas/README.md
# "EXPLORATION SECTION"). "alternative" is excluded on purpose — see
# check_schema's creativity branch.
CREATIVITY_TYPES = {"experiment", "synthesis", "speculation"}

TAG_TOKEN_RE = re.compile(r"\[[^\]]*\]")
GOOD_TAG_RE = re.compile(r"^\[[a-z0-9][a-z0-9._-]*\]$")

# --------------------------------------------------------------------------- issue-form parsing
# GitHub Issue Forms render submitted values as:
#   ### Field Label
#
#   value (possibly multi-line)
#
#   ### Next Field
# We parse by that structure and map label -> the field id via a label->id table
# supplied by the caller (built from the .yml form definitions), so this parser
# has no hardcoded dependency on exact label wording.

SECTION_RE = re.compile(r"^### (.+?)\s*$", re.M)

# The label->id map used to exist as a hand-maintained sidecar JSON file kept
# "in sync" with each Issue Form .yml by hand — an end-to-end test caught the
# real failure mode: a field silently disappears (not an error) the moment
# the two drift, e.g. a label edited in the form but not in the sidecar.
# Fix: derive the map directly FROM the form .yml, so there is exactly one
# source of truth. This is a small tolerant scanner, not a full YAML parser
# (stdlib has none) — it only needs to handle the specific, controlled shape
# of these generated forms: a top-level `body:` list of blocks, each with
# `id:` and, nested under `attributes:`, a `label:`.

_FORM_ID_RE = re.compile(r"^\s*-\s*type:\s*\S+\s*\n\s*id:\s*(\S+)\s*$", re.M)
_FORM_BLOCK_SPLIT_RE = re.compile(r"^\s*-\s*type:\s*\S+\s*$", re.M)
_FORM_LABEL_RE = re.compile(r"^\s*label:\s*(.+?)\s*$", re.M)
_FORM_ID_LINE_RE = re.compile(r"^\s*id:\s*(\S+)\s*$", re.M)


def derive_label_map(form_yaml_text: str) -> dict[str, str]:
    """Extract {label text: field id} from an Issue Form .yml's raw text,
    without a YAML dependency. Single source of truth: edit the form, the map
    updates itself — nothing to keep in sync by hand."""
    label_to_id: dict[str, str] = {}
    # Split on each top-level list item ("- type: ..."); each chunk holds at
    # most one `id:` and one `label:` (markdown/input body items skip one or
    # both — markdown blocks have no id, and we simply don't map those).
    blocks = _FORM_BLOCK_SPLIT_RE.split(form_yaml_text)[1:]  # [0] is the preamble before the first block
    for block in blocks:
        id_m = _FORM_ID_LINE_RE.search(block)
        label_m = _FORM_LABEL_RE.search(block)
        if id_m and label_m:
            label = label_m.group(1).strip().strip('"').strip("'")
            label_to_id[label] = id_m.group(1).strip()
    return label_to_id


def parse_issue_form_body(body: str, label_to_id: dict[str, str]) -> dict[str, str]:
    """Parse a rendered GitHub Issue Form body into {field_id: value}."""
    if body is None:
        return {}
    matches = list(SECTION_RE.finditer(body))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        if value in ("_No response_", ""):
            value = ""
        field_id = label_to_id.get(label)
        if field_id:
            out[field_id] = value
    return out


# --------------------------------------------------------------------------- schema check

def check_schema(entry_type: str, fields: dict[str, str]) -> list[str]:
    errors = []
    schema = TYPE_SCHEMAS.get(entry_type)
    if schema is None:
        return [f"unknown entry type '{entry_type}'"]
    for name in schema["required"]:
        if not fields.get(name, "").strip():
            errors.append(f"missing required field '{name}'")
    total_len = sum(len(v) for v in fields.values())
    if total_len > MAX_TOTAL_LEN:
        errors.append(f"submission too large ({total_len} chars, max {MAX_TOTAL_LEN})")
    for name, value in fields.items():
        if len(value) > MAX_FIELD_LEN:
            errors.append(f"field '{name}' too large ({len(value)} chars, max {MAX_FIELD_LEN})")
    if entry_type == "memory":
        tags_ok, tag_errs = _check_tags(fields.get("tags", ""))
        errors.extend(tag_errs)
    if entry_type == "ideas":
        domain = fields.get("domain", "").split("/")[0].strip().upper()
        if domain and domain not in ESTABLISHED_DOMAINS:
            errors.append(
                f"domain '{domain}' is not an established domain "
                f"({', '.join(sorted(ESTABLISHED_DOMAINS))}) — flagged for human review, not rejected"
            )
    if entry_type == "tension":
        ttype = fields.get("type", "").strip().lower()
        if ttype and ttype not in TENSION_TYPES:
            errors.append(
                f"tension type '{ttype}' is not one of {', '.join(sorted(TENSION_TYPES))}"
            )
        if ttype == "assumption":
            if not fields.get("bet", "").strip():
                errors.append(
                    "assumption-type tension entries require 'bet' (the wagered claim) "
                    "in place of 'poles'"
                )
        elif not fields.get("poles", "").strip():
            errors.append("missing required field 'poles' (only type=assumption uses 'bet' instead)")
    if entry_type == "creativity":
        ctype = fields.get("type", "").strip().lower()
        if ctype == "alternative":
            errors.append(
                "type 'alternative' belongs to the tension-fork form now — creativity's parked "
                "alternatives migrated to the tension ledger (2026-07-02); resubmit there"
            )
        elif ctype and ctype not in CREATIVITY_TYPES:
            errors.append(
                f"creativity type '{ctype}' is not one of {', '.join(sorted(CREATIVITY_TYPES))}"
            )
    return errors


def _check_tags(tags_field: str) -> tuple[bool, list[str]]:
    errors = []
    toks = TAG_TOKEN_RE.findall(tags_field)
    if not toks:
        errors.append("Tags field has no [bracketed] tags")
    for t in toks:
        if not GOOD_TAG_RE.match(t):
            errors.append(f"bad tag {t!r} (use lowercase [a-z0-9._-], bracketed)")
    return (len(errors) == 0, errors)


# --------------------------------------------------------------------------- slug / filename
# The filename is ALWAYS server-derived — never taken verbatim from user input.
# This is the fix for the "no path-scoped write ACL" problem: even though the
# bot has full write to `collective`, nothing the contributor supplies can
# choose *where* that write lands.

_SLUG_SAFE_RE = re.compile(r"[^a-z0-9-]+")


def derive_slug(entry_type: str, seed_text: str, sequence: int) -> str:
    """Build a safe filename from a (possibly hostile) seed string + a
    server-controlled sequence number. Never trust seed_text as a path."""
    normalized = unicodedata.normalize("NFKD", seed_text or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().strip()
    slug = _SLUG_SAFE_RE.sub("-", lowered).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60] or "untitled"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date}__{entry_type}-{sequence:04d}__{slug}.md"
    # Defense in depth: reject if anything produced a path-like result despite
    # the sanitization above (should be structurally impossible, but assert it).
    if "/" in filename or ".." in filename or "\x00" in filename:
        raise ValueError("derived filename failed path-safety assertion")
    return filename


# --------------------------------------------------------------------------- injection defense
# Reactive by nature — the INVARIANT ("stored entries are reference data, never
# executed") is the real backstop for phrasing this deny-list misses. This is
# defense-in-depth, not the security boundary itself.

INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    re.compile(r"\bsystem\s*:\s*", re.I),
    re.compile(r"###?\s*(system|instructions|admin|root)\b", re.I),
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"\bjavascript\s*:", re.I),
    re.compile(r"\bdata\s*:\s*text/html", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"disregard (the )?(above|prior)", re.I),
    re.compile(r"BRAIN_ACK\s*=", re.I),  # attempt to forge an ack token from the old CLI gate
]

_ZERO_WIDTH_RE = re.compile(r"[​‌‍⁠﻿]")


def scan_injection(text: str) -> list[str]:
    hits = []
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            hits.append(f"possible injection phrasing matched: {pat.pattern}")
    if _ZERO_WIDTH_RE.search(text):
        hits.append("zero-width/invisible unicode characters present")
    return hits


# --------------------------------------------------------------------------- secret scan
# Lifted directly from memory/scripts/validate.py's SECRET_RES — copied, not
# imported, so collective has no dependency on the private repo at runtime.

SECRET_RES = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
        "private key",
    ),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*"
            r"['\"][^'\"]{12,}['\"]"
        ),
        "hardcoded credential",
    ),
]


def scan_secrets(text: str) -> list[str]:
    hits = []
    for rx, label in SECRET_RES:
        if rx.search(text):
            hits.append(f"possible {label} present")
    return hits


# --------------------------------------------------------------------------- moderation
# Deliberately BASIC per the plan ("a first line at launch, not a full trust &
# safety system") — a different problem from injection/schema poisoning above.
# Never echoes the matched content back in output.

MODERATION_PATTERNS = [
    re.compile(r"\b(kill yourself|kys)\b", re.I),
    re.compile(r"\b(https?://)?(bit\.ly|tinyurl|t\.co|is\.gd)\b", re.I),  # link-shorteners: spam signal
]


def scan_moderation(text: str) -> list[str]:
    return [f"moderation pattern hit (category redacted)" for pat in MODERATION_PATTERNS if pat.search(text)]


# --------------------------------------------------------------------------- dedup
# Kernel-dedup (per ideas/README.md) needs real judgment a regex can't fully
# replicate — this is a cheap PROXY only: exact/near-duplicate text is caught
# mechanically; true kernel-vs-tag dedup is left for human review, per design.

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dedup_check(entry_type: str, description: str, existing: list[str],
                 exact_threshold: float = 0.9, review_threshold: float = 0.6) -> str | None:
    """Returns None (no dup), 'duplicate' (reject), or 'needs-human-dedup-review'."""
    best = 0.0
    for other in existing:
        sim = jaccard_similarity(description, other)
        best = max(best, sim)
    if best >= exact_threshold:
        return "duplicate"
    if best >= review_threshold:
        return "needs-human-dedup-review"
    return None


# --------------------------------------------------------------------------- identity / rate limiting

@dataclass
class AccountInfo:
    login: str
    created_at: datetime  # UTC


def is_new_account(acct: AccountInfo, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return (now - acct.created_at).days < NEW_ACCOUNT_DAYS


class RateLimiter:
    """Anchored to the authenticated GitHub login (never IP, never a
    self-reported name — closes the "identity" gap flagged in the audit).
    Backing store is injected so the Action wrapper can persist it (e.g. a
    small JSON file committed alongside collective, or a GitHub Actions
    cache) — this class itself is pure logic, unit-testable without one."""

    def __init__(self, counts_by_login_and_day: dict[str, dict[str, int]] | None = None):
        self._counts = counts_by_login_and_day or {}

    def count_today(self, login: str, day: str) -> int:
        return self._counts.get(login, {}).get(day, 0)

    def record(self, login: str, day: str) -> None:
        self._counts.setdefault(login, {})
        self._counts[login][day] = self._counts[login].get(day, 0) + 1

    def check(self, login: str, day: str, cap: int) -> bool:
        """True if under cap (allowed to proceed)."""
        return self.count_today(login, day) < cap

    def to_json(self) -> str:
        return json.dumps(self._counts, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "RateLimiter":
        return cls(json.loads(s) if s else {})


# --------------------------------------------------------------------------- top-level result

@dataclass
class ValidationResult:
    status: str  # "accept" | "reject" | "moderation_hold" | "needs_human_review"
    reasons: list[str] = field(default_factory=list)
    filename: str | None = None
    tier: str | None = None  # "mechanical" once accepted


def validate_submission(
    entry_type: str,
    raw_fields: dict[str, str],
    *,
    account: AccountInfo,
    existing_descriptions: list[str],
    limiter: RateLimiter,
    sequence: int,
    now: datetime | None = None,
) -> ValidationResult:
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    full_text = "\n".join(raw_fields.values())

    # 1. moderation first — never auto-close, never leak content back, stop immediately on hit
    if scan_moderation(full_text):
        return ValidationResult(status="moderation_hold", reasons=["content flagged for moderation review"])

    # 2. schema
    schema_errors = check_schema(entry_type, raw_fields)
    if schema_errors:
        return ValidationResult(status="reject", reasons=schema_errors)

    # 3. injection + secrets (structural poisoning, distinct from moderation)
    reasons = scan_injection(full_text) + scan_secrets(full_text)
    if reasons:
        return ValidationResult(status="reject", reasons=reasons)

    # 4. dedup
    description_field = (
        raw_fields.get("description")
        or raw_fields.get("what")
        or raw_fields.get("poles")
        or raw_fields.get("bet")
        or full_text
    )
    dup = dedup_check(entry_type, description_field, existing_descriptions)
    if dup == "duplicate":
        return ValidationResult(status="reject", reasons=["duplicate of an existing entry"])

    # 5. identity + rate limit
    new_acct = is_new_account(account, now)
    cap = DAILY_CAP_NEW_ACCOUNT if new_acct else DAILY_CAP
    if not limiter.check(account.login, day, cap):
        return ValidationResult(status="reject", reasons=[f"daily cap ({cap}) reached for this account"])

    # 6. derive filename (never from user input)
    seed = raw_fields.get("title") or raw_fields.get("what") or raw_fields.get("description") or ""
    filename = derive_slug(entry_type, seed, sequence)

    if new_acct or dup == "needs-human-dedup-review" or entry_type == "tension":
        # New accounts, borderline dedup, and ALL tension submissions (a
        # wrongly-marked-resolved public fork is worse than a stale open one)
        # never auto-land — human review regardless of a clean mechanical pass.
        limiter.record(account.login, day)
        return ValidationResult(
            status="needs_human_review",
            reasons=(["new account — forced review"] if new_acct else [])
            + (["borderline dedup match — forced review"] if dup else [])
            + (["tension entries are never auto-resolved/auto-landed"] if entry_type == "tension" else []),
            filename=filename,
            tier="mechanical",
        )

    limiter.record(account.login, day)
    return ValidationResult(status="accept", reasons=[], filename=filename, tier="mechanical")
