# collective — reference implementation (staged, not deployed)

Everything in this directory implements the "Public collective — full 4-type system, zero
touches to core" plan. It is built and **tested locally in a scratchpad** — nothing here has
been pushed anywhere, because the `collective` repo does not exist yet and creating/writing to
it is outside this session's GitHub scope. Read access to all five private repos
(`pappydapimp69/{Brain,memory,ideas,Tension,Creativity}`) is available this session; write
access to any of them is never taken, by design — see below. This is the exact content to drop
into `collective` once it exists and write access to it is granted.

**Core repos get zero changes from any of this.** Every file here either lives inside
`collective` once created, or only ever *reads* memory/ideas/tension/creativity (never writes) —
confirmed by the tests below, which prove no code path here can write to a private repo even in
principle.

## What's proven, not just sketched

All of the load-bearing logic is real, runnable Python with a passing test suite — per the
plan's build order ("prototype the mediated-write pipeline standalone... nothing else gets built
until this holds"):

```
python3 -m unittest test_intake_steward.py test_export_job.py -v
# Ran 118 tests, OK
```

Two real bugs were caught and fixed by these tests during development, worth knowing about:
1. `redact()` was stripping the provenance *label* but leaving trailing detail text
   ("...from prior lesson.") on the same line — defeated the point of coarsening it. Fixed to
   consume the whole line.
2. The label→id mapping for parsing an Issue Form's rendered body was originally a **hand-written
   sidecar JSON** kept "in sync" with each `.yml` form by hand — an end-to-end run caught the
   real failure mode: a field silently vanishes (no error) the moment the two drift. Fixed by
   `derive_label_map()`, which extracts the map directly from the form `.yml` text, so there's
   exactly one source of truth. Also caught: `memory`'s entry extractor (`## E<n>`) cannot be
   reused for `ideas` (`## [DOMAIN / ...]`, no numeric ID) — they're genuinely different
   identity schemes, now two separate functions (`EXTRACTORS` dispatch table), not one function
   silently returning nothing for one of the two repos.

## Files

| File | Plan section | Status |
|---|---|---|
| `intake_steward.py` | Mediated-write pipeline (schema/injection/secret/dedup/moderation/rate-limit) | Tested, all 4 type schemas confirmed |
| `cli_validate.py` | CLI wrapper an Action step shells out to | Tested end-to-end against real form files |
| `export_job.py` | Core→public export (allow-list, redaction, snapshot, retraction diff) | Tested, all 4 extractors implemented |
| `ISSUE_TEMPLATE/*.yml` | The 4 public intake forms (memory/ideas/tension/creativity) | Field IDs verified against `intake_steward.py`'s schemas |
| `workflows/intake.yml` | The Action wiring the form → steward → PR (not straight to main) | Concrete YAML, **not live-tested** (needs a real repo + bot token) |
| `workflows/diff-shape-check.yml` | Second, independent check before merge | Concrete YAML, **not live-tested** |
| `workflows/export.yml` | Nightly/manual core→public export job, checks out all 4 private repos and groups output by target type | Concrete YAML, **not live-tested** |
| `allowlist/{memory,ideas,tension,creativity}.json` | The opt-in export manifest | Empty by default — nothing exports until a human adds an entry |
| `schema-examples/*.json` | Worked examples of the allowlist + retraction schema | Verified against the real extractors |

### Tension/creativity schemas — confirmed 2026-07-08 (previously inferred)

Read access to `tension` and `creativity` was granted this session. Two findings changed the
build:

1. **`tension-ledger.md`'s real shape** is `### T<n> · <type> · <title>` (types: `tradeoff`,
   `assumption`, `open-question`, `contradiction`, `alternative`), with a `Poles:` line (or
   `Bet:` for type `assumption`), a `Lean:` line carrying the status emoji inline, and a
   `Source:` citation. `TYPE_SCHEMAS["tension"]`, the tension Issue Form, and
   `extract_tension_entry` now match this exactly — a third distinct entry-identity scheme
   (numeric id like `memory`, but type+title baked into the header like neither `memory` nor
   `ideas`).

