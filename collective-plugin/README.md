# Collective plugin

The public version of the private Brain CLI + ZaneGPT plugin, as one Claude Code plugin.

- `skills/collective` — read-only Brain: `query`, `challenge`, `gaps`, `status` against
  Collective's published snapshot (`scripts/collective.py`, stdlib only).
- `skills/zanegpt` — the ZaneGPT reasoning skill. A copy of
  `Pappydapimp69/Zanegpt/zanegpt-plugin/skills/zanegpt/SKILL.md`; that file is the
  source of truth, re-copy it here when it changes.

## Install

```
/plugin marketplace add Pappydapimp69/Collective
/plugin install collective@collective
```

Then ask "query collective for X", or run `/collective` / `/zanegpt`.

Without Claude Code, the script runs anywhere Python 3.10+ does:

```
python3 collective-plugin/skills/collective/scripts/collective.py query determinism
```

## Brain vs Collective

| Brain (private) | Collective plugin (public) |
|---|---|
| `brain query` / `brain challenge` | `collective query` / `collective challenge` |
| reads the private node repos | reads the allow-listed, redacted `snapshot/` |
| writes proposals + `brain sync` | never writes — contribute via the gap-log Issue Form |
