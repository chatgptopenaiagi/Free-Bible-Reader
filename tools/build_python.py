"""Build the portable public distribution from explicitly allowed resources.

Run in the FBR-004 worktree's isolated build environment. Never gathers private
profiles, original BIBLIA corpus files, executables, models or arbitrary folders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "free_bible_reader/assets"
DATABASES = ("reader.sqlite", "romanian.sqlite", "xref_visual.sqlite", "xref_aggregate.sqlite", "xref_phrase.sqlite", "xref_reference.sqlite")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare():
    if ASSETS.is_symlink() or ASSETS.resolve() != ROOT / "free_bible_reader/assets":
        raise ValueError("UNSAFE_PACKAGE_ASSET_DIRECTORY")
    files = set()
    for name in DATABASES:
        path = ROOT / "data" / name
        if not path.is_file():
            raise FileNotFoundError("Required public database: " + str(path))
        files.add(path)
    files.update(p for p in (ROOT / "data").iterdir() if p.suffix in {".json", ".gz"} and p.is_file())
    for relative, suffixes in (("workbench", {".html", ".js", ".css", ".svg", ".json"}),
            ("ui-core", {".js", ".css", ".svg", ".json"}),
            ("parser", {".js", ".mjs", ".json", ".txt", ".md"}),
            ("studio/fonts", {".ttf", ".txt", ".md"}),
            ("licenses", {".txt", ".md", ".json"})):
        files.update(p for p in (ROOT / relative).rglob("*") if p.is_file() and p.suffix.lower() in suffixes and "node_modules" not in p.parts)
    for name in ("studio/voice_manifest.json", "studio/windows_speech.ps1", "engines/visual/component.js", "engines/visual/component.css", "LICENSE", "THIRD-PARTY-NOTICES.md"):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    manifest = []
    allowed = {p.relative_to(ROOT).as_posix() for p in files}
    # Refuse an unexpected stale payload instead of silently shipping it.
    if ASSETS.exists():
        extra = [p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*") if p.is_file() and p.relative_to(ASSETS).as_posix() not in allowed | {"PUBLIC-ASSET-MANIFEST.json"}]
        if extra:
            raise ValueError("Unexpected staged assets: " + repr(extra[:10]))
    for source in sorted(files):
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("PUBLIC_RESOURCE_SYMLINK_REJECTED")
        relative = source.relative_to(ROOT)
        target = ASSETS / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        source_hash = sha256(source)
        if not target.is_file() or target.stat().st_size != source.stat().st_size or sha256(target) != source_hash:
            shutil.copyfile(source, target)
        manifest.append({"path": relative.as_posix(), "bytes": source.stat().st_size, "sha256": source_hash})
    summary = {"schema_version": 1, "scope": "PUBLIC_ALLOWLIST_ONLY", "private_corpus_included": False,
               "native_runtime_included": False, "database_count": len(DATABASES),
               "database_bytes": sum((ROOT / "data" / n).stat().st_size for n in DATABASES), "assets": manifest}
    (ASSETS / "PUBLIC-ASSET-MANIFEST.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    result = prepare()
    print(json.dumps({k: v for k, v in result.items() if k != "assets"}, indent=2), flush=True)
    if not args.prepare_only:
        subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