2. **The private `creativity` repo is FROZEN.** Its own README says explicitly: "demoted from a
   standalone node to a tagged section within `ideas`... do not route new entries here." Its
   `alternative`-type content (parked roads-not-taken) migrated to `tension`; everything else
   (`experiment`/`synthesis`/`speculation`) migrated to `ideas/exploration.md`, which reuses the
   same ledger-style header shape as `tension-ledger.md` but with type-prefixed alphanumeric ids
   that reset per prefix (`E1`, `S1`, `Sp1`...) rather than one global counter, plus a trailing
   `**state**` marker (`live`/`promoted`/`spent`).

   Per an explicit decision this session (confirmed with the owner, not guessed): collective's
   "creativity" public type now targets `ideas/exploration.md`'s live schema —
   `TYPE_SCHEMAS["creativity"]` requires `type` (`experiment`/`synthesis`/`speculation`, with
   `alternative` explicitly rejected and redirected to the tension form), `title`, and
   `description`. `extract_creativity_entry` is a *separate function* from
   `extract_tension_entry` even though both currently delegate to the same regex helper — the
   shared shape is a fact about the 2026-07-02 migration, not a guaranteed invariant, so a future
   divergence in either format won't silently break the other's export.

   This also means `AllowlistEntry` gained a `type` field distinct from `repo`: `repo` is which
   private repo to fetch from, `type` is which collective public folder/extractor to route
   through. They match 1:1 for memory/ideas/tension, but diverge for creativity entries sourced
   from `ideas/exploration.md` (`repo="ideas"`, `type="creativity"`). Historical entries from the
   frozen `creativity/creativity-log.md` can still be allow-listed too (`repo="creativity"`,
   `type="creativity"`) as read-only legacy — see `schema-examples/allowlist.example.json`.

## What still needs a live repo to actually prove

- The three `workflows/*.yml` files reference `secrets.COLLECTIVE_BOT_APP_ID` /
  `secrets.COLLECTIVE_BOT_APP_PRIVATE_KEY` and `secrets.COLLECTIVE_READONLY_PAT` — can't be
  exercised without a real GitHub App/PAT and a real repo to run Actions in.
- The full pre-launch checklist in the plan (rate-limit-under-load, moderation queue routing,
  GitHub App scoping verification) needs the real thing running.
- Whether `creativity`'s frozen historical entries are worth allow-listing at all versus leaving
  that folder exclusively fed by `ideas/exploration.md` going forward — a human call once
  `collective` exists and someone reviews what's actually in `creativity-log.md`.

## Wiring instructions, once `collective` exists

1. `ISSUE_TEMPLATE/*.yml` → `.github/ISSUE_TEMPLATE/` (GitHub's required path)
2. `workflows/*.yml` → `.github/workflows/`
3. `intake_steward.py`, `export_job.py`, `cli_validate.py` → repo root (or a `scripts/` dir;
   update the `python3 cli_validate.py` / `sys.path.insert` references in the workflow YAMLs if
   moved elsewhere)
4. Create `memory/`, `ideas/`, `tension/`, `creativity/` folders, each with a `_state/` subfolder
   containing `existing.json` (`[]`), `ratelimit.json` (`{}`), `sequence` (`0`), and a
   `retracted.json` (`[]`)
5. Set up the bot identity and read-only fetch credential as repo secrets:
   - **`COLLECTIVE_BOT_APP_ID`** + **`COLLECTIVE_BOT_APP_PRIVATE_KEY`**: register a new GitHub
     App (Settings → Developer settings → GitHub Apps → New GitHub App), give it repository
     permissions `Contents: Read & write`, `Issues: Read & write`, `Pull requests: Read & write`
     — nothing else — generate a private key, and install the App **only** on `collective`
     (never on Brain/memory/ideas/tension/creativity). `intake.yml` mints a fresh short-lived
     token from these on every run via `actions/create-github-app-token` — this is required, not
     just isolation: GitHub doesn't let a workflow run triggered by the default `GITHUB_TOKEN`
     cascade into triggering another workflow, so a PR opened with `GITHUB_TOKEN` would silently
     never fire `diff-shape-check.yml`'s `pull_request` trigger. A distinct App identity avoids
     that trap.
   - **`COLLECTIVE_READONLY_PAT`**: a fine-grained personal access token scoped to exactly
     `memory`, `ideas`, `tension`, `creativity` with `Contents: Read-only` and nothing else — no
     access to any other repo, no write scope anywhere.
   - Add both as Collective repo secrets (Settings → Secrets and variables → Actions). Generate
     and paste these directly into GitHub's UI — never share the raw private key or PAT value
     outside it.
6. Update `allowlist/{memory,ideas,tension,creativity}.json` as a human reviews existing private
   canon and opts entries in — starts empty, stays empty until someone deliberately adds a line.
   Remember the `type` field when adding a creativity entry sourced from `ideas/exploration.md`
   (`repo: "ideas"`, `type: "creativity"` — NOT `repo: "creativity"`).
