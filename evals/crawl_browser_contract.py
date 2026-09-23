"""Offline browser-selection and renderer launch contracts; no browser or HTTP."""
from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

os.environ["MOCK_LLM"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import crawl

MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LINUX = "/srv/demo/.cache/ms-playwright/chromium-123/chrome-linux/chrome"
OVERRIDE = "/opt/Installed Browser/chrome"


class BrowserSelectionContract(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"CRAWL_BROWSER_EXECUTABLE": ""}))
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "subprocess.Popen"):
            self.stack.enter_context(patch(target, side_effect=AssertionError("No browser, subprocess or network allowed")))
        self.files, self.executables = set(), set()
        self.stack.enter_context(patch.object(Path, "is_file", lambda path: str(path) in self.files))
        self.stack.enter_context(patch.object(crawl.os, "access", side_effect=lambda path, mode: str(path) in self.executables and mode == os.X_OK))
        self.context = MagicMock()
        self.page = self.context.new_page.return_value
        self.page.url = "https://example.com/creta"
        self.page.content.return_value = "<title>CRETA</title><p>Reviewed page.</p>"
        self.browser = MagicMock()
        self.browser.new_context.return_value = self.context
        self.chromium = SimpleNamespace(executable_path=LINUX, launch=MagicMock(return_value=self.browser))
        playwright = MagicMock()
        playwright.__enter__.return_value = SimpleNamespace(chromium=self.chromium)
        self.stack.enter_context(patch("playwright.sync_api.sync_playwright", return_value=playwright))

    def installed(self, *paths):
        self.files.update(paths)
        self.executables.update(paths)

    def render(self, **kwargs):
        return crawl.render_public("https://example.com/creta", timeout=12, fetcher=MagicMock(side_effect=AssertionError("Unexpected fetch")), **kwargs)

    def assert_path(self, expected):
        self.render()
        self.assertEqual(self.chromium.launch.call_args.kwargs["executable_path"], expected)
        self.chromium.launch.assert_called_once()

    def test_explicit_override_wins_and_space_path_is_one_value(self):
        self.installed(OVERRIDE, MAC, LINUX)
        os.environ["CRAWL_BROWSER_EXECUTABLE"] = OVERRIDE
        self.assert_path(OVERRIDE)

    def test_invalid_override_fails_without_fallback(self):
        self.installed(MAC, LINUX)
        for invalid in ("relative/chrome", "/missing/chrome", "/installed/directory", "/opt/chrome --no-sandbox"):
            with self.subTest(path=invalid):
                os.environ["CRAWL_BROWSER_EXECUTABLE"] = invalid
                with self.assertRaisesRegex(RuntimeError, "absolute path"):
                    self.render()
        self.chromium.launch.assert_not_called()

    def test_non_executable_override_fails_closed(self):
        self.installed(LINUX)
        self.files.add(OVERRIDE)
        os.environ["CRAWL_BROWSER_EXECUTABLE"] = OVERRIDE
        with self.assertRaisesRegex(RuntimeError, "existing executable file"):
            self.render()
        self.chromium.launch.assert_not_called()

    def test_existing_mac_chrome_keeps_priority(self):
        self.installed(MAC, LINUX)
        self.assert_path(MAC)

    def test_linux_uses_installed_playwright_chromium(self):
        self.installed(LINUX)
        self.assert_path(LINUX)

    def test_no_installed_browser_is_explicitly_unavailable(self):
        with self.assertRaisesRegex(RuntimeError, "Rendered extraction unavailable.*service user"):
            self.render()
        self.chromium.launch.assert_not_called()

    def test_non_executable_default_is_not_launched(self):
        self.files.update((MAC, LINUX))
        with self.assertRaisesRegex(RuntimeError, "no installed Chromium"):
            self.render()
        self.chromium.launch.assert_not_called()

    def test_actual_renderer_preserves_sandbox_and_request_isolation(self):
        self.installed(LINUX)
        routes = []
        fetched = []
        def navigate(url, **kwargs):
            handler = self.context.route.call_args.args[1]
            for target, method, resource in (
                (url, "GET", "document"),
                ("http://127.0.0.1/private", "GET", "document"),
                ("https://other.example/specs", "GET", "script"),
                ("https://example.com/upload", "POST", "fetch"),
                ("https://example.com/movie", "GET", "media"),
            ):
                route = MagicMock(request=SimpleNamespace(url=target, method=method, resource_type=resource))
                routes.append(route)
                handler(route)
        self.page.goto.side_effect = navigate
        def fetch(url, **kwargs):
            fetched.append((url, kwargs))
            return {"raw": b"<p>Reviewed page</p>", "mime": "text/html"}
        # URL content cannot supply launch arguments.
        url = "https://example.com/creta?text=--no-sandbox;echo"
        result = crawl.render_public(url, timeout=12, fetcher=fetch)
        launch = self.chromium.launch.call_args.kwargs
        self.assertTrue(launch["chromium_sandbox"])
        self.assertTrue(launch["headless"])
        self.assertEqual(launch["timeout"], 12000)
        self.assertEqual(launch["args"], ["--disable-background-networking", "--disable-sync", "--no-first-run", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        self.browser.new_context.assert_called_once_with(service_workers="block", accept_downloads=False, user_agent=crawl.UA)
        websocket = MagicMock()
        self.context.route_web_socket.call_args.args[1](websocket)
        websocket.close.assert_called_once()
        self.assertEqual([item[0] for item in fetched], [url])
        self.assertEqual(fetched[0][1]["allowed_hosts"], {"example.com"})
        self.assertEqual(len(result["render"]["blocked"]), 4)
        routes[0].fulfill.assert_called_once()
        for blocked in routes[1:]:
            blocked.abort.assert_called_once()
        self.context.close.assert_called_once()
        self.browser.close.assert_called_once()

    def test_launch_failure_never_retries_with_relaxed_flags(self):
        self.installed(LINUX)
        self.chromium.launch.side_effect = RuntimeError("Missing OS dependency or sandbox unavailable")
        with self.assertRaisesRegex(RuntimeError, "Missing OS dependency"):
            self.render()
        self.chromium.launch.assert_called_once()
        self.assertTrue(self.chromium.launch.call_args.kwargs["chromium_sandbox"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
