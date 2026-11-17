# Romanian voice companion verification

The companion implements a genuine Android `TextToSpeechService`, not merely a
diagnostics shortcut. Its small, independent engine provides one basic offline
Romanian voice. The framework-service and native-screen checks below passed on
the available Android emulator; physical phone and audible pronunciation checks
are not claimed.

| Identity | Actual value |
| --- | --- |
| Application | Free Bible Reader Romanian Voice Add-on |
| Package | `com.freebiblereader.voice.ro` |
| Version / code | `0.1.0` / `1` |
| Voice | `com.freebiblereader.voice.ro.ro-RO.espeak` |
| Locale / network | `ro-RO` / not required |
| Native engine | eSpeak NG; no Piper or ONNX dependency |
| Bundled data | 12 files, 1,035,306 bytes, plus manifest |
| Signing | Existing Android Debug development certificate |

## Exact artifacts

The final debug APK is **3,582,193 bytes**, SHA-256
`5dd506ab1adea904b64017d72671fc04936c9fb6781f481d9997d7be28e02297`.
The installed APK was pulled back and matched that hash. Android reported
`primaryCpuAbi=arm64-v8a`, debuggable true, version 0.1.0/code 1. This binds the
following debug-client and native-screen results to the actual installed file.

The release APK is **2,101,891 bytes**, SHA-256
`46952d4e87fae34ab09c94304f9d04411e46b01cb18be12f91f22ef038a0b9b8`.
Its native library inventory is ARM64 only. Static manifest inspection confirms
the debug probe is absent. It contains no SQLite databases, neural voice models
or Windows binaries. Release installation and runtime checks must be recorded
separately; a debug-client result is not labeled a release-installation result.

## Real Android framework synthesis

The debug probe used an ordinary `TextToSpeech` client, explicitly selected the
companion engine and exact voice, and invoked `synthesizeToFile`. Android bound
the exported service, which streamed PCM through `SynthesisCallback`; the
framework wrote the WAV. This was not a direct JNI-only synthesis test.

| Check | Result |
| --- | --- |
| Romanian availability | `1` (`LANG_COUNTRY_AVAILABLE`) |
| English availability | `-2` (`LANG_NOT_SUPPORTED`) |
| Voice returned | Exact named offline `ro-RO` voice |
| Test input | 89 Unicode characters; hash retained in the receipt |
| WAV | 298,590 bytes; PCM16LE, mono, 22,050 Hz |
| Audio samples | 149,273; 6.769750566893424 seconds |
| Digital audio | Nonzero samples, peak 25,784, RMS 2,567.6903 |
| WAV SHA-256 | `56e692b9172bb9ff091ba32803f70ecaeae4ddc098a2abac6c4e7fb0665ebe01` |
| System default TTS setting | Unchanged: null before and after |

The final rebuild includes an explicit error when the bounded audio-duration
budget is exceeded. It does not silently present a budget-truncated request as
completed speech. The short final framework probe passed after that source fix
and the final branding change. An actual maximum-duration stress test was not
performed.

## Native screen

The installed screen displayed the engine selector, exact Romanian offline voice,
editable Romanian text, readiness status, Test Romanian, Stop and voice-settings
controls. The actual Test Romanian button was tapped; its status reached
“Test finished” and AudioTrack reported delivered frames. The app did not change
the system's default engine. No owner app data was cleared.

Evidence is retained locally under `android/evidence/fbr005/`:
`addon-final-framework.json`, its WAV, `addon-ui.png`, `addon-after.png`, and the
native playback log. These emulator observations establish scoped digital
functionality. They do not establish physical Vivo compatibility, physical
speaker output or human judgment of Romanian pronunciation.

The independent reader integration must also select this engine explicitly and
check voice/locale readback; those checks belong to the reader's integration
receipt. The companion does not alter the reader's databases, models or private
research material.
