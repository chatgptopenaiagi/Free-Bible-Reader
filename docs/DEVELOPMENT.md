# Developing FREE BIBLE READER

The application is a local Python service with browser ES modules, read-only SQLite assets and a desktop launcher. Its own source code is [MIT licensed](../LICENSE); data and packaged runtimes have [separate notices](../THIRD-PARTY-NOTICES.md).

Version 0.1.1 improves reading continuity and startup recovery without rebuilding Scripture or research data. The actual final installed application passed 68 reading-experience, 24 existing browser and eight startup-recovery checks, alongside production lifecycle/integrity verification. [VERIFICATION.md](VERIFICATION.md) records exact scope and limitations. Local application verification and public delivery verification are separate checks.

## Existing architecture

| Path | Responsibility |
|---|---|
| `app.py` | Desktop lifecycle, loopback HTTP service, launcher preferences, existing-instance handling and self-test. |
| `reader/service.py` | Main edition catalog, native chapter navigation and parameterized SQLite FTS5 search. |
| `workbench/` | Responsive reader, search, settings and research interface. |
| `workbench/bootstrap.js` | Dependency-free startup feedback, caught module/localization initialization and explicit reload recovery. |
| `workbench/reader-state.js` | Validated saved reading coordinates and navigation sequencing. |
| `workbench/reader-search.js` | Immutable submitted search context and stale-response handling. |
| `workbench/reader-comparison.js` | Actual native-coordinate comparison text and explicit missing/error outcomes. |
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

Use the research asset ZIP and SHA-256 in the committed [release manifest](../data/research-release.json). Version 0.1.1 reuses that published **0.1.0** asset, with SHA-256 `bcb76773dbd025a8acd14c9e78be4b79ca2339807053ba368b2f4fbec035c8e1`. Installer users already have its data and do not need this additional download. Startup never silently downloads research data. PowerShell can read the manifest directly:

```powershell
$research = Get-Content -LiteralPath .\data\research-release.json -Raw | ConvertFrom-Json
python engines/fetch_research_assets.py --url $research.url --sha256 $research.sha256
```

Alternatively, use `--release-zip PATH` for an already downloaded archive and the same `--sha256` value. The checksum is mandatory in both forms. The helper checks the archive hash, extracts only the four named research SQLite assets, validates their SQLite structure and preserves an existing different file. An identical reference seed or database is reused. It does not modify `reader.sqlite`. The ZIP also carries dataset attribution and notices.

Source execution can use a suitable `node` on PATH. Windows packaging requires the verified Node executable at `runtime/node.exe` and its license notice. Git does not include that binary; supply the official Windows x64 Node version, size and hash recorded in the portable [build-input manifest](../data/build-inputs.json). It pins six relative-path inputs: five SQLite files and Node. Packaging rejects missing or changed inputs and does not need the original machine or private evidence directory. The complete installer supplies these inputs for end users.

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
node tests/ui/reader-navigation.mjs
node tests/i18n/translations.test.mjs
python app.py --self-test --self-test-output .\self-test.json
```

Latest source checks passed 29 Python tests, 24 core tests, 14 focused reader tests and 15 internal localization checks, with 521 matching keys in each language. The earlier 28-test Python record is a historical baseline; the added test exercises 96 bounded HTTP fetches. Counts describe the recorded suite version; new tests may change them. Localization evidence now uses a unique default output or `FBR_TEST_EVIDENCE_DIR` and refuses existing receipt collisions. A source self-test does not establish a frozen or installed-runtime pass. Browser acceptance and actual installer results are separate evidence.

For browser acceptance, install only the locked developer package and point the harness at a running reader. This command uses an existing Edge installation and does not download a browser:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
$env:READER_URL = 'http://127.0.0.1:48179/' # Use the actual URL reported by your running reader.
$env:READER_RUNTIME_KIND = 'source'
$env:EXPECTED_READER_VERSION = '0.1.1'
node tests/browser/reading-experience.mjs
npm run test:browser
node tests/browser/bootstrap-recovery.mjs
```

