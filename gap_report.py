#!/usr/bin/env python3
"""Read-only status report over the public gaps/ folder.

Run it any time to see what the public training-mode path has produced — one
line per gap (domain, type, status, how many sessions, last touched), with the
gaps that reached `converging` called out separately, because convergence is
the signal for a human to go LOOK, never an automatic promotion (see
gaps/README.md). This script only READS; it holds no credentials and writes
nothing back. Output is Markdown, meant for a GitHub Actions job summary or a
terminal.

    python3 gap_report.py [gaps_dir]   # default: gaps
"""

from __future__ import annotations

import glob
import os
import re
import sys

HEADER_RE = re.compile(r"^-\s*\*\*(?P<key>[^:*]+):\*\*\s*(?P<val>.*)$")
TITLE_RE = re.compile(r"^#\s*Gap:\s*(?P<title>.+)$")
SESSION_RE = re.compile(r"^###\s+(?P<date>\S+)\s+·\s+(?P<mode>\S+)")


def parse_gap(path: str) -> dict:
    title, domain, gtype, status = "", "", "", ""
    session_dates: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = TITLE_RE.match(line)
            if m and not title:
                title = m.group("title").strip()
                continue
            m = HEADER_RE.match(line)
            if m:
                key = m.group("key").strip().lower()
                val = m.group("val").strip()
                if key == "domain":
                    domain = val
                elif key == "type":
                    gtype = val
                elif key == "status":
                    status = val.lower()
                continue
            m = SESSION_RE.match(line)
            if m:
                session_dates.append(m.group("date"))
    return {
        "file": os.path.basename(path),
        "title": title or "(untitled)",
        "domain": domain or "—",
        "type": gtype or "—",
        "status": status or "—",
        "sessions": len(session_dates),
        "last": max(session_dates) if session_dates else "—",
    }


def build_report(gaps_dir: str) -> str:
    slug = re.compile(r"^[a-z0-9][a-z0-9-]*\.md$")
    paths = sorted(
        p for p in glob.glob(os.path.join(gaps_dir, "*.md"))
        if slug.match(os.path.basename(p))
    )
    gaps = [parse_gap(p) for p in paths]

    total = len(gaps)
    total_sessions = sum(g["sessions"] for g in gaps)
    by_status: dict[str, int] = {}
    for g in gaps:
        by_status[g["status"]] = by_status.get(g["status"], 0) + 1
    converging = [g for g in gaps if g["status"] == "converging"]

    out: list[str] = []
    out.append("# Collective — gaps status report\n")
    if total == 0:
        out.append("No gaps recorded yet. The public training-mode path has produced nothing so far.\n")
        return "\n".join(out)

    status_line = ", ".join(f"{v} {k}" for k, v in sorted(by_status.items()))
    out.append(f"**{total} gaps** · **{total_sessions} sessions** logged · {status_line}\n")

    if converging:
        out.append("## ⚠️ Needs your eyes — converging (a human decides, not the count)\n")
        for g in converging:
            out.append(
                f"- **{g['title']}** — {g['sessions']} sessions, last {g['last']} "
                f"(`{g['file']}`)"
            )
        out.append("")

    out.append("## All gaps\n")
    out.append("| Gap | Domain | Type | Status | Sessions | Last |")
    out.append("|---|---|---|---|---|---|")
    for g in sorted(gaps, key=lambda x: (x["status"], -x["sessions"])):
        title = g["title"] if len(g["title"]) <= 70 else g["title"][:67] + "…"
        out.append(
            f"| {title} | {g['domain']} | {g['type']} | {g['status']} "
            f"| {g['sessions']} | {g['last']} |"
        )
    out.append("")
    out.append(
        "_Convergence flags a gap for a human to read the content — it is never proof "
        "and never closes a gap on its own. See `gaps/README.md`._"
    )
    return "\n".join(out)


def main() -> int:
    gaps_dir = sys.argv[1] if len(sys.argv) > 1 else "gaps"
    print(build_report(gaps_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
