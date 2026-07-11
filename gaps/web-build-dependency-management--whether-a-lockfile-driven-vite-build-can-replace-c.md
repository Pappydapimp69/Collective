# Gap: Whether a lockfile-driven Vite build can replace committed Three.js files without losing self-contained deployment or genuinely offline CI.

- **Domain:** web-build / dependency-management
- **Type:** fact-lookup
- **Status:** accumulating
- **Origin:** The existing Three.js vendoring tradeoff and the prior headless-WebGL vendoring lesson.
- **Closure condition:** A human reviewer confirms the distinction between deploy-time self-containment and build-time offline hermeticity, then records which dependency-byte strategy the project will rely on.

## Sessions

### 2026-07-10 · auto
- **Scenario / mad-lib:** Research-only auto pass; no human scenario or self-scored artifact.
- **User inputs:** None.
- **Artifacts:** None; this was an external fact lookup.
- **Steer / outcome:** Official documentation separates the two properties: Vite can produce a self-contained deployable build, but installing its locked dependencies still requires the registry or a complete local source of package bytes.
- **Mined:** Separate deploy self-containment from build hermeticity. `npm ci` freezes the dependency tree recorded in the lockfile, and Vite bundles Three.js into a deployable `dist` directory, so generated Three.js files do not need to live in git. That does not make CI offline: `npm ci --offline` works only when all required package data is already local; npm explicitly says its cache is not a persistent, reliable data store; GitHub-hosted jobs use new runners, and Actions caches may miss or be evicted. Strict offline CI therefore requires dependency bytes in a guaranteed input—such as committed package tarballs/vendor files, a durable package mirror, or a preserved build artifact—not merely a lockfile or an Actions cache. Sources checked: official npm `ci`, offline configuration, and cache documentation; official Three.js installation guide; official Vite static-deployment guide; official GitHub-hosted runner and dependency-cache documentation. — provenance: Assumed
- **Left open:** Which guaranteed-input strategy best fits this project once its dependency surface grows: committed tarballs/vendor files, a durable registry mirror, or accepting online locked installs. A later human-reviewed session should also decide whether exact Node/npm/Vite versions and output hashes must be pinned.
