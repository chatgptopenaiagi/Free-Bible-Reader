"""Stable public facade over the existing, independently usable services.

Personal data is written only to the explicit profile or per-user data folder.
The public corpus is always opened read-only. Windows adapters are optional.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from .resources import asset_root


def configure_profile(path):
    from studio.paths import configure_root
    configure_root(path)


def catalog(edition=None):
    from studio.library import catalog as function
    return function(edition)


def chapter(edition="web", book="John", chapter=1):
    from studio.library import chapter as function
    result = function(edition, book, chapter)
    # New shared records supplement the established GUI contract; they never
    # rewrite native verse labels, original text or publisher identity.
    metadata = result["edition"]
    result["records"] = [{"edition": metadata["id"], "language": metadata["language"],
        "book": result["book"]["id"], "chapter": result["chapter"], "verse": row.get("label", row["number"]),
        "original_text": row["text"], "source": {"attribution": metadata["source"], "license": metadata["license"],
        "metadata": metadata.get("metadata", {}), "reference": row["reference"], "text_sha256": row["text_sha256"]}}
        for row in result["verses"]]
    return result


def passage(reference, edition="web", language="en", max_verses=1000):
    """Resolve one canonical same-book range without inventing native mappings.

    For imported noncanonical/native labels use chapter() directly; canonical
    KJV coordinates cannot prove a personal edition's versification equivalence.
    """
    from bridge.reference import parse_reference, split_reference
    parsed = parse_reference(reference, language)
    if parsed.get("status") != "VALID" or len(parsed.get("normalized", [])) != 1:
        raise ValueError("REFERENCE_" + parsed.get("status", "INVALID"))
    start, end = split_reference(parsed["normalized"][0])
    if start[0] != end[0]:
        raise ValueError("SAME_BOOK_PASSAGE_REQUIRED")
    records = []
    for number in range(start[1], end[1] + 1):
        for item in chapter(edition, start[0], number)["records"]:
            verse = str(item["verse"])
            if not verse.isdigit():
                raise ValueError("NATIVE_LABEL_REQUIRES_EXPLICIT_CHAPTER_SELECTION")
            if number == start[1] and int(verse) < start[2]:
                continue
            if number == end[1] and int(verse) > end[2]:
                continue
            records.append(item)
            if len(records) > max_verses:
                raise ValueError("PASSAGE_BOUND_EXCEEDED")
    if not records:
        raise ValueError("REFERENCE_NOT_FOUND_IN_EDITION")
    return {"status": "VALID_RESULT", "edition": edition, "reference": parsed["normalized"][0],
            "parser": parsed, "records": records, "mapping_scope": "Native source coordinates; no cross-edition alignment assertion"}


def search(query, edition="web", **options):
    from studio.search import search as function
    return function(query, edition=edition, **options)


def parse_reference(reference, language="en"):
    from bridge.reference import parse_reference as function
    return function(reference, language)


def research(reference, edition_id="eng-kjv", engine="all", limit=25, **options):
    from bridge.hub import query
    return query(dict(options, reference=reference, edition_id=edition_id, engine=engine, limit=limit))


def validate_database(path, full=True):
    """Integrity check and schema discovery via a read-only connection."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        checks = [row[0] for row in db.execute("PRAGMA integrity_check" if full else "PRAGMA quick_check")]
        foreign = [list(row) for row in db.execute("PRAGMA foreign_key_check")]
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {"status": "PASS" if checks == ["ok"] and not foreign else "FAIL", "path": str(path),
            "bytes": path.stat().st_size, "sha256": digest.hexdigest(), "integrity": checks,
            "foreign_key_violations": foreign, "tables": tables, "read_only": True}


def inspect_database(path, **options):
    from studio.importers import inspect_source
    return inspect_source(path, **options)


def import_database(path, mapping, metadata, confirmed=False, batch_size=500, cancel_event=None):
    from studio import library
    info = library.inspect_source(path)
    if info.get("requires_member_selection"):
        raise ValueError("ZIP_MEMBER_SELECTION_REQUIRED")
    if not confirmed:
        return {"status": "PREVIEW_ONLY", "inspection": info,
                "preview": library.preview_import(info["inspection_id"], mapping, metadata)}
    job = library.create_import(info["inspection_id"], mapping, metadata, confirmed=True)
    while job["status"] not in {"COMPLETE", "CANCELLED", "FAILED"}:
        job = library.run_import(job["id"], batch_size=batch_size, cancel_event=cancel_event)
    return job


def export_document(output, *, reference="John 3:16", edition="web", format="pdf", title=None, language="en", request=None, overwrite=False):
    from studio import documents
    output = Path(output).expanduser().resolve()
    if output.exists() and not overwrite:
        raise FileExistsError("OUTPUT_EXISTS_USE_OVERWRITE")
    if request is None:
        result = passage(reference, edition, language)
        request = {"format": format, "title": title or f"{edition}: {reference}", "shape": "verses",
            "blocks": [{"text": r["original_text"], "reference": r["source"]["reference"],
                        "edition_id": r["edition"], "label": r["source"]["attribution"]} for r in result["records"]]}
    artifact = documents.create_export(request)
    source = documents.artifact_file(artifact["artifact_id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids an overwrite race when overwrite was not chosen.
    with source.open("rb") as incoming, output.open("wb" if overwrite else "xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=65536)
    return {**artifact, "output": str(output)}


def capabilities():
    from importlib.util import find_spec
    import sys
    root = asset_root()
    return {"asset_root": str(root), "platform": sys.platform,
        "reading": all((root / "data" / n).is_file() for n in ("reader.sqlite", "romanian.sqlite")),
        "research": {n: (root / "data" / f"xref_{n}.sqlite").is_file() for n in ("visual", "aggregate", "phrase", "reference")},
        "documents": {n: find_spec(n) is not None for n in ("docx", "reportlab")},
        "windows_native_speech": sys.platform == "win32",
        "parser": "Explicit platform delegate, optional pinned upstream Node parser, or strict portable EN/RO/DE fallback"}
