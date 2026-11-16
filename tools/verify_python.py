"""Run from outside the source tree using the actual wheel-installed interpreter.

Evidence includes real public data reads, all research engines, a synthetic
import clearly labeled as such, export text/Unicode checks and a local server.
No original BIBLIA source or existing user profile is opened.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="wheel-verification-", dir=output.parent))
    os.environ["FBR_STUDIO_DIR"] = str(profile / "profile")
    os.environ["FBR_PARSER"] = "portable"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import free_bible_reader
    from free_bible_reader import services
    from free_bible_reader.resources import asset_root
    evidence = {"schema_version": 1, "platform": platform.platform(), "python": sys.version,
        "executable": sys.executable, "cwd": str(Path.cwd()), "package": free_bible_reader.__file__,
        "asset_root": str(asset_root()), "version": importlib.metadata.version("free-bible-reader"),
        "profile": str(profile), "parser": "portable-strict, deliberately no Node calls", "checks": []}

    def check(name, function):
        started = time.perf_counter()
        try:
            detail = function()
            value = {"name": name, "status": "PASS", "detail": detail}
        except Exception as error:
            value = {"name": name, "status": "FAIL", "error": str(error), "traceback": traceback.format_exc()}
        value["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        evidence["checks"].append(value)
        print(name, value["status"], flush=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    def installed():
        assert "site-packages" in Path(free_bible_reader.__file__).parts, "Must test installed wheel, not source"
        assert free_bible_reader.__version__ == "0.3.0"
        assert (asset_root() / "PUBLIC-ASSET-MANIFEST.json").is_file()
        metadata = importlib.metadata.metadata("free-bible-reader")
        assert metadata["Requires-Python"] == ">=3.11"
        return {"version": free_bible_reader.__version__, "requires_python": metadata["Requires-Python"], "entry_points": [str(e) for e in importlib.metadata.entry_points(group="console_scripts") if e.name == "fbr"]}
    check("installed_metadata", installed)

    def catalog():
        result = services.catalog()
        editions = {e["id"]: e for e in result["editions"]}
        assert set(editions) == {"web", "kjv", "bsb", "ronbl"}
        assert editions["ronbl"]["metadata"]["coverage"] == "New Testament only"
        assert len(services.catalog("ronbl")["books"]) == 27
        return [{"id": e["id"], "name": e["name"], "language": e["language"]} for e in editions.values()]
    check("real_edition_catalog", catalog)

    def reading():
        results = []
        for edition in ("web", "kjv", "bsb"):
            for book, chapter, count in (("Gen", 1, 31), ("Ps", 23, 6), ("Matt", 5, 48), ("John", 1, 51), ("John", 3, 36), ("Rom", 8, 39), ("Rev", 21, 27)):
                rows = services.chapter(edition, book, chapter)["records"]
                assert len(rows) == count
                assert all(hashlib.sha256(r["original_text"].encode()).hexdigest() == r["source"]["text_sha256"] for r in rows)
                results.append({"edition": edition, "book": book, "chapter": chapter, "verses": count, "all_text_hashes_match": True})
        romanian = services.passage("Ioan 3:16-18", "ronbl", "ro")["records"]
        assert len(romanian) == 3 and "Fiindcă" in romanian[0]["original_text"]
        results.append({"edition": "ronbl", "reference": "John.3.16-John.3.18", "verses": 3, "unicode": True})
        return results
    check("complete_chapters_and_unicode", reading)

    def parsing():
        cases = [("John 3:16", "en", "VALID"), ("Genesis 1:1", "en", "VALID"), ("Ioan 3:16", "ro", "VALID"),
                 ("Johannes 1,1", "de", "VALID"), ("John 3:99", "en", "INVALID"), ("John 3:16-2", "en", "AMBIGUOUS"), ("unknown 1:1", "en", "UNRECOGNIZED")]
        results = []
        for reference, language, expected in cases:
            answer = services.parse_reference(reference, language)
            assert answer["status"] == expected, answer
            results.append({"input": reference, "language": language, "status": answer["status"], "normalized": answer["normalized"]})
        return results
    check("node_free_parser", parsing)

    def searching():
        results = []
        for query, edition in (("love", "web"), ("faith", "kjv"), ("forgiveness", "bsb"), ("Dumnezeu", "ronbl")):
            answer = services.search(query, edition=edition, limit=3)
            assert answer["total"] > 0 and answer["results"]
            results.append({"query": query, "edition": edition, "total": answer["total"], "returned": len(answer["results"])})
        return results
    check("real_scripture_search", searching)

    def research():
        answer = services.research("John 1:1", limit=3)
        assert answer["status"] == "VALID_RESULT"
        assert set(answer["engines"]) == {"A", "B", "C"}
        result = {}
        for name, value in answer["engines"].items():
            assert value["status"] == "VALID_RESULT" and value["results"]
            assert all(r["validation_status"] == "SOURCE_ASSERTION_PRESERVED" for r in value["results"])
            result[name] = {"status": value["status"], "returned": len(value["results"]), "first": value["results"][0]}
        return result
    check("three_real_research_engines", research)

    def personal_import():
        source = profile / "synthetic-import-fixture.sqlite"
        with sqlite3.connect(source) as db:
            db.execute("CREATE TABLE verses(id INTEGER PRIMARY KEY,book TEXT,chapter TEXT,verse TEXT,text TEXT)")
            db.executemany("INSERT INTO verses VALUES(?,?,?,?,?)", [(1, "FixtureBook", "0", "1-2", "Synthetic test fixture ă â î ș ț"), (2, "FixtureBook", "3", "3a", "Not Scripture; import mechanics only")])
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        mapping = {"table": "verses", "book": "book", "chapter": "chapter", "verse": "verse", "text": "text", "source_record_id": "id"}
        metadata = {"name": "Clearly labeled synthetic import fixture", "language": "ro", "source_edition_id": "fixture-only", "source": "Software verification fixture, not biblical text"}
        preview = services.import_database(source, mapping, metadata)
        assert preview["status"] == "PREVIEW_ONLY"
        assert len(services.catalog()["editions"]) == 4
        job = services.import_database(source, mapping, metadata, confirmed=True, batch_size=1)
        assert job["status"] == "COMPLETE" and job["inserted"] == 2
        native = services.chapter(job["edition_id"], "FixtureBook", "0")["records"][0]
        assert native["verse"] == "1-2" and native["chapter"] == 0
        assert native["original_text"] == "Synthetic test fixture ă â î ș ț"
        assert services.search("Synthetic", edition=job["edition_id"])["total"] == 1
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        return {"status": job["status"], "rows": job["inserted"], "native_range": native["verse"], "source_hash_unchanged": True, "edition": job["edition_id"]}
    check("personal_sqlite_import_native_labels", personal_import)

    def exports():
        from pypdf import PdfReader
        from docx import Document
        result = []
        for format in ("pdf", "docx"):
            path = profile / ("romanian-john3." + format)
            artifact = services.export_document(path, edition="ronbl", reference="John 3:16-18", format=format, title="Romanian Scripture export verification")
            assert path.is_file() and path.stat().st_size == artifact["bytes"]
            text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages) if format == "pdf" else "\n".join(p.text for p in Document(path).paragraphs)
            assert "Fiindcă" in text and "Dumnezeu" in text and "John.3.16" in text
            result.append({"format": format, "path": str(path), "bytes": path.stat().st_size, "sha256": artifact["sha256"], "unicode_selectable_text": True})
        return result
    check("pdf_docx_export_and_unicode", exports)

    def cli():
        reports = []
        mapping = profile / "mapping.json"
        mapping.write_text(json.dumps({"table": "verses", "book": "book", "chapter": "chapter", "verse": "verse", "text": "text", "source_record_id": "id"}))
        commands = [("--help",), ("version",), ("catalog", "--edition", "ronbl"), ("read", "John 3:16", "--edition", "ronbl"),
            ("search", "Dumnezeu", "--edition", "ronbl", "--limit", "2"), ("research", "John 1:1", "--limit", "2"),
            ("validate-db", str(profile / "synthetic-import-fixture.sqlite")),
            ("import-db", str(profile / "synthetic-import-fixture.sqlite"), "--mapping", str(mapping), "--name", "CLI synthetic fixture preview"),
            ("import-db", str(profile / "synthetic-import-fixture.sqlite"), "--mapping", str(mapping), "--name", "CLI synthetic fixture import", "--yes")]
        for format in ("pdf", "docx"):
            commands.append(("export", "--format", format, "--edition", "ronbl", "--reference", "John 3:16", "--output", str(profile / ("cli-romanian." + format))))
        for args in commands:
            value = subprocess.run([sys.executable, "-m", "free_bible_reader", *args], text=True, encoding="utf-8", capture_output=True, timeout=60)
            assert value.returncode == 0, value.stderr
            reports.append({"arguments": list(args), "exit": value.returncode, "output_bytes": len(value.stdout.encode())})
        return reports
    check("cli_real_commands", cli)

    def server():
        process = subprocess.Popen([sys.executable, "-m", "free_bible_reader", "serve"], text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            lines = []
            for _ in range(12):
                line = process.stdout.readline()
                assert line, "Server exited before startup"
                lines.append(line)
                if line.strip() == "}":
                    break
            state = json.loads("".join(lines))
            assert state["bind"] == "127.0.0.1"
            base = state["url"]
            with urllib.request.urlopen(base + "api/reader/chapter?edition=ronbl&book=John&chapter=3", timeout=10) as stream:
                data = json.load(stream)
            assert len(data["verses"]) == 36
            with urllib.request.urlopen(base, timeout=10) as stream:
                assert b"FREE BIBLE READER" in stream.read()
            return {"bind": state["bind"], "romanian_chapter_verses": len(data["verses"]), "local_ui_served": True}
        finally:
            process.terminate()
            process.communicate(timeout=15)
    check("local_server_reading_and_shutdown", server)

    def integrity():
        inventory = json.loads((asset_root() / "PUBLIC-ASSET-MANIFEST.json").read_text())
        results = []
        for item in inventory["assets"]:
            if not item["path"].endswith(".sqlite"):
                continue
            answer = services.validate_database(asset_root() / item["path"])
            assert answer["status"] == "PASS" and answer["sha256"] == item["sha256"]
            results.append({"path": item["path"], "bytes": answer["bytes"], "sha256": answer["sha256"], "integrity": answer["integrity"], "foreign_key_violations": len(answer["foreign_key_violations"]), "source_hash_matches": True})
        assert len(results) == 6
        return results
    check("all_six_public_database_integrity_and_preservation", integrity)
    evidence["passed"] = sum(c["status"] == "PASS" for c in evidence["checks"])
    evidence["failed"] = sum(c["status"] == "FAIL" for c in evidence["checks"])
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": evidence["passed"], "failed": evidence["failed"], "evidence": str(output)}))
    return 1 if evidence["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
