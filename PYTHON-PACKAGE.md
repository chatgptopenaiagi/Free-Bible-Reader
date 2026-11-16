# FREE BIBLE READER for Python

An offline, local-first Bible reading and study package. The 0.3.0 wheel includes
WEB, KJV, BSB, the Romanian Biblia Liberă draft **New Testament only**, and all
three public source-specific research databases. Private BIBLIA corpus data,
notes and downloaded voice models are never included.

Requires Python 3.11 or later. The distribution's own code and assets are portable;
optional document and speech dependencies resolve separately for each platform.
No Python interpreter, Node executable or Windows speech DLL is embedded.

```sh
python -m pip install free_bible_reader-0.3.0-py3-none-any.whl
fbr --help
fbr version
fbr catalog
fbr --parser portable read "John 3:16" --edition ronbl
fbr search "Dumnezeu" --edition ronbl --limit 5
fbr --parser portable research "John 1:1" --engine all --limit 5
fbr serve
```

`serve` binds only to `127.0.0.1`; it is not a remote mobile server. A personal
profile is stored outside the installed package. Use `fbr --profile PATH ...` or
`FBR_STUDIO_DIR` to isolate one. Linux respects `XDG_DATA_HOME` and Windows uses
`LOCALAPPDATA`. Source data is opened read-only.

```sh
fbr validate-db my-bible.sqlite
fbr inspect-db my-bible.sqlite
fbr import-db my-bible.sqlite --mapping mapping.json --name "My edition" --language ro
fbr import-db my-bible.sqlite --mapping mapping.json --name "My edition" --language ro --yes
```

The first import command previews only. A mapping JSON object names actual
columns: `{"table":"verses","book":"book","chapter":"chapter","verse":"verse","text":"text"}`.
Use `edition_column` and `edition_value` to select one edition from a shared source.
Imports preserve native labels, verse ranges, source hashes and raw records.
Original files are never rewritten. Unknown SQL statements are rejected, not run.

```sh
python -m pip install 'free-bible-reader[documents]'
fbr export --edition ronbl --reference "John 3:16-18" --format pdf --output study.pdf
fbr export --edition ronbl --reference "John 3" --format docx --output study.docx
```

The public Python API is `free_bible_reader.services`: `catalog`, `chapter`,
`passage`, `search`, `parse_reference`, `research`, `inspect_database`,
`import_database`, `validate_database`, `export_document`, `configure_profile`.
Chapter records expose edition, language, book, native chapter/verse,
original_text and source provenance without replacing the existing GUI contract.

The installed wheel defaults to a **strict bounded parser** that recognizes
EN/RO/DE names, OSIS, chapters and same-book ranges in KJV66 coordinates. It is
not the upstream parser's complete grammar and does not infer edition equivalence.
The source/frozen Windows deployment retains automatic use of the pinned upstream
parser. Choose explicitly with `--parser portable`, `--parser upstream` (separately
available Node required), or `--parser auto` (upstream when available, strict fallback).
`bridge.reference.configure_parser(delegate)` allows an explicit platform adapter
to supply the full parser. Windows native speech and SQL Server helpers remain
Windows adapters; their existence is not a Linux or Android compatibility claim.

Public datasets and bundled components retain their individual attribution and
notices in `free_bible_reader/assets/`. The application source is MIT licensed;
that does not relicense separately attributed texts or third-party components.
