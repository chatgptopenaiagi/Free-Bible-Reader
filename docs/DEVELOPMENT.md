# Developing FREE BIBLE READER 0.2.0

The application is a local Python HTTP service, standards-based browser ES modules and a small Tk companion. The existing reader and three attributed research engines remain separate from the new studio services.

| Location | Responsibility |
|---|---|
| `app.py`, `workbench/server.py` | Desktop lifecycle, loopback-only routes, streaming responses, native-dialog scheduling and self-test |
| `reader/` | Immutable bundled Scripture and the combined personal-edition catalog |
| `studio/library.py`, `importers.py`, `downloads.py`, `sqlserver.py` | Private library, restricted format adapters, bounded downloads and explicit read-only SQL Server |
| `studio/search.py` | Bounded Unicode search with exact/folded matching; original quick English FTS remains available |
| `studio/workspace.py`, `documents.py` | Immutable source-linked annotations, collections, corrections and real PDF/DOCX |
| `studio/audio.py`, `piper_worker.py`, `windows_speech.ps1` | Verified voice catalog/downloads, bounded synthesis and a separate frozen inference worker |
| `studio/native.py`, `jobs.py`, `paths.py` | Main-thread Windows dialogs, cancellable bounded jobs and separate private storage |
| `workbench/studio/` | Menu/selection, library, search, workspace/export and audio modules; six EN/RO/DE namespaces |
| `ui-core/` | Existing reusable themes, typography, localization, preferences and adaptive panels |
| `bridge/`, `engines/`, `parser/` | Existing independent research APIs and reference semantics |

## Reuse an isolated environment

The verified route is Python 3.14.10 x64, project-local Node 26.12.1, PyInstaller 6.22.3 and Inno Setup 7.1.1 on Windows 11. Reuse working tools rather than installing global substitutes. End users do not need these tools.

Create a virtual environment with an existing suitable interpreter, then install the two dependency sets separately:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-venv\Scripts\python.exe -m pip install --require-hashes -r requirements-studio.txt
```

The runtime manifest pins all thirteen Windows/CPython 3.14 inference/document wheel hashes. The build-only manifest is separate so pip's runtime hash mode does not incorrectly apply to PyInstaller's build dependencies. Do not install Torch, CUDA or training frameworks for narration. Tests additionally use pypdf for document extraction; pypdfium2/LibreOffice were verification tools, not application requirements.

## Restore public build inputs

The public Git source includes the compact English reader, reference seed, Romanian database/source evidence, eSpeak runtime and fonts. Three larger research databases and Node are ignored build inputs. Use:

```powershell
pwsh -File tools/prepare_build_inputs.ps1 -Mode Restore
pwsh -File tools/prepare_build_inputs.ps1 -Mode Check
```

The helper restores only missing ignored inputs from official Node HTTPS and the existing pinned public v0.1.0 research-data release. It validates exact sizes/SHA-256, never executes downloaded Node as an installer, and refuses to overwrite differing existing inputs. `data/build-inputs.json` defines seven unique pins. The separate eSpeak manifest verifies all 444 files, with no links, missing or unexpected entries. Voice models are not build inputs and must not be copied into the installer or Git.

## Run and test

```powershell
.\.build-venv\Scripts\python.exe app.py --profile-dir "$env:LOCALAPPDATA\FBRDevelopment"
.\.build-venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\runtime\node.exe --test tests/ui/*.mjs tests/i18n/translations.test.mjs
pwsh -File tests/installer-guards.ps1
pwsh -File tests/build-input-guards.ps1
```

Use `-t .` for unittest discovery so `tests/reader` does not shadow the application `reader` package. For a headless service, add `--headless --no-browser --port <available-loopback-port>`. Native dialogs are deliberately unavailable in headless mode. A separate `--profile-dir` isolates private library/voices/notes/runtime state; normal users keep `%LOCALAPPDATA%\FreeBibleReader`.

Browser harnesses in `tests/browser/` require `READER_URL` and an existing Edge/Playwright Core route. `PLAYWRIGHT_MODULE` selects an existing module; do not install another browser unnecessarily. Set `READER_RUNTIME_STATE` to the actual runtime JSON and `READER_RUNTIME_KIND=installed` for process-bound installation evidence. Give every run fresh `READER_EVIDENCE` and `READER_SCREENSHOTS` paths outside public source when private editions exist. Synthetic fixtures must remain clearly labeled. Audio test downloads are opt-in test actions, not startup behavior.

## Build, installation and publication are separate

The obsolete root-level 0.1.x PyInstaller spec was removed. The verified build script generates a versioned spec with Studio resources, inference dependencies and input guards; do not reuse an older spec that omits them.

```powershell
pwsh -File tools/build_windows.ps1 -Phase App -ArtifactDirectory <fresh-project-dist-folder>
pwsh -File tools/build_windows.ps1 -Phase TestInstaller -ArtifactDirectory <same-folder>
pwsh -File tools/verify_installer.ps1 -Phase InstallTest -Installer <verification-setup.exe> -RunId <fresh-id>
pwsh -File tools/verify_installer.ps1 -Phase VerifyTest -RunId <same-id>
```

The verification installer has a separate identity; it does not overwrite the owner's installation. Verify the real GUI, reading, audio, native dialogs and imported-library behavior before `UninstallTest -ConfirmGuiFinished`. The self-test strips developer runtime paths and compares all immutable bundle files. A successful compile is not an installation test.

`ProductionInstaller` creates the ordinary setup separately. `UpdateOwner` requires the explicitly expected prior executable hash, a successful prior owner receipt and a same-build isolated verification receipt. No unrelated application or database is touched. Outputs and evidence are create-only. The `promote_verified_bundle.ps1` route documents a fresh staging copy of a verified runtime plus explicitly identified source-notice additions; it never rewrites an earlier bundle or claims a recompilation.

Package the full installer, exact checksums and matching speech corresponding-source ZIP. The original research-data ZIP remains immutable. Do not publish private databases, annotation stores, models, WAV caches, credentials, build environments or machine-specific evidence. `THIRD-PARTY-NOTICES.md` distinguishes application MIT code from separately licensed components. The package is unsigned.

## Integrity and platform boundaries

Preserve edition-specific native references and raw originals. Personal corrections are separate records. Engine compatibility is explicit; a matching coordinate or phrase in another edition is not a proven mapping. SQL dumps are parsed as data rather than executed, and SQL Server access is explicit/read-only. Filesystem capabilities originate from native file choice, controlled uploads or staged HTTPS downloads.

The current shipped container is Windows x64 with an existing browser. Responsive tests do not certify physical Android/iPhone devices or native mobile packages. Recorded PCM/playback checks do not establish human-perceived sound on every speaker. PDF Romanian text was verified; universal complex-script shaping is not certified.
