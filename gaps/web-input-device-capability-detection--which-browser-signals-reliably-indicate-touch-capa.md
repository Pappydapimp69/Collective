# Gap: Which browser signals reliably indicate touch capability without incorrectly treating every touchscreen device as touch-only.

- **Domain:** web input / device capability detection
- **Type:** fact-lookup
- **Status:** accumulating
- **Origin:** The recorded lesson that checking for a touch-event property produced false negatives on real touch hardware.
- **Closure condition:** A human reviewer confirms the capability-versus-preference distinction and records the project rule for showing touch controls on hybrid devices.

## Sessions

### 2026-07-10 · auto
- **Scenario / mad-lib:** Research-only auto pass; no human scenario or self-scored artifact.
- **User inputs:** None.
- **Artifacts:** None; this was an external fact lookup.
- **Steer / outcome:** Standards and browser documentation distinguish hardware capability from the user's primary pointer, so no single signal should be used to classify a device as touch-only.
- **Mined:** Use capability signals for capability and interaction signals for behavior. A positive touch-point count indicates that touch contacts are supported, while pointer media queries describe the accuracy of the primary or available pointing devices; hybrid laptops may therefore support both touch and a precise pointer. Show touch controls when touch is available, but do not remove mouse or keyboard controls or assume touch is primary. The most reliable final confirmation is observing the input event the person actually uses. Sources checked: the Pointer Events standard and current MDN documentation for touch-point counts and pointer media queries. — provenance: Assumed
- **Left open:** Whether this project should show touch controls immediately from capability signals, reveal them after the first touch interaction, or combine both approaches to avoid clutter on hybrid devices.
