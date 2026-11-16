"""Synthetic export fixtures only; no private Bible corpus inputs."""
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from docx import Document
from pypdf import PdfReader
from studio import documents as d


class DocumentExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fbr-documents-")
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {"FBR_STUDIO_DIR": str(self.root)})
        self.environment.start()
        self.sample = "Text sintetic de test: Știință, țară, înger, credință și înțelepciune."
        self.payload = {"format": "pdf", "shape": "selection", "title": "Synthetic Romanian export test",
                        "blocks": [{"text": "unselected surrounding text", "selected_text": self.sample,
                                    "reference": "Synthetic.1.2", "label": "Synthetic source only", "edition_id": "test-ro"}],
                        "settings": {"font": "serif", "font_size": 12, "paper": "A4", "margins_mm": 20,
                                     "header": "Antet de test", "footer": "Subsol de test", "page_numbers": True,
                                     "alignment": "left", "include_notes": True},
                        "notes": ["Notă personală sintetică."]}

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_pdf_selectable_romanian_exact_selection_provenance_and_reopen(self):
        item = d.create_export(self.payload)
        raw, metadata = d.read_artifact(item["artifact_id"])
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn(self.sample, text)
        self.assertNotIn("unselected surrounding text", text)
        self.assertIn("Notă personală sintetică.", text)
        self.assertIn("Antet de test", text)
        self.assertIn("Subsol de test", text)
        self.assertEqual(float(reader.pages[0].mediabox.width), 595.2756)
        self.assertEqual(metadata["blocks"][0]["source_block"]["text"], "unselected surrounding text")
        self.assertEqual(metadata["blocks"][0]["text"], self.sample)
        self.assertEqual(metadata["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotIn(str(self.root), json.dumps(item))
        self.assertEqual(d.list_artifacts()["total"], 1)

    def test_docx_is_editable_unicode_with_headers_footer_page_field_and_letter(self):
        request = {**self.payload, "format": "docx", "settings": {**self.payload["settings"], "paper": "Letter", "font": "Georgia", "alignment": "justify"}}
        item = d.create_export(request)
        raw, _ = d.read_artifact(item["artifact_id"])
        document = Document(io.BytesIO(raw))
        self.assertIn(self.sample, "\n".join(p.text for p in document.paragraphs))
        self.assertIn("Notă personală sintetică.", "\n".join(p.text for p in document.paragraphs))
        self.assertAlmostEqual(document.sections[0].page_width.inches, 8.5, places=3)
        self.assertAlmostEqual(document.sections[0].page_height.inches, 11, places=3)
        self.assertEqual(document.sections[0].header.paragraphs[0].text, "Antet de test")
        document.paragraphs[-1].add_run(" Editable addition")
        output = io.BytesIO()
        document.save(output)
        self.assertIn("Editable addition", Document(io.BytesIO(output.getvalue())).paragraphs[-1].text)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn(b"PAGE", archive.read("word/footer1.xml"))
            self.assertNotIn("unselected surrounding text".encode(), archive.read("word/document.xml"))
        title = document.styles["Title"].element
        self.assertEqual(title.xpath(".//w:pBdr"), [])
        self.assertFalse(any("theme" in name.casefold() for name in title.get_or_add_rPr().get_or_add_rFonts().attrib))

    def test_long_pdf_paginates_and_preserves_tail_with_letter_margins(self):
        blocks = [{"text": f"Synthetic paragraph {index}: " + self.sample * 3, "reference": f"Synthetic.1.{index + 1}"} for index in range(45)]
        item = d.create_export({**self.payload, "blocks": blocks, "settings": {**self.payload["settings"], "paper": "Letter", "margins_mm": {"top": 15, "right": 18, "bottom": 15, "left": 18}, "alignment": "justify"}})
        raw, _ = d.read_artifact(item["artifact_id"])
        reader = PdfReader(io.BytesIO(raw))
        self.assertGreater(len(reader.pages), 2)
        extracted = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Synthetic paragraph 44", extracted)
        self.assertLess(extracted.index("Synthetic paragraph 0"), extracted.index("Synthetic paragraph 44"))
        self.assertIn("Notă personală sintetică.", reader.pages[-1].extract_text())
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 612)
        self.assertEqual(item["rendering"]["pages"], len(reader.pages))

    def test_markup_is_literal_and_notes_can_be_excluded(self):
        text = '<script>alert("test")</script> & literal <b>text</b>'
        for output_format in ("pdf", "docx"):
            request = {**self.payload, "format": output_format, "blocks": [{"text": text}], "settings": {**self.payload["settings"], "include_notes": False}}
            item = d.create_export(request)
            raw, _ = d.read_artifact(item["artifact_id"])
            extracted = PdfReader(io.BytesIO(raw)).pages[0].extract_text() if output_format == "pdf" else "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
            self.assertIn(text, extracted)
            self.assertNotIn("Notă personală", extracted)

    def test_artifact_lookup_rejects_paths_and_detects_modified_files(self):
        item = d.create_export(self.payload)
        for value in ("../outside", str(self.root / "secret.pdf"), "not-an-id"):
            with self.assertRaises(d.w.WorkspaceError):
                d.read_artifact(value)
        path = d.artifact_file(item["artifact_id"])
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaises(d.DocumentError) as error:
            d.read_artifact(item["artifact_id"])
        self.assertEqual(error.exception.code, "ARTIFACT_CHANGED")

    def test_bounds_invalid_controls_settings_and_missing_glyphs(self):
        requests = [{**self.payload, "blocks": [{"text": "x"}] * 1001},
                    {**self.payload, "blocks": [{"text": "bad\x01"}]},
                    {**self.payload, "settings": {"font": "../../arbitrary.ttf"}},
                    {**self.payload, "settings": {"font_size": 100}},
                    {**self.payload, "blocks": [{"text": "\U0010ffff"}]},
                    {**self.payload, "blocks": [], "notes": []}]
        for request in requests:
            with self.assertRaises(d.w.WorkspaceError):
                d.create_export(request)
        self.assertEqual(d.list_artifacts()["total"], 0)

    def test_artifact_history_and_safe_delete(self):
        first = d.create_export(self.payload)
        second = d.create_export({**self.payload, "format": "docx", "shape": "collection"})
        self.assertEqual(d.list_artifacts(limit=1)["total"], 2)
        self.assertEqual(len(d.list_artifacts(limit=1)["items"]), 1)
        self.assertEqual(d.get_artifact(second["artifact_id"])["shape"], "collection")
        path = d.artifact_file(first["artifact_id"])
        d.delete_artifact(first["artifact_id"])
        self.assertFalse(path.exists())
        self.assertEqual(d.list_artifacts()["total"], 1)

    def test_citation_display_choices_keep_full_provenance_and_long_text_wrap(self):
        request = {**self.payload, "settings": {**self.payload["settings"], "include_references": False, "include_source_labels": False}}
        item = d.create_export(request)
        raw, metadata = d.read_artifact(item["artifact_id"])
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages)
        self.assertNotIn("Synthetic.1.2", text)
        self.assertNotIn("Synthetic source only", text)
        self.assertEqual(metadata["blocks"][0]["source_block"]["reference"], "Synthetic.1.2")
        font, _ = d._font(metadata["settings"])
        source = "Învățare e\u0301 " * 1000
        lines = list(d._wrap(source, 420, font, 12))
        self.assertEqual("".join(value for value, _ in lines), source)
        self.assertGreater(len(lines), 100)


if __name__ == "__main__":
    unittest.main()
