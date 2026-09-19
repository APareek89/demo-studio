"""Read-only regression: Align's detached preview must not cover the player.

Run against an existing demo; no model, microphone, audio or mutation requests.
Uses an isolated headless browser, never the user's Chrome profile.
"""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8896")
parser.add_argument("--demo", default="dm_41513908")
args = parser.parse_args()
assert args.base.startswith("http://127.0.0.1:")
with urlopen(f"{args.base}/api/demos/{args.demo}", timeout=10) as response:
    state = json.load(response)
assert state.get("bundle_ready") and not state.get("running"), "Run after Build completes; its overlay intentionally blocks review edits"
out = Path("output/playwright/creta-align-modal")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True, args=["--mute-audio"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    forbidden = []
    def guard(route):
        request = route.request
        if not request.url.startswith(args.base + "/"):
            route.abort()  # Includes optional remote fonts; never a provider call.
        elif request.method != "GET":
            forbidden.append((request.method, request.url))
            route.abort()
        else:
            route.continue_()
    context.route("**/*", guard)
    page = context.new_page()
    page.goto(f"{args.base}/?mute=1#/studio/{args.demo}/align")
    page.get_by_role("button", name="Preview", exact=True).nth(2).click()
    expect(page.locator(".preview-bg")).to_have_count(1)
    page.evaluate("hash => location.hash = hash", f"#/play/{args.demo}")
    expect(page.locator(".preview-bg")).to_have_count(0)
    page.wait_for_selector(".pl-stage")
    page.screenshot(path=str(out / "player-without-stale-preview.png"))
    assert not forbidden, forbidden
    browser.close()
print("PASS Align preview removed on navigation to customer player; GET-only, muted, isolated browser")
