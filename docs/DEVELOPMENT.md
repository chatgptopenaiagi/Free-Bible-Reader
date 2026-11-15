# Developing FREE BIBLE READER

The application is a local Python service with browser ES modules, read-only SQLite assets and a desktop launcher. Its own source code is [MIT licensed](../LICENSE); data and packaged runtimes have [separate notices](../THIRD-PARTY-NOTICES.md).

## Existing architecture

| Path | Responsibility |
|---|---|
| `app.py` | Desktop lifecycle, loopback HTTP service, launcher preferences, existing-instance handling and self-test. |
| `reader/service.py` | Main edition catalog, native chapter navigation and parameterized SQLite FTS5 search. |
| `workbench/` | Responsive reader, search, settings and research interface. |
| `ui-core/` | Shared theme, color, typography, preferences, layout and localization modules. |
| `bridge/` | Reference parsing, bounded research requests and explicit source-edition resolution. |
| `engines/visual/`, `engines/aggregate/`, `engines/phrase/` | Three independent research models, retaining source-specific semantics. |
| `parser/` | Local parser adapter and vendored MIT-licensed upstream modules. |
| `data/` | Main reader database, source JSONL archive and immutable research assets. |
| `tools/`, `installer/` | Reader-data build, Windows packaging and per-user Inno installer definition. |

The service uses Python’s standard library and SQLite integration. There is no mandatory database server, frontend framework, npm dependency installation or remote API. The parser executes a local Node process; the Windows application package contains that runtime. Installed application requests open the SQLite databases read-only.

## Source prerequisites

The recorded source verification used Python 3.14.10 x64, Node.js 26.12.1 and PowerShell 7. These are observed build/test versions, not proof that every other version is incompatible. Reuse suitable installed tools and check their actual executable paths before adding dependencies.

Clone the repository and enter it:

```powershell
git clone https://github.com/chatgptopenaiagi/Free-Bible-Reader.git
Set-Location Free-Bible-Reader
```

The following commands use `python`, `node` and `pwsh` as placeholders for your verified executables. On machines with multiple Python installations, invoke the chosen interpreter by its full path rather than assuming the default resolves correctly.

## Reader data and research assets

Git includes `data/reader.sqlite`, the compressed `data/reader-source.jsonl.gz` source records and the compact `data/xref_reference.sqlite` reference seed. The three larger research databases are distributed separately:

- `data/xref_visual.sqlite`
- `data/xref_aggregate.sqlite`
- `data/xref_phrase.sqlite`

Use the research asset ZIP and SHA-256 in the committed [release manifest](../data/research-release.json). Startup never silently downloads research data. For version 0.1.0, PowerShell can read that manifest directly:

```powershell
$research = Get-Content -LiteralPath .\data\research-release.json -Raw | ConvertFrom-Json
python engines/fetch_research_assets.py --url $research.url --sha256 $research.sha256
```

Alternatively, use `--release-zip PATH` for an already downloaded archive and the same `--sha256` value. The checksum is mandatory in both forms. The helper checks the archive hash, extracts only the four named research SQLite assets, validates their SQLite structure and preserves an existing different file. An identical reference seed or database is reused. It does not modify `reader.sqlite`. The ZIP also carries dataset attribution and notices.

Source execution can use a suitable `node` on PATH. Windows packaging requires the verified Node executable at `runtime/node.exe` and its license notice. The Git source does not include that binary; supply an official, appropriate Windows x64 runtime as a deliberate build input. The complete installer supplies it for end users.

## Run and test

```powershell
python app.py
```

For a terminal-owned process without the desktop companion:

```powershell
python app.py --headless --no-browser
```

The launcher attempts a remembered loopback origin, initially port 48179, and can fall back to an available port if it is occupied. The current CLI treats `--port 0` as this default behavior; an explicit nonzero `--port` selects that port and reports a bind failure rather than silently changing it. It never needs a public bind. Terminate a terminal-owned process with Ctrl+C; use the companion’s Close application action in normal desktop mode.

Run the source checks from the repository root:

```powershell
python -m unittest discover -s tests -t . -v
node --test tests/ui/core-preferences.mjs tests/ui/core-theme-typography.mjs
node --test tests/i18n/translations.test.mjs
python app.py --self-test --self-test-output .\self-test.json
```

