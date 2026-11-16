"""Portable facade/parser regressions; no outside service or personal corpus."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from free_bible_reader import reference, services


class PortablePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name) / "profile"
        self.env = patch.dict(os.environ, {"FBR_STUDIO_DIR": str(self.profile), "FBR_PARSER": "portable"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_declared_coordinate_examples(self):
        cases = [("John 3:16", "en", "John.3.16"), ("Psalm 23", "en", "Ps.23.1-Ps.23.6"),
                 ("1 Corinthians 13:4", "en", "1Cor.13.4"), ("Gen.1.1", "en", "Gen.1.1"),
                 ("Ioan 3:16-18", "ro", "John.3.16-John.3.18"), ("Johannes 1,1", "de", "John.1.1"),
                 ("John 3:16-4:2", "en", "John.3.16-John.4.2"),
                 ("John.3.16-John.3.18", "en", "John.3.16-John.3.18"),
                 ("John1:1", "en", "John.1.1"), ("1John3:16", "en", "1John.3.16")]
        for text, language, expected in cases:
            with self.subTest(text=text):
                result = reference.parse_reference(text, language)
                self.assertEqual(result["status"], "VALID")
                self.assertEqual(result["normalized"], [expected])

    def test_invalid_input_is_not_substring_fished_or_corrected(self):
        for text in ("John 0:1", "John 99:1", "John 3:99", "John 3:16 trailing text", "Unknown 1:1", "<script>John 1:1</script>", "John -1:1"):
            with self.subTest(text=text):
                self.assertNotEqual(reference.parse_reference(text)["status"], "VALID")
        self.assertEqual(reference.parse_reference("John 3:16-2")["status"], "AMBIGUOUS")
        self.assertEqual(reference.parse_reference("John 1:1; Gen 1:1")["status"], "AMBIGUOUS")
        self.assertEqual(reference.parse_reference("يوحنا 1:1", "ar")["status"], "UNSUPPORTED_LANGUAGE")

    def test_all_canonical_book_aliases_validate_without_node(self):
        for line in reference._BOOK_NAMES.strip().splitlines():
            parts = line.split("|")
            for index, language in enumerate(("en", "ro", "de"), 1):
                with self.subTest(book=parts[0], language=language):
                    self.assertEqual(reference.parse_reference(parts[index] + " 1:1", language)["normalized"], [parts[0] + ".1.1"])

    def test_translation_annotation_and_scope_are_explicit(self):
        result = reference.parse_reference("John 1:1 BSB")
        self.assertEqual(result["indices"][0]["translations"], ["BSB"])
        self.assertEqual(result["parser_backend"], "portable-strict")
        self.assertEqual(reference.parse_many([{"operation": "metadata"}])[0]["status"], "UNSUPPORTED_OPERATION")

    def test_platform_parser_is_explicit_and_response_bounded(self):
        from bridge import reference as bridge
        try:
            bridge.configure_parser(lambda values: [dict(status="VALID", normalized=["John.1.1"], parser_backend="test-delegate") for _ in values])
            self.assertEqual(bridge.parse_reference("opaque")["parser_backend"], "test-delegate")
            bridge.configure_parser(lambda values: [])
            with self.assertRaisesRegex(RuntimeError, "RESPONSE_COUNT"):
                bridge.parse_reference("opaque")
        finally:
            bridge.configure_parser(None)

    def test_complete_chapters_and_original_hashes(self):
        for edition in ("web", "kjv", "bsb"):
            for book, chapter, count in (("Gen", 1, 31), ("Ps", 23, 6), ("Matt", 5, 48), ("John", 1, 51), ("John", 3, 36), ("Rom", 8, 39), ("Rev", 21, 27)):
                result = services.chapter(edition, book, chapter)
                self.assertEqual(len(result["records"]), count)
                for record in result["records"]:
                    self.assertEqual(hashlib.sha256(record["original_text"].encode()).hexdigest(), record["source"]["text_sha256"])

    def test_romanian_partial_edition_retains_unicode_and_attribution(self):
        result = services.passage("Ioan 3:16", "ronbl", "ro")
        record = result["records"][0]
        self.assertIn("Fiindcă atât de mult", record["original_text"])
        self.assertTrue(record["source"]["metadata"]["draft"])
        self.assertEqual(record["source"]["metadata"]["coverage"], "New Testament only")
        self.assertEqual(set(record), {"edition", "language", "book", "chapter", "verse", "original_text", "source"})
        with self.assertRaisesRegex(ValueError, "REFERENCE_NOT_FOUND"):
            services.chapter("ronbl", "Gen", 1)

    def test_search_and_research_are_real_services(self):
        self.assertGreater(services.search("Dumnezeu", edition="ronbl", limit=2)["total"], 0)
        result = services.research("John 1:1", limit=2)
        self.assertEqual(set(result["engines"]), {"A", "B", "C"})
        for engine in result["engines"].values():
            self.assertEqual(engine["status"], "VALID_RESULT")
            self.assertTrue(engine["results"])

    def test_asset_paths_cannot_escape(self):
        from free_bible_reader.resources import asset_path
        with self.assertRaisesRegex(ValueError, "OUTSIDE_ROOT"):
            asset_path("../private.sqlite")


if __name__ == "__main__":
    unittest.main()