Start the target application first. For installed testing, use `READER_RUNTIME_KIND=installed` and set `READER_RUNTIME_STATE` to that actual runtime's state file; match its URL, process and installed executable. Changing the variable alone cannot turn a source test into installed verification. Set `BROWSER_EXECUTABLE` for a different verified Edge path. `PLAYWRIGHT_MODULE` can select an existing compatible module. `READER_EVIDENCE` and `READER_SCREENSHOTS` select fresh outputs; avoid old receipt paths. The harnesses create isolated contexts rather than modifying personal browser preferences. The final actual production package passed 68 reading-experience, 24 existing acceptance and eight startup-recovery checks, including the book-selection viewport correction and intentional module/catalog/bootstrap failures. Earlier candidate receipts remain historical, rather than substitutes for the final installed run.

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
pwsh -File tools/build_windows.ps1 -Phase App -BuildPython .\.build-venv\Scripts\python.exe -InnoCompiler $env:INNO_COMPILER
pwsh -File tools/build_windows.ps1 -Phase TestInstaller -InnoCompiler $env:INNO_COMPILER
```

Set `INNO_COMPILER` to the exact verified compiler executable before these commands. Do not assume a compiler is installed or on PATH. `App` checks versions and all six pinned inputs, then creates a one-directory application and immutable `app-build-manifest.json` under `dist/0.1.1/` by default. `TestInstaller` creates a verification installer with a separate application/uninstall identity; it installs nothing. Outputs and receipts are create-only. Use a deliberate new output run for later edits and retest it rather than overwriting a completed build. `-ArtifactDirectory` selects a versioned output below this repository's `dist/`.

Install and verify the isolated package as explicit operations, retaining the same fresh run ID:

```powershell
pwsh -File tools/verify_installer.ps1 -Phase InstallTest -RunId verify-example-011
pwsh -File tools/verify_installer.ps1 -Phase VerifyTest -RunId verify-example-011
```

The test destination is a dedicated marked verification directory. The existing ordinary installation, uninstall registration and shortcuts are checked for preservation. `VerifyTest` compares all installed bundle files to the immutable build manifest and runs the clean-environment self-test; it does not prove actual companion/browser operation or automatically uninstall.

Launch the exact verification executable normally, run the installed browser suites and check normal companion shutdown. After those GUI checks are complete and that specific runtime is closed normally:

```powershell
pwsh -File tools/verify_installer.ps1 -Phase UninstallTest -RunId verify-example-011 -ConfirmGuiFinished
pwsh -File tools/build_windows.ps1 -Phase ProductionInstaller -InnoCompiler $env:INNO_COMPILER
```

Only the test identity is removed. Production installer creation is separate from ordinary installation. The later `UpdateOwner` phase requires `-UpdateOwnedInstall`, the current owner's expected executable SHA-256 and an approved same-build test receipt; it cannot replace the isolated verification phases. Do not use the owner's uninstaller for a test. The installer creates no permanent service and requests the lowest privilege level.

After production verification, `python tools/package_research_data.py` creates versioned release metadata/checksums. Despite its historical name, this release utility reuses the published 0.1.0 ZIP, creates no new large research archive, and does not publish anything.

No code-signing certificate is configured for this release. Identify unsigned artifacts accurately and publish exact checksums; do not represent an unsigned binary as a verified publisher signature.

## Startup recovery boundary

The page loads a small dependency-free external bootstrap, which dynamically imports the app and catches module or initial localization failure. Literal HTML status/retry feedback exists even if bootstrap loading fails. Its EN/RO/DE messages intentionally do not require a catalog request, and fixed failsafe colors remain readable without application CSS. Explicit Retry reloads the page without clearing storage; there is no automatic reload loop. The final server source uses a bounded pending queue of 128 instead of the inherited five. A controlled local A/B run recorded 67 refused requests out of 280 with queue five versus zero out of 280 with queue 128. The rebuilt production package passed lifecycle/integrity checks, all eight failure/retry scenarios and the 68/24 browser suites. A final repeated-start diagnostic saw 16/16 ready pages and zero refused requests in 120 bounded static requests. These scoped successes do not establish a universal failure rate.

## Source semantics and portability boundaries

The main reader contains English WEB/KJV/BSB. Interface localization is English/Romanian/German and does not rewrite source text. Research native KJV/BSB/AOV identifiers are separate from main-reader IDs. The `eng-kjv` compatibility alias explicitly selects the research KJV source; it is not a proof of equivalence with an external corpus. The visual/aggregate graphs do not claim BSB/AOV mappings, and WEB does not inherit KJV graph compatibility.

Public assets omit S21 data, private edition mappings, cached private resolutions and private host metadata. Repackaging must preserve those derivations and their attribution. Read [research-PROVENANCE.md](../licenses/research-PROVENANCE.md) before changing datasets.

Display preferences and `free-bible-reader.position.v1` are separate browser-origin records. Position stores identifiers/coordinates, not Scripture. Preserve request sequencing and immutable search context when changing the reader; presentation changes should retain the passage and avoid new reading/research requests. Comparison at shared coordinates is not certified versification alignment.

The browser architecture can be adapted elsewhere, but the shipped/tested desktop build is Windows x64. Native Android/iOS/macOS/Linux packaging, universal font coverage and universal ancient-script mark placement are outside current certification. No private corpus package, SQL instance or original engineering workspace is a runtime dependency.
