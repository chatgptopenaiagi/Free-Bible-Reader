# Reproducing the audio browser checks

`studio-audio.mjs` drives the real application through an existing Edge browser. It does not launch the application, install a browser or provide mock speech responses. WAV generation, selected source text, pending pause/Stop, lazy chapter traversal, translated controls and mobile controls use the actual loopback service. Delayed-response cases use `route.fetch()` on a real request.

By default the harness previews only voices that the runtime actually reports installed. It never downloads or removes a model. Unavailable optional providers and all three model-lifecycle cases are recorded as **SKIP**, separately from PASS and FAIL. A successful run with skips is `PASS_WITH_SKIPS`, not a claim that all16 scenarios were executed. SAPI/Windows.Media discovery reflects this PC; no particular Windows voice or Romanian Windows package is assumed.

## Start an isolated source runtime

Install the documented project dependencies in an isolated environment and restore the pinned build inputs as described in [DEVELOPMENT.md](../../docs/DEVELOPMENT.md). Use a separate test profile even for ordinary audio checks: the application creates local WAVs and may record ordinary reading history in the selected profile. Do not use a daily personal profile for destructive acceptance testing.

In the first PowerShell terminal, from the repository root:

```powershell
$profile = Join-Path $env:LOCALAPPDATA ('FBRVerification\audio-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profile
Write-Output $profile # Copy this exact path to the second terminal.
& .\.build-venv\Scripts\python.exe .\app.py --headless --no-browser --profile-dir $profile
```

The application prints its actual loopback URL and writes `runtime.json` inside that profile. Leave the process running. It can use an available port; do not substitute an unrelated reader instance's URL. When finished, stop this terminal-owned runtime with Ctrl+C. The harness never closes the runtime or native companion.

In the second terminal, from the same repository:

```powershell
$profile = '<exact test profile path printed by the first terminal>'
$env:READER_RUNTIME_STATE = Join-Path $profile 'runtime.json'
$env:READER_URL = (Get-Content -LiteralPath $env:READER_RUNTIME_STATE -Raw | ConvertFrom-Json).url
$env:READER_RUNTIME_KIND = 'source'
$env:EXPECTED_READER_VERSION = '0.2.0'
$env:FBR_AUDIO_ALLOW_MODEL_CHANGES = '0'
# Optional: use an already available compatible Playwright module through PLAYWRIGHT_MODULE.
# Otherwise restore this repository's locked developer package; no browser is downloaded:
npm ci --ignore-scripts --no-audit --no-fund
& .\runtime\node.exe .\tests\browser\studio-audio.mjs
```

Use your verified Node executable if the pinned `runtime/node.exe` has not yet been restored. `PLAYWRIGHT_MODULE` may be a local module path or `file:` URL; without it, the harness imports `playwright-core` normally. `BROWSER_EXECUTABLE` overrides the existing Edge executable path. The default is the standard `Program Files (x86)` Edge location; absence produces an error rather than a browser installation.

`READER_URL` is mandatory and must be a credential-free loopback HTTP root URL. Non-loopback browser requests are blocked. This is not equivalent to disabling operating-system networking, and intentional model downloads are server-side requests when explicitly enabled.

## Optional managed-model lifecycle

Only enable this for a fresh disposable profile created for this test. It downloads about63.3MB of Romanian Mihai files, tests cancellation and installation, then removes and reinstalls **only the model this run newly installed**. It leaves that test model installed afterward. No English or German neural model is automatically acquired.

```powershell
$env:FBR_AUDIO_ALLOW_MODEL_CHANGES = '1'
$env:FBR_AUDIO_TEST_PROFILE = $profile
& .\runtime\node.exe .\tests\browser\studio-audio.mjs
```

The opt-in alone is insufficient. The harness requires the actual runtime state and verifies its health PID, URL and Windows process executable. It also verifies that the live process was explicitly launched with `--profile-dir` equal to the selected real profile path. The profile must be below `%LOCALAPPDATA%\FBRVerification` or this repository's `reports\MISSION-FBR-003\evidence`; the normal owner profile is outside those allowed roots. The state file must be that profile's default `runtime.json`.

On Windows source runs, a virtual-environment `python.exe` can be a redirector whose live process image is the base interpreter. The harness accepts this only in `source` mode when `pyvenv.cfg` explicitly binds both `home` and `executable` to the actual observed base Python. Frozen/installed executable matching remains strict.

If Mihai or its folder existed before the run, model mutation cases are **skipped and that installation is protected**, even with the opt-in. Before any removal, the guard rechecks the runtime/profile identity and all expected managed-model file hashes. Unknown or unrelated files remain protected by the backend. An out-of-scope profile is rejected before browser/provider/model operations. Do not run another model-management task concurrently in the same test profile.

## Frozen and installed runtime evidence

Start the exact intended application separately with an isolated `--profile-dir`, then set its actual `READER_RUNTIME_STATE`, `READER_URL` and `READER_RUNTIME_KIND` (`frozen` or `installed`). `READER_EXECUTABLE_SHA256` can require an independently recorded exact executable hash. Installed mode requires runtime-state and live-process identity evidence; changing the mode string alone does not prove an installer ran.

The harness never performs installation, production update, uninstallation, Windows voice settings changes or native Save As. Installer/lifecycle receipts remain separate. A verification installer with another AppId must not be described as a production-owner installation merely because the same executable passes this suite.

## Results and limits

Outputs go to a new unique folder under ignored `reports/MISSION-FBR-003/evidence`, or a fresh directory specified by `FBR_AUDIO_EVIDENCE_DIR`. Existing receipt directories are refused. `audio-gui.json` records the harness SHA, requested runtime/process evidence, actual job results, text hashes, individual PASS/FAIL/SKIP cases and screenshots. Only jobs created through this harness's page are cancelled during cleanup; the application process and unrelated jobs are preserved.

The original private source, frozen-main and verification-installer runs executed all16 scenarios with explicitly isolated model lifecycle testing. Those dated receipts remain historical evidence. New public runs report their own actual result and skipped scope rather than inheriting those passes.

Advancing HTMLAudio time and valid nonzero PCM prove playable generated audio. They do not establish pronunciation quality, physical speaker output or human listening. No complete-book auditory review or physical-mobile-device certification is claimed.
