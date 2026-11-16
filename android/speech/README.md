# Android offline speech adapter

This Android library builds the maintained OHF Piper C++ engine through the pinned
Piper Kotlin native build. It does not package a Windows executable or DLL and does
not require Python for speech inference. Lite does not depend on this module.

`SpeechBridge.invoke(Context, operation, payloadJson)` accepts `speech.catalog`,
`speech.synthesize`, and `speech.cancel`. The two local provider identifiers are
`piper` and `espeak-ng`; the app adapter merges its independently discovered
`android-native` provider. Call blocking work on a worker thread. Cancellation can
run on another thread. Piper and standalone eSpeak use one process-wide lock.

Synthesis accepts `provider`, `voice`, `text`, `speed`, `output_path` and
`request_id`. Text is UTF-8, at most 25,000 characters; speed is 0.5–2.2. Output
must remain within the app's files or cache directory. The result reports a real
16-bit mono WAV's sample rate, sample count, duration, peak, RMS, byte count and
SHA-256. The browser's audio element provides pause/resume and playback volume.
Cancellation removes an incomplete WAV. No external speech service is contacted.

Prepare inputs from the worktree root using the existing build Python:

```powershell
python android/speech/prepare_native.py
python android/speech/prepare_assets.py --cmake <verified-host-cmake> --generator "Visual Studio 18 2026"
```

The source preparer verifies the exact pinned revisions and ONNX Runtime hash.
The host build uses a separate eSpeak source copy and compiles all dictionaries,
including Romanian and German. The public models are obtained only from the
pinned URLs and SHA-256 values in `studio/voice_manifest.json`; an installed user's
voice directory is never used. `build-support/` remains excluded from Git.

Assets are staged under `build-support/android-assets/speech/fbr-speech` with a
per-file integrity manifest. The app copies changed resources into its private
`files/speech` directory after checking SHA-256. Existing equal resources remain
in place during an upgrade. Voice cards and all relevant notices are included.

The pristine Piper Kotlin checkout and its three pinned submodules remain
unchanged. Its two declared Android patches are applied to `piper-adapted` only.
The relevant source/patch identifiers are recorded in `source-origins.json`.
GPL-covered native components and the combined distribution retain their terms;
the first-party application source retains its own stated license. Provide the
matching corresponding-source archive alongside a distributed native binary.

The release pin is ONNX Runtime Android **1.22.0**, with its matching headers.
The newer 1.31.0 failed inside ARM64 library initialization under the tested
emulator native bridge; that failure is retained. The corrected adapter and 1.22
generated complete, non-silent Romanian Mihai, English Joe and German Thorsten
WAVs on the ARM64 guest runtime. Standalone eSpeak Romanian and cancellation also
passed. This is emulator evidence; physical-device pronunciation, speaker output
and Vivo performance remain unverified. The source archive includes exact Piper,
eSpeak, Sonic and ONNX sources, the local adapter, build scripts and patches.

`SpeechProbeActivity` exists in debug builds only. It writes diagnostic results
and WAVs below private `files/speech-probes/`. A `cancel_after_ms` intent extra
exercises real cancellation. It is excluded from release manifests.

An Android x86_64 runtime test and an ARM64 native-bridge test are different
evidence. Neither establishes physical Vivo pronunciation or performance. A model
file's presence and an ELF build alone do not establish successful synthesis.
Keep failed runtime probes when investigating a dependency-version change.
