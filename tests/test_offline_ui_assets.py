import os
import re
import unittest
from pathlib import Path

from app.ui.app import app


class TestOfflineUIAssets(unittest.TestCase):
    """
    Offline test suite verifying that all external CDN dependencies have been
    completely removed from the Flask UI templates and replaced with bundled
    local vendor static assets under app/ui/static/vendor/.
    """

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.templates_dir = cls.project_root / "app" / "ui" / "templates"
        cls.static_dir = cls.project_root / "app" / "ui" / "static" / "vendor"
        cls.client = app.test_client()

    def test_no_external_cdn_references_in_templates(self):
        """Verify that zero HTML templates reference external CDN domains (e.g. cdn.jsdelivr.net)."""
        html_files = list(self.templates_dir.glob("*.html"))
        self.assertGreater(len(html_files), 0, "No HTML templates found in app/ui/templates.")

        cdn_pattern = re.compile(r"https?://(?:cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|unpkg\.com|fonts\.googleapis\.com)", re.IGNORECASE)

        for template_path in html_files:
            content = template_path.read_text(encoding="utf-8")
            matches = cdn_pattern.findall(content)
            self.assertEqual(
                len(matches),
                0,
                f"External CDN reference found in {template_path.name}: {matches}",
            )

    def test_local_vendor_assets_exist_on_disk(self):
        """Verify that all required bundled vendor distribution files and licenses exist on disk."""
        expected_assets = [
            ("bootstrap/css/bootstrap.min.css", 100_000),       # ~230 KB
            ("bootstrap/js/bootstrap.bundle.min.js", 50_000),   # ~80 KB
            ("bootstrap/LICENSE", 500),                         # MIT License
            ("bootstrap-icons/bootstrap-icons.css", 50_000),     # ~95 KB
            ("bootstrap-icons/fonts/bootstrap-icons.woff2", 50_000),  # ~120 KB
            ("bootstrap-icons/fonts/bootstrap-icons.woff", 50_000),   # ~164 KB
            ("bootstrap-icons/LICENSE.md", 500),                # MIT License
        ]

        for relative_path, min_size in expected_assets:
            full_path = self.static_dir / relative_path
            self.assertTrue(
                full_path.exists(),
                f"Required local vendor asset missing: {full_path}",
            )
            file_size = full_path.stat().st_size
            self.assertGreaterEqual(
                file_size,
                min_size,
                f"Asset file {relative_path} is unexpectedly small ({file_size} bytes, expected >= {min_size}).",
            )

    def test_bootstrap_icons_font_relative_urls_match_disk(self):
        """Verify that bootstrap-icons.css references ./fonts/ which exists alongside the CSS."""
        css_path = self.static_dir / "bootstrap-icons" / "bootstrap-icons.css"
        css_text = css_path.read_text(encoding="utf-8")

        self.assertIn("./fonts/bootstrap-icons.woff2", css_text)
        self.assertIn("./fonts/bootstrap-icons.woff", css_text)

        font_woff2 = self.static_dir / "bootstrap-icons" / "fonts" / "bootstrap-icons.woff2"
        font_woff = self.static_dir / "bootstrap-icons" / "fonts" / "bootstrap-icons.woff"
        self.assertTrue(font_woff2.exists())
        self.assertTrue(font_woff.exists())

    def test_flask_serves_local_vendor_assets(self):
        """Verify that Flask test client successfully serves each bundled vendor asset with HTTP 200."""
        routes_to_test = [
            ("/static/vendor/bootstrap/css/bootstrap.min.css", "text/css"),
            ("/static/vendor/bootstrap/js/bootstrap.bundle.min.js", "javascript"),
            ("/static/vendor/bootstrap-icons/bootstrap-icons.css", "text/css"),
            ("/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2", "font"),
            ("/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff", "font"),
        ]

        for path, expected_content_type in routes_to_test:
            resp = self.client.get(path)
            self.assertEqual(
                resp.status_code,
                200,
                f"Failed to fetch static asset {path}: got status {resp.status_code}",
            )
            self.assertIn(
                expected_content_type,
                resp.content_type.lower(),
                f"Asset {path} returned content-type {resp.content_type}, expected {expected_content_type}",
            )
            self.assertGreater(len(resp.data), 1000)
            resp.close()

    def test_rendered_ui_routes_reference_local_assets_only(self):
        """Verify that rendered HTML from core pages references local static paths and zero CDN URLs."""
        routes = ["/", "/history", "/symbols"]

        for route in routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed with status {resp.status_code}")
            html = resp.data.decode("utf-8")

            # Must NOT contain CDN links
            self.assertNotIn("cdn.jsdelivr.net", html, f"Route {route} contains cdn.jsdelivr.net")
            self.assertNotIn("https://", html, f"Route {route} contains external https:// link")

            # MUST contain local static paths
            self.assertIn("/static/vendor/bootstrap/css/bootstrap.min.css", html, f"Route {route} missing local Bootstrap CSS")
            self.assertIn("/static/vendor/bootstrap-icons/bootstrap-icons.css", html, f"Route {route} missing local Bootstrap Icons")
            self.assertIn("/static/vendor/bootstrap/js/bootstrap.bundle.min.js", html, f"Route {route} missing local Bootstrap JS")


if __name__ == "__main__":
    unittest.main()
