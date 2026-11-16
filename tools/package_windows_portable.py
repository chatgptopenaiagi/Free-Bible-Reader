"""Create a ZIP64 portable Windows distribution from a verified bundle.

The bundle and notice allowlist are the only inputs. Private profiles, voices,
credentials, original corpus and developer environments are never gathered.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    bundle, output, evidence = map(lambda v: Path(v).resolve(), (args.bundle, args.output, args.evidence))
    if not bundle.is_relative_to(ROOT / "dist") or not output.is_relative_to(ROOT / "dist"):
        raise ValueError("BUILD_PATHS_MUST_STAY_IN_WORKTREE_DIST")
    manifest_file = bundle.parent / "app-build-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    files = {}
    for item in manifest["files"]:
        path = (bundle / item["relative_path"]).resolve()
        if not path.is_relative_to(bundle) or path.is_symlink() or digest(path) != item["sha256"]:
            raise ValueError("BUNDLE_MANIFEST_MISMATCH")
        files[path.relative_to(bundle).as_posix()] = path
    for path in [ROOT / "LICENSE", ROOT / "THIRD-PARTY-NOTICES.md", *sorted((ROOT / "licenses").rglob("*"))]:
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()] = path
    public = {"product": "FREE BIBLE READER", "version": manifest["version"], "format": "Windows portable ZIP",
              "personal_data_included": False, "files": [{"path": name, "bytes": path.stat().st_size, "sha256": digest(path)} for name, path in sorted(files.items())]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, "FreeBibleReader/" + name)
        archive.writestr("FreeBibleReader/PORTABLE-MANIFEST.json", json.dumps(public, indent=2))
        archive.writestr("FreeBibleReader/PORTABLE-README.txt", "FREE BIBLE READER " + manifest["version"] + "\n\nExtract this entire folder and open FreeBibleReader.exe.\nNo separate Python, Node, SQL Server or installer is required.\nKeep the small launcher window open while reading in your browser.\nPersonal libraries, notes, preferences and downloaded voices are stored in your Windows user profile, outside this folder.\nRomanian Biblia Libera is a draft New Testament, not a complete Bible.\n")
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        evidence.mkdir(parents=True, exist_ok=True)
        extracted = Path(tempfile.mkdtemp(prefix="portable-extracted-", dir=evidence))
        for info in archive.infolist():
            if not (extracted / info.filename).resolve().is_relative_to(extracted):
                raise ValueError("UNSAFE_ARCHIVE_PATH")
        archive.extractall(extracted)
    app = extracted / "FreeBibleReader"
    for item in public["files"]:
        if digest(app / item["path"]) != item["sha256"]:
            raise ValueError("EXTRACTED_FILE_HASH_MISMATCH")
    profile = evidence / (extracted.name + "-profile")
    profile.mkdir()
    child_env = {**os.environ, "PYTHONPATH": "", "PYTHONHOME": "", "NODE_PATH": "", "PATH": os.environ.get("SystemRoot", r"C:\Windows") + r"\System32", "FBR_STUDIO_DIR": str(profile / "studio")}
    receipt = evidence / (extracted.name + "-self-test.json")
    result = subprocess.run([str(app / "FreeBibleReader.exe"), "--self-test", "--self-test-output", str(receipt), "--profile-dir", str(profile)], cwd=app, env=child_env, timeout=300)
    checks = json.loads(receipt.read_text(encoding="utf-8"))
    assert result.returncode == 0 and checks["status"] == "PASS" and checks["version"] == manifest["version"]
    report = {"status": "PASS", "version": manifest["version"], "zip": str(output), "bytes": output.stat().st_size,
        "sha256": digest(output), "zip_integrity": "PASS", "extracted_file_hashes": len(public["files"]),
        "extracted_directory": str(app), "isolated_profile": str(profile), "self_test": checks,
        "developer_runtime_removed_from_path": True, "private_data_included": False,
        "gui_launch_and_shutdown": "PENDING_SEPARATE_VERIFICATION"}
    target = evidence / "portable-verification.json"
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
