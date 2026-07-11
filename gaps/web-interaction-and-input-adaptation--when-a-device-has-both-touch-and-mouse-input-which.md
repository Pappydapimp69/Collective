# Gap: When a device has both touch and mouse input, which signals should a website trust when deciding what controls and hints to show?

- **Domain:** Web interaction and input adaptation
- **Type:** fact-lookup
- **Status:** open
- **Origin:** memory entry about touch-device false negatives and the related device-adaptive input entries
- **Closure condition:** A human review confirms a source-backed rule for mixed-input devices, including which signals describe the primary input, which describe any available input, and why capability checks should not be treated as proof of the user's current choice.

## Sessions

### 2026-07-11 · auto
- **Scenario / mad-lib:** Not used in auto mode.
- **User inputs:** Mode choice only: auto.
- **Artifacts:** No self-scored artifact was made. The pass compared browser standards and current reference guidance for primary pointer accuracy, any available pointer accuracy, hover ability, and reported touch capacity.
- **Steer / outcome:** No human steer in auto mode.
- **Mined:** Assumed — Treat mixed-input devices as capability sets, not fixed device categories. Use the primary-pointer signal only for defaults tied to the main input, use the any-pointer and any-hover signals when asking whether an alternate input exists, and use reported touch capacity only as evidence that touch is available. None of these proves what the person is using at this moment, so interaction hints should also update from actual recent input events. Sources reviewed: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/pointer ; https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/any-pointer ; https://developer.mozilla.org/en-US/docs/Web/API/Navigator/maxTouchPoints ; https://www.w3.org/TR/mediaqueries-4/#pointer
- **Left open:** A later hands-on session should test how quickly visible hints should switch after the user changes from touch to mouse or back, because standards describe capabilities but do not settle the best timing for a person.
