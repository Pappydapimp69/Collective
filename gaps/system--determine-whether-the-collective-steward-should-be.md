# Gap: Determine whether the Collective steward should be runnable through an explicit workflow surface rather than only through issue-triggered intake.

- **Domain:** SYSTEM
- **Type:** fit
- **Status:** open
- **Origin:** seed: user request on 2026-07-13 to run steward as a workflow in Collective
- **Closure condition:** A Collective workflow run or workflow design proves the steward can be invoked safely with bounded writes and clear persistence semantics.

## Sessions

### 2026-07-13 · auto
- **Scenario / mad-lib:** Run steward as a workflow in Collective.
- **User inputs:** "Run steward as a work flow in Collective"
- **Artifacts:** Inspected Collective GitHub Actions workflow definitions for intake, gap intake, gap report, gap index, persistence verification, and diff-shape checks.
- **Steer / outcome:** The active steward workflow surface is issue-triggered gap intake; full entry intake is disabled and no standalone steward workflow_dispatch entry point is present.
- **Mined:** Verified: In Collective, the active steward path is collective-gap-intake on issues labeled intake:gap; it runs cli_gap.py and can only write bounded gaps/ content through a PR that waits for human merge.
- **Left open:** Whether to add an explicit workflow_dispatch wrapper for steward dry-runs or keep the issue-form trigger as the only public invocation surface.
<!-- collective-gap-source issue=74 fingerprint=8ee4114afc1fc8b99fe1bf1fa13fcc3f36f84e34c81513bcdf1dc34600d722ce -->
