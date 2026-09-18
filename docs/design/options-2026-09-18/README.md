# Demo Studio — four design directions

Start with **index.html**, the review gallery. Current local preview: http://127.0.0.1:8895/.

- **A · Bluebird:** bright enterprise workspace, horizontal navigation, original bird guide.
- **B · Atelier:** editorial typography, curated collection and a quiet, premium studio.
- **C · Control Room:** compact navigation, evidence review and detailed reporting.
- **D · Panorama:** spacious product showroom, large imagery and conversation alongside.

Recommendation: begin with Atelier for the workspace and Panorama for the customer experience. No direction has been selected or applied.

## Review in five minutes

1. Use the gallery's Workspace / Studio / Customer experience / On your phone buttons to compare the screenshots.
2. Open a direction and visit Workspace, Studio, customer view and Insights. Try a review card and a suggested question.
3. Use the live two-pane comparison for a closer look. The panes show responsive layouts; open full size to judge desktop composition.
4. Shortlist any directions and write notes. Notes are saved only in that browser. Download them if you want a portable copy; nothing is sent automatically.

## Open later

The HTML, pictures and previews are together in this folder. Keep that structure intact. The downloadable ZIP contains the same review files. After extracting it, open index.html in your browser. Direct-file opening was not verified because the in-app browser blocks file:// URLs; the complete gallery was verified through the static local server.

If your browser restricts local files, serve this folder with Python:

```sh
python3 -m http.server 8895 --bind 127.0.0.1 --directory /path/to/options-2026-09-18
```

Then open http://127.0.0.1:8895/. No install or build step is required. The gallery and Panorama optionally load Google Fonts; they use system fonts without network access. Bluebird, Atelier and Control Room use system font stacks.

## Boundaries

These are isolated design prototypes with clearly labelled sample data. Questions, approvals, build/rehearsal controls, reports, contacts and exports simulate the interface. They do not use real agents, product facts, provider calls, uploads, audio or microphone. Reported metrics are fictional and are not app KPIs. Prototype edits reset when the page is reloaded; only gallery notes and shortlists persist locally where browser storage is available.

The actual app's web/, server/ and api/ code is unchanged from f4863fa. Real demos, workflow, provider configuration and audio are untouched. No merge, deployment or paid calls.

## Evidence

Desktop and phone screenshots are in previews/. Four main views in each direction were checked at 390×844 with no page overflow or broken product images. Desktop compositions and sample review/question controls were exercised at 1440×1000. Gallery preview switching, live comparison, saved notes and export control were checked. QA review text and selections were cleared afterward.

qa/browser-review.json records browser coverage and limits. qa/final-summary.md records the free repository gates (307/307 deck, 24/24 acceptance, both smoke phases), syntax and asset checks. The assets/provenance.json file identifies the existing approved local product pictures used here. Audi is Q5; imagery and labels were reviewed together.
