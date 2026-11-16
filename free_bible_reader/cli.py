"""Command-line entry point; no desktop, Node or SQL Server prerequisite."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from . import __version__, services


def _print(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _json(path):
    value = Path(path)
    if value.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("CONFIGURATION_TOO_LARGE")
    return json.loads(value.read_text(encoding="utf-8"))


def parser():
    result = argparse.ArgumentParser(prog="fbr", description="FREE BIBLE READER: offline Scripture, personal libraries, research and documents")
    result.add_argument("--profile", help="Isolated personal data directory (public databases remain read-only)")
    result.add_argument("--parser", choices=("auto", "portable", "upstream"), help="Strict portable or optional full upstream parser")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Show package version")
    sub.add_parser("capabilities", help="Show actual resource and optional dependency availability")
    catalog = sub.add_parser("catalog", help="List installed editions and selected edition's books")
    catalog.add_argument("--edition")
    read = sub.add_parser("read", help="Read a passage, or native chapter labels with --book/--chapter")
    read.add_argument("reference", nargs="?")
    read.add_argument("--edition", default="web")
    read.add_argument("--language", default="en")
    read.add_argument("--book")
    read.add_argument("--chapter")
    search = sub.add_parser("search", help="Search installed editions without rewriting source text")
    search.add_argument("query")
    search.add_argument("--edition", default="web")
    search.add_argument("--book")
    search.add_argument("--mode", choices=("words", "phrase", "prefix", "boolean"), default="words")
    search.add_argument("--diacritics", choices=("exact", "folded"), default="exact")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--offset", type=int, default=0)
    validate = sub.add_parser("validate-db", help="Read-only integrity, foreign keys, schema and SHA-256")
    validate.add_argument("path")
    validate.add_argument("--quick", action="store_true")
    inspect = sub.add_parser("inspect-db", help="Inspect an import source and available table mappings")
    inspect.add_argument("path")
    imp = sub.add_parser("import-db", help="Preview, then explicitly confirm a mapped personal edition")
    imp.add_argument("path")
    imp.add_argument("--mapping", required=True, help="JSON file mapping table/book/chapter/verse/text columns")
    imp.add_argument("--name", required=True)
    imp.add_argument("--language", default="und")
    imp.add_argument("--source-edition-id")
    imp.add_argument("--source", default="User-selected local file")
    imp.add_argument("--yes", action="store_true", help="Confirm the displayed mapping and import into private storage")
    imp.add_argument("--batch-size", type=int, default=500)
    exp = sub.add_parser("export", help="Generate selectable PDF or editable DOCX (install [documents] extra)")
    exp.add_argument("--output", required=True)
    exp.add_argument("--format", choices=("pdf", "docx"), required=True)
    exp.add_argument("--reference", default="John 3:16")
    exp.add_argument("--edition", default="web")
    exp.add_argument("--language", default="en")
    exp.add_argument("--title")
    exp.add_argument("--request", help="Optional full, bounded document request JSON file")
    exp.add_argument("--overwrite", action="store_true")
    parse = sub.add_parser("parse", help="Normalize a biblical coordinate reference")
    parse.add_argument("reference")
    parse.add_argument("--language", default="en")
    research = sub.add_parser("research", help="Query real, provenance-preserving independent research engines")
    research.add_argument("reference")
    research.add_argument("--edition-id", default="eng-kjv")
    research.add_argument("--engine", choices=("all", "A", "B", "C"), default="all")
    research.add_argument("--limit", type=int, default=10)
    research.add_argument("--direction", choices=("both", "incoming", "outgoing"), default="both")
    serve = sub.add_parser("serve", help="Serve the local-only reading/study web interface")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--engine", choices=("all", "A", "B", "C"), default="all")
    return result


def main(argv=None):
    # Console encodings on older Windows shells must not corrupt Romanian text.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    if args.profile:
        services.configure_profile(args.profile)
    if args.parser:
        import os
        os.environ["FBR_PARSER"] = args.parser
    try:
        command = args.command
        if command == "version":
            print(__version__)
        elif command == "capabilities":
            _print(services.capabilities())
        elif command == "catalog":
            _print(services.catalog(args.edition))
        elif command == "read":
            if args.book is not None and args.chapter is not None:
                _print(services.chapter(args.edition, args.book, args.chapter))
            elif args.reference:
                _print(services.passage(args.reference, args.edition, args.language))
            else:
                raise ValueError("REFERENCE_OR_BOOK_AND_CHAPTER_REQUIRED")
        elif command == "search":
            _print(services.search(args.query, edition=args.edition, book=args.book, mode=args.mode,
                diacritics=args.diacritics, limit=args.limit, offset=args.offset))
        elif command == "parse":
            _print(services.parse_reference(args.reference, args.language))
        elif command == "research":
            _print(services.research(args.reference, edition_id=args.edition_id, engine=args.engine,
                                     limit=args.limit, direction=args.direction))
        elif command == "validate-db":
            result = services.validate_database(args.path, full=not args.quick)
            _print(result)
            return 0 if result["status"] == "PASS" else 1
        elif command == "inspect-db":
            _print(services.inspect_database(args.path))
        elif command == "import-db":
            _print(services.import_database(args.path, _json(args.mapping),
                {"name": args.name, "language": args.language, "source_edition_id": args.source_edition_id, "source": args.source},
                confirmed=args.yes, batch_size=args.batch_size))
        elif command == "export":
            _print(services.export_document(args.output, reference=args.reference, edition=args.edition, format=args.format,
                title=args.title, language=args.language, request=_json(args.request) if args.request else None, overwrite=args.overwrite))
        elif command == "serve":
            from workbench.server import Handler, ThreadingHTTPServer
            if not 0 <= args.port <= 65535:
                raise ValueError("INVALID_PORT")
            server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
            server.allowed_engine = args.engine
            _print({"url": f"http://127.0.0.1:{server.server_port}/", "bind": "127.0.0.1", "version": __version__})
            sys.stdout.flush()
            try:
                server.serve_forever(poll_interval=.3)
            finally:
                server.server_close()
        return 0
    except KeyboardInterrupt:
        return 130
    except ImportError as error:
        print(json.dumps({"status": "MISSING_OPTIONAL_DEPENDENCY", "error": str(error),
            "hint": "PDF/DOCX: pip install 'free-bible-reader[documents]'"}), file=sys.stderr)
        return 2
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
