# Public feedback deployment boundary

The shared demo link opens the player without a password. The editor, demo inventory, build controls, provider traces, saved-session inventory and raw demo files require the operator's private administrator credentials. The application workflow and agent graph are unchanged.

`Caddyfile.feedback.template` keeps the deployed hostname, upstream `127.0.0.1:8877`, one-gigabyte request-body limit and existing 600-second upstream read/write timeouts, plus a 600-second response-header timeout. Apply it only after validating the configuration, snapshotting the deployed configuration and checking the real-Caddy contract below.

Public requests are limited to:

- `GET`/`HEAD` of the app shell, frontend modules, health, a valid demo ID's published bundle and exported video.
- `GET`/`HEAD` of image, audio and video extensions inside that demo's `sources`, `derived`, `media` and `audio` directories. PDF, JSON, JSONL, SVG and HTML media remain private. Published media URLs use safe relative segments; a segment cannot begin with a dot or include backslashes or residual percent escapes.
- `POST` to the player's `run/qa`, `run/tts`, `run/pitch`, `run/lead`, `run/stt` and `run/session` endpoints. The browser needs these for questions, voice and incremental session saving.
- A `GET` WebSocket upgrade to `run/live`.
- `GET`/`HEAD` of the signed session-summary endpoint with a `k` query parameter. The application remains responsible for validating the HMAC key and returning its existing redacted summary.

The `POST /feedback` endpoint is **private**. The customer player does not call it; Playground uses it to invoke the review graph. Making it public would expose editing behavior under an innocuous name.

The final catch-all uses `basic_auth` and imports `/etc/caddy/demo-studio-admin.auth`. That file contains an operator-managed username and bcrypt hash, is readable only by the intended administrator/Caddy service, and is never committed. No password or generated hash belongs in release receipts. If administrator credentials are already installed, preserve them when replacing the configuration.

This boundary keeps intentionally public customer interactions public. It is not application-level multi-tenant authorization, session ownership enforcement or a rate-limiting system. Direct access to the app's upstream must remain loopback-only; opening port 8877 externally would bypass this boundary.

## Real proxy contract

Run on a host with the deployed Caddy binary installed:

```sh
python3 docs/aws/check_feedback_proxy.py --caddy /usr/bin/caddy --output /tmp/feedback-proxy-contract.json
```

The script adapts and validates the actual template, then starts a separate Caddy process against a stdlib HTTP stub. Both listeners use ephemeral loopback ports. Its Caddy admin API and automatic HTTPS are disabled, and its home/config/data directories are temporary. It never reloads production, calls the app, requests providers, reads real credentials or accesses stored demos. It checks actual correct/incorrect Basic authentication, public and private methods, WebSocket upgrade, signed-summary delegation and encoded traversal. The output includes counts and failed paths but no credentials.

For a release, run the contract before cutover and perform read-only HTTPS checks afterward: the shared bundle and selected image/audio ranges should succeed, while anonymous inventory, session, trace, editor and raw JSON requests should return 401. Do not use a real runtime question or POST session as a proxy smoke test; those perform customer work and can incur provider calls or create records.

Matcher behavior follows Caddy's [request-matcher documentation](https://caddyserver.com/docs/caddyfile/matchers), with a final [Basic authentication handler](https://caddyserver.com/docs/caddyfile/directives/basic_auth). URI-decoded matching is why the contract includes both single-encoded and double-encoded traversal instead of trusting a text-only regular-expression check.
