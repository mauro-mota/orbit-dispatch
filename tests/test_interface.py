"""Cuidados estruturais. A experiência completa também precisa de teste no navegador."""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static/index.html").read_text()
        cls.page = Page(cls.html)
        cls.ids = {attrs["id"]: attrs for _, attrs in cls.page.elements if "id" in attrs}

    def test_document_language_headings_and_unique_ids(self):
        self.assertEqual(next(a for t,a in self.page.elements if t == "html")["lang"], "pt-BR")
        self.assertEqual(sum(t == "h1" for t,_ in self.page.elements), 1)
        all_ids = [a["id"] for _,a in self.page.elements if "id" in a]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_original_brand_is_preserved(self):
        self.assertIn('aria-label="Orbit Dispatch, início"', self.html)
        self.assertIn('<span class="brand-icon" aria-hidden="true">↗</span><span>orbit<span class="brand-light">dispatch</span></span>', self.html)
        css = (ROOT / "static/styles.css").read_text()
        self.assertIn('--ink:#182733', css)
        self.assertIn('--lime:#d1f570', css)
        self.assertIn('width:32px; height:32px', css)

    def test_links_and_accessibility_references_have_targets(self):
        for _,attrs in self.page.elements:
            for name in ("aria-labelledby", "aria-describedby"):
                for target in attrs.get(name, "").split():
                    self.assertIn(target, self.ids)
            if attrs.get("href", "").startswith("#"):
                self.assertIn(attrs["href"][1:], self.ids)

    def test_both_choices_are_buttons_with_selected_state(self):
        for choice in ("a", "b"):
            attrs = self.ids[f"choice-{choice}"]
            self.assertEqual(attrs["data-choice"], choice)
            self.assertEqual(attrs["aria-pressed"], "false")
            self.assertEqual(attrs["type"], "button")

    def test_live_notice_stays_present_and_dialog_is_named(self):
        notice = self.ids["notice"]
        self.assertEqual(notice["role"], "status")
        self.assertEqual(notice["aria-live"], "polite")
        self.assertNotIn("hidden", notice)
        self.assertIn("aria-labelledby", self.ids["stop-dialog"])
        self.assertIn("aria-describedby", self.ids["stop-dialog"])
        self.assertIn("cancel-stop", self.ids)
        self.assertIn("aria-labelledby", self.ids["reset-dialog"])
        self.assertIn("aria-describedby", self.ids["reset-dialog"])
        self.assertIn("cancel-reset", self.ids)

    def test_script_ids_match_the_document(self):
        script = (ROOT / "static/app.js").read_text()
        for name in re.findall(r"\$\(['\"]([\w-]+)['\"]\)", script):
            self.assertIn(name, self.ids)

    def test_external_assets_match_content_security_policy(self):
        for tag,attrs in self.page.elements:
            if tag == "script":
                self.assertEqual(attrs["src"], "./app.js")
                self.assertIn("defer", attrs)
            self.assertFalse(any(name.startswith("on") for name in attrs))
        self.assertIn('__DISPATCH_TOKEN__', self.html)

    def test_main_text_and_action_colors_have_readable_contrast(self):
        def luminance(color):
            values = [int(color[i:i+2],16)/255 for i in (1,3,5)]
            linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
            return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
        for foreground,background in [("#182733","#fffdf5"),("#182733","#e5eadf"),("#52605e","#e5eadf"),("#d1f570","#182733")]:
            high,low = sorted((luminance(foreground),luminance(background)),reverse=True)
            self.assertGreaterEqual((high+.05)/(low+.05),4.5)

    def test_progress_and_result_are_explicit(self):
        progress = self.ids["mission-progress"]
        self.assertEqual(progress["max"], "30")
        self.assertEqual(progress["value"], "0")
        self.assertIn("aria-label", progress)
        self.assertIn("hidden", self.ids["finish"])
        self.assertIn("disabled", self.ids["next"])
        self.assertIn("answer-verdict", self.ids)
        self.assertIn("level-message", self.ids)

    def test_external_source_link_is_isolated(self):
        source = self.ids["source"]
        self.assertEqual(source["target"], "_blank")
        self.assertIn("noopener", source["rel"])
        self.assertIn("noreferrer", source["rel"])

    def test_game_storage_does_not_clear_other_app_data(self):
        script = (ROOT / "static/app.js").read_text()
        self.assertIn("orbit-dispatch-quiz-v1", script)
        self.assertNotIn("localStorage.clear", script)
        self.assertNotIn(".innerHTML", script)

    def test_explanation_is_optional_and_art_is_decorative(self):
        self.assertNotIn("open", self.ids["why"])
        artworks = [attrs for tag,attrs in self.page.elements if tag == "svg"]
        self.assertTrue(artworks)
        self.assertTrue(all(attrs.get("aria-hidden") == "true" for attrs in artworks))
        self.assertIn("hidden", self.ids["level-reward"])
        css = (ROOT / "static/styles.css").read_text()
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn(".scene.celebrate", css)
