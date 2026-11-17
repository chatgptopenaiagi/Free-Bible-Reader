# Romanian offline voice companion

This module is an independent Android `TextToSpeechService` plus a native
diagnostics screen. It contains one basic eSpeak NG Romanian voice and no Bible
database, Python interpreter, Piper engine, ONNX runtime or neural model.

- Application ID: `com.freebiblereader.voice.ro`
- Version: `0.1.0`
- Exact voice name: `com.freebiblereader.voice.ro.ro-RO.espeak`
- Locale: `ro-RO`; network required: **false**
- Quality: basic formant synthesis, distinct from the Piper Mihai neural voice.

The service advertises only Romanian and rejects unsupported languages or voice
names. English dictionary/bootstrap data does not add an advertised English
voice. Android clients must select this engine explicitly and verify the returned
voice and locale. Installing this app does not change Android's default TTS engine.

The native screen lists installed engines, inspects their reported Romanian
voices, previews editable Romanian text, changes preview speed, stops playback
and opens Android voice settings. No account or network permission is required.
It never silently speaks an English fallback when Romanian is missing.

## Source and assets

The standalone JNI target builds only eSpeak NG and its Unicode tables from the
already prepared pristine source, revision
`699e79690f23e2558d990a3a78b0050745b96932`. It does not link the separate reader
speech module. Synthesis is synchronous PCM16; stop invalidates the owned request
token and the next native callback stops sending audio.

Run `prepare_assets.py` using the existing project build Python before compiling
`:voice-addon:assembleDebug` or `:voice-addon:assembleRelease`. The stager verifies
the pinned upstream checkout and compiled-data hashes, then copies only eight
common/Romanian/bootstrap data files plus upstream notices to ignored
`build-support/android-assets/voice-addon`. Its initial measured resource payload
is 1,035,306 bytes across 12 files, before the small manifest. APK and installed
sizes must be measured from the actual build.

The existing Android toolchain is SDK 36, NDK 28.2.13676358, CMake 3.22.1 and
JDK 21. `-PtargetAbi=arm64-v8a` selects an ARM64 build. Other supported ABIs may
be supplied explicitly for emulation. Release builds currently use the existing
Android development signer; they are not production-signed Play Store packages.

## Verification contract

The debug-only `VoiceProbeActivity` is an ordinary Android TTS client. It calls
the exported service through Android, selects and reads back the exact offline
Romanian voice, checks that English is unsupported, and asks the framework to
write a WAV. It validates RIFF/PCM16, sample rate, duration and nonzero samples.
This exercises the complete service path rather than a direct JNI test.

```text
adb shell am start -n com.freebiblereader.voice.ro/.VoiceProbeActivity --es test_id romanian-service
adb shell run-as com.freebiblereader.voice.ro cat files/native-tests/romanian-service.json
```

The probe accepts a bounded `text` extra and optional `cancel_after_ms`. It writes
only to its app-private test directory. The activity is excluded from release
APKs. Digital audio success does not establish physical speaker output or a human
assessment of Romanian pronunciation. Verification results belong to the actual
built package, device or emulator, and signing configuration.

Implementation follows Android's documented
[TextToSpeechService](https://developer.android.com/reference/android/speech/tts/TextToSpeechService)
and [SynthesisCallback](https://developer.android.com/reference/android/speech/tts/SynthesisCallback)
contracts: audio is delivered on the synthesis thread, in bounded buffers, with
completion/error reporting. eSpeak NG and its data retain their GPL and other
upstream notices. First-party adapter source and corresponding eSpeak sources
must accompany distribution according to those terms.

Scoped compilation, installed debug-service synthesis and native-screen results
are recorded in [VERIFICATION.md](VERIFICATION.md). The final release artifact's
runtime checks are distinguished from those debug-client results. Physical
speaker and physical-device assessment remain separate.
