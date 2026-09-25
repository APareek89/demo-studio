# AWS runtime/gallery evidence — 25 September 2026

Application d94d6ef is live. See the [release receipt](../../aws/release-runtime-gallery-2026-09-25.md) for cutover, scope, failures, backup and limits.

`gate-counts.json` records every staged count and raw-log hash; `staged-gates.json` records execution durations. Full mock logs remain in the private AWS receipt and local operational output. Knowledge has two explicit environment skips, not60executed passes. All27processes succeed with zero outbound attempts. Local JavaScript/browser results are in the [application QA](../runtime-gallery-release-2026-09-25/README.md).

The JSON receipts and screenshots contain only release/public-fixture information. Production environment values, operator credentials, data manifests and customer visit history are deliberately absent. Browser screenshots prove remote welcome loading at1440/390, not an acoustic tour. Initial staging/preflight failures are preserved in `preflight-corrections.json`; the browser's initial sandbox-URL failure remains in local operational logs and is disclosed in the release receipt. No paid provider run occurred.
