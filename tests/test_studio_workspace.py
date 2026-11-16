"""Actual isolated personal SQLite workflows; never touches reader databases."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import workspace as w


class PersonalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fbr-workspace-")
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {"FBR_STUDIO_DIR": str(self.root)})
        self.environment.start()
        self.source = {"edition_id": "synthetic-ro", "book": "Test", "chapter": 1,
                       "verse_start": 2, "verse_end": 2, "reference": "Test.1.2",
                       "selected_text": "Înțelepciune și credință", "label": "Synthetic test only"}

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_crud_reopen_unicode_and_independent_personal_database(self):
        sentinel = self.root / "source.sqlite"
        sentinel.write_bytes(b"read-only source sentinel")
        before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        item = w.create_item("notes", {"title": "Observație", "body": "Știință, țară, înger și â.", "source": self.source})
        self.assertEqual(w.get_item(item["id"])["body"], "Știință, țară, înger și â.")
        self.assertTrue((self.root / "workspace.sqlite").exists())
        changed = w.update_item(item["id"], {"body": "Revizie personală"}, expected_revision=1)
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(changed["source"], self.source)
        w.delete_item(item["id"], expected_revision=2)
        with self.assertRaises(w.WorkspaceError) as error:
            w.get_item(item["id"])
        self.assertEqual(error.exception.code, "NOT_FOUND")
        self.assertEqual(hashlib.sha256(sentinel.read_bytes()).hexdigest(), before)

    def test_revision_conflict_cannot_overwrite_a_newer_note(self):
        item = w.create_item("note", {"body": "First"})
        w.update_item(item["id"], {"body": "Second"}, expected_revision=1)
        with self.assertRaises(w.WorkspaceError) as error:
            w.update_item(item["id"], {"body": "Stale"}, expected_revision=1)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(w.get_item(item["id"])["body"], "Second")

    def test_corrections_and_highlights_never_replace_original_source(self):
        item = w.create_item("correction", {"source": self.source, "corrected_text": "Personal alternative", "body": "My correction"})
        updated = w.update_item(item["id"], {"corrected_text": "Another personal alternative"})
        self.assertEqual(updated["source"]["selected_text"], self.source["selected_text"])
        with self.assertRaises(w.WorkspaceError) as error:
            w.update_item(item["id"], {"source": {**self.source, "selected_text": "Changed original"}})
        self.assertEqual(error.exception.code, "IMMUTABLE_SOURCE")
        highlight = w.create_item("highlights", {"source": self.source, "color": "yellow"})
        self.assertEqual(w.get_item(highlight["id"])["source"], self.source)

    def test_utf16_offsets_preserve_astral_and_combining_characters(self):
        original = "A😀Șe\u0301Z"
        source = {**self.source, "original_text": original, "selected_text": "😀Șe\u0301", "start_utf16": 1, "end_utf16": 6,
                  "sourceTextSha256": hashlib.sha256(original.encode("utf-8")).hexdigest()}
        saved = w.create_item("highlights", {"source": source, "color": "#ffee00"})["source"]
        self.assertEqual(saved["selected_text"].encode("utf-8"), "😀Șe\u0301".encode("utf-8"))
        self.assertEqual((saved["start_scalar"], saved["end_scalar"]), (1, 5))
        self.assertEqual(saved["offset_space"], "source_original_utf16")
        for bad in ({**source, "start_utf16": 2}, {**source, "selected_text": "wrong"}, {**source, "sourceTextSha256": "0" * 64}):
            with self.assertRaises(w.WorkspaceError):
                w.create_item("highlights", {"source": bad})

    def test_collection_snapshots_retain_provenance_after_item_edit_and_delete(self):
        note = w.create_item("notes", {"body": "Original note", "source": self.source})
        collection = w.create_item("collections", {"title": "Sources and notes"})
        collection = w.add_collection_item(collection["id"], {"item_id": note["id"]})
        member = collection["members"][0]
        w.update_item(note["id"], {"body": "Edited note"})
        w.delete_item(note["id"])
        collection = w.get_item(collection["id"])
        self.assertIsNone(collection["members"][0]["item_id"])
        self.assertEqual(collection["members"][0]["snapshot"]["body"], "Original note")
        self.assertEqual(collection["members"][0]["snapshot"]["source"], self.source)
        collection = w.add_collection_item(collection["id"], {"blocks": [self.source, {**self.source, "verse_start": 3, "verse_end": 3}]})
        collection = w.add_collection_item(collection["id"], {"note": {"text": "Colecție personală"}})
        self.assertEqual([x["position"] for x in collection["members"]], [0, 1, 2])
        w.remove_collection_item(collection["id"], member["id"])
        self.assertEqual(w.collection_items(collection["id"])["total"], 2)

    def test_literal_unicode_personal_search_paging_and_types(self):
        note = w.create_item("notes", {"title": "ȚARĂ", "body": "100% _ ' OR 1=1; --"})
        w.create_item("bookmarks", {"source": self.source})
        w.create_item("savedsearch", {"title": "Saved", "data": {"query": "faith", "edition_id": "web"}})
        w.create_item("history", {"source": self.source})
        self.assertEqual(w.search_items("țară")["items"][0]["id"], note["id"])
        self.assertEqual(w.search_items("% _")["total"], 1)
        self.assertEqual(w.search_items("not present")["total"], 0)
        self.assertEqual(len(w.list_items(limit=2)["items"]), 2)
        self.assertEqual(w.list_items("notes")["total"], 1)

    def test_native_zero_suffix_range_and_nonnumeric_chapter_labels_are_preserved(self):
        for chapter, start, end in [(0, 0, 0), ("Preface", "1a", "3-4"), ("01", "0", "2b")]:
            source = {**self.source, "chapter": chapter, "verse_start": start, "verse_end": end,
                      "edition_name": "Synthetic native edition", "language": "ro", "label": str(start),
                      "origin": {"publisher": "Synthetic test"}, "license": "Synthetic fixture", "source_record_id": "row-0"}
            item = w.create_item("bookmarks", {"source": source})
            self.assertEqual(item["source"], source)
        self.assertEqual(w.list_items(edition_id="synthetic-ro", book="Test", chapter="Preface")["total"], 1)
        self.assertEqual(w.list_items(edition_id="different", book="Test")["total"], 0)

    def test_invalid_payload_rolls_back_and_source_identity_is_bounded(self):
        for kind, payload in [("unknown", {}), ("highlights", {}), ("corrections", {"source": self.source}),
                              ("notes", {"data": {"bad": float("nan")}}), ("notes", {"body": "x" * 100_001}),
                              ("notes", {"source": {"start_scalar": 1}}), ("notes", {"color": "url(http://example.com)"})]:
            with self.assertRaises(w.WorkspaceError):
                w.create_item(kind, payload)
        self.assertEqual(w.list_items()["total"], 0)
        with w._connect() as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
