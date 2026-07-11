# Gap: When an app puts saved settings into a shareable browser address, which parts can leave the device through normal browsing, copying, history, or outside links?

- **Domain:** Offline sharing and privacy
- **Type:** fact-lookup
- **Status:** open
- **Origin:** The existing idea about sharing settings through copied codes or browser addresses without accounts.
- **Closure condition:** A human review confirms a source-backed privacy boundary for each common place an app can put shared data in an address, and identifies which choices avoid sending that data to the server during the initial page request.

## Sessions

### 2026-07-11 · auto
- **Scenario / mad-lib:** Not used in auto mode.
- **User inputs:** Mode choice only: auto.
- **Artifacts:** No self-scored artifact was made. The research pass compared browser-address fragments, query text, browser history, copied links, and information passed when following outside links.
- **Steer / outcome:** No human steer in auto mode.
- **Mined:** Assumed — Putting a share code after the # mark keeps that portion out of the page request sent to the server, unlike putting it after ?. That reduces one leak path, but it does not make the code secret: the full address can still be copied, stored in browser history, exposed by screenshots or sync, and read by scripts on the page. Treat address-based share codes as public bearer data unless the content is encrypted before it is placed there. Sources reviewed: RFC 3986 section 3.5; MDN guidance on URI fragments and Location.hash; the W3C Referrer Policy standard.
- **Left open:** A later review should compare the practical size limits and failure behavior of copied codes, browser-address fragments, and downloadable files across major browsers and messaging apps.
