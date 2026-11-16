# Python package verification

The final FREE BIBLE READER 0.3.0 wheel passes clean-install verification on
Windows x64 and Linux x86-64. Both runs install the actual distribution file into
a new virtual environment and execute outside the source directory. No Windows
installer or desktop GUI verification was performed during this final pass.

| Distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| `free_bible_reader-0.3.0-py3-none-any.whl` | 223,102,823 | `2e0eeb9fa1605665aa7ab3f10180d03f3b3843b69dadbd217b26984e1c27b5af` |
| `free_bible_reader-0.3.0.tar.gz` | 217,383,942 | `4309515629f3dd2fab836eb3e29bd84f3a3b3df986dd96d004de81c153d1024a` |

The wheel is pure Python with public SQLite, JavaScript, interface, font and
attribution assets. Its own payload contains no EXE, DLL, PYD, SO or ONNX voice
models. Optional document dependencies supply their own platform-specific wheels.
The archive CRC, wheel tag, source-distribution metadata and safe member paths
passed inspection. All six public database payloads match between wheel and
source distribution and total **929,001,472 bytes** before compression.

| Acceptance group | Windows | Linux |
| --- | --- | --- |
| Installed metadata and console entry point | PASS | PASS |
| Four actual bundled Bible editions | PASS | PASS |
| Complete chapters and original-text Unicode hashes | PASS | PASS |
| Node-free reference parsing with invalid/ambiguous states | PASS | PASS |
| Real English and Romanian Scripture search | PASS | PASS |
| Three independent research engines with provenance | PASS | PASS |
| Separate personal SQLite import and native labels | PASS | PASS |
| Selectable PDF and editable DOCX Unicode export | PASS | PASS |
| Actual CLI commands | PASS | PASS |
| Loopback server reading and process shutdown | PASS | PASS |
| Six database integrity, foreign-key and source-hash checks | PASS | PASS |
| **Total** | **11 / 11** | **11 / 11** |

The reading check covers Genesis 1, Psalm 23, Matthew 5, John 1, John 3,
Romans 8 and Revelation 21 in WEB, KJV and BSB: 21 complete chapters and
714 verse records. Romanian John 3:16–18 is also checked. Biblia Liberă remains
accurately identified as a **draft New Testament only**, with 27 books and
7,958 scripture rows. The three English editions contain 93,307 rows in total.

The executed CLI includes `--help`, `version`, `catalog`, `read`, `search`,
`research`, `validate-db`, preview and confirmed `import-db`, PDF/DOCX `export`,
and `serve`. Imports use an explicitly labeled synthetic fixture, not invented
Scripture. Its chapter zero, verse range, suffix and Romanian diacritics are
preserved; source-file hashes remain unchanged. Real bundled biblical datasets
provide reading, search, export and all three research-engine evidence.

Windows uses CPython 3.14.10 in `.wheel-final-venv`. Linux uses CPython 3.14.10
and SQLite 3.46.1 in a fresh virtual environment inside the existing
`python:3.14-slim` Docker image. Linux has no Node executable. The registered
Ubuntu WSL environment could not start because its VHDX is missing; no repair
was attempted. Linux container verification is not a physical Android, macOS or
bare-metal desktop GUI claim. Dependencies passed `pip check` on both systems.

The default wheel parser is deliberately bounded to EN/RO/DE names, canonical
OSIS, chapters and same-book ranges within KJV66 coordinates. It preserves
invalid, ambiguous, unsupported and unrecognized states. The complete pinned
upstream parser remains available through an explicit optional Node backend or
platform delegate. Coordinate recognition never proves edition equivalence.

PDF text was extracted with pypdf; DOCX paragraphs were reopened with python-docx.
These tests establish document structure and selectable Unicode text. This pass
does not claim physical speaker listening, new voice-model synthesis, visual
document review, an installed Windows 0.3.0 GUI, or physical mobile-device testing.

Private profiles are configured before application imports. Tests do not read
the original `C:\ggg` corpus or package private notes, downloaded voice models or
credentials. The separate owner-workspace checksum investigation is outside this
package verification and is not resolved by these test results.

The relevant source backend suite passed **101 tests** using a new profile and
`python -m unittest discover -s tests -t .`. Earlier harness failures and initial
wheel evidence are retained, not overwritten. The initial Linux bind-mount
permission error was resolved by copying the public wheel into the disposable
container; no host artifact permissions were changed.

Reproduction and evidence:

- `tools/verify_python.py` exercises the installed wheel from an external working directory.
- `tools/Verify-Python-Linux.ps1` creates and removes only its uniquely named test container.
- `evidence/python/windows-final-wheel-verification.json` contains the Windows checks.
- `evidence/python/linux-wheel-verification.json` contains the final Linux checks.
- `evidence/python/final-artifact-integrity.json` records exact distribution hashes and archive checks.
- `PYTHON-PACKAGE.md` documents installation, public APIs, imports and limitations.

The Python distributions are ready for delivery. No package has been published
by this verification task. Existing Windows 0.3.0 build artifacts are preserved
and remain outside this final package acceptance classification.