Release preparation recorded 28 passing Python tests, 24 passing core Node tests, 15 localization checks and nine successful frozen-executable self-test checks, including all three research engines. The localization file contains fifteen internal checks; it is not fifteen separate Node test files. These observations do not replace testing a new change or an installer on a target machine. Browser acceptance and actual installer results are separate release evidence.

For browser acceptance, install only the locked developer package and point the harness at a running reader. This command uses an existing Edge installation and does not download a browser:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
$env:READER_URL = 'http://127.0.0.1:48179/' # Use the actual URL reported by your running reader.
$env:READER_RUNTIME_KIND = 'installed'
$env:READER_RUNTIME_STATE = Join-Path $env:LOCALAPPDATA 'FreeBibleReader\runtime.json'
npm run test:browser
```

Start the installed application first. For source-runtime testing, omit the two `READER_RUNTIME_*` variables and label the result as source testing. Set `BROWSER_EXECUTABLE` if your Edge executable uses a different verified location. The harness creates an isolated browser context, writes receipts under `evidence/browser/` and captures screenshots; it does not change the desktop browser’s stored preferences.

## Rebuilding the main reader database

`tools/build_reader_data.py` can rebuild the reader from the included compressed source records. It refuses to overwrite an existing `data/reader.sqlite`. Work in a disposable build checkout or keep a deliberate backup before preparing a new output; preserve the distributed database when simply running the application.

Once the target path is intentionally absent in that build checkout:

```powershell
python tools/build_reader_data.py
```

With `reader-source.jsonl.gz` present, this operation needs no upstream download. Its source-acquisition fallback, used only if that archive is missing, obtains the published WEB verse-per-line archive and requires the local native phrase database for KJV/BSB records. The build compares all text records exactly, creates FTS5, checks integrity/foreign keys and writes verification receipts under `evidence/`; create that directory in a fresh checkout if absent. Keep the original source manifests when regenerating assets.

The reader schema preserves edition-native references. Do not normalize WEB’s Romans structure into KJV coordinates or assert that matching labels establish textual identity.

## Build the Windows installer

Build inputs include all four research SQLite files, `reader.sqlite`, the Node executable, frontend modules and applicable licenses. `requirements-build.txt` pins PyInstaller 6.22.3. Use an isolated build environment and a suitable official Inno Setup compiler; the release preparation used Inno Setup 7.1.1. No global Python package installation is required.

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
pwsh -File tools/build_windows.ps1 -BuildPython .\.build-venv\Scripts\python.exe -InnoCompiler 'C:\Path\To\InnoSetup\ISCC.exe'
```

Replace the compiler path with its real verified location. The script builds a PyInstaller one-directory application, invokes `installer/FreeBibleReader.iss` and calculates SHA-256 for `dist/Free-Bible-Reader-0.1.0-windows-x64-setup.exe`. The Inno definition is per user, requests the lowest privilege level and creates no permanent service. Packaging alone does not establish installation success: test the frozen self-test, actual installation, browser operation, clean Close application and uninstallation separately before publishing.

No code-signing certificate is configured for this release. Identify unsigned artifacts accurately and publish exact checksums; do not represent an unsigned binary as a verified publisher signature.

## Source semantics and portability boundaries

The main reader contains English WEB/KJV/BSB. Interface localization is English/Romanian/German and does not rewrite source text. Research native KJV/BSB/AOV identifiers are separate from main-reader IDs. The `eng-kjv` compatibility alias explicitly selects the research KJV source; it is not a proof of equivalence with an external corpus. The visual/aggregate graphs do not claim BSB/AOV mappings, and WEB does not inherit KJV graph compatibility.

Public assets omit S21 data, private edition mappings, cached private resolutions and private host metadata. Repackaging must preserve those derivations and their attribution. Read [research-PROVENANCE.md](../licenses/research-PROVENANCE.md) before changing datasets.

The browser architecture can be adapted elsewhere, but the shipped/tested desktop build is Windows x64. Native Android/iOS/macOS/Linux packaging, universal font coverage and universal ancient-script mark placement are outside current certification. No private corpus package, SQL instance or original engineering workspace is a runtime dependency.
