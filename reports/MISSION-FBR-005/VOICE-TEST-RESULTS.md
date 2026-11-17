# FBR-005 Romanian Voice Recovery — verification

**Physical device status: PHYSICAL_VIVO_TESTING_NOT_AVAILABLE.** The owner's Vivo V2450 was not connected. No physical-device success or human loudspeaker-listening claim is made.

Tests used the existing dedicated `FBR_004_API37` emulator: Android 17/API 37, x86_64 guest with Android's ARM64 native bridge. Applications were installed explicitly as ARM64; Android reported `primaryCpuAbi=arm64-v8a`. Airplane mode remained enabled. App upgrades used `adb install -r`; applications were never uninstalled and their storage was never cleared.

## Frozen release artifacts

| Artifact | Version | Bytes | SHA-256 |
|---|---|---:|---|
| Free Bible Reader Ultimate ARM64 | 0.3.1-beta.1, code 301 | 446,400,281 | `ad8504f7f3caff5f58c5805de11a41547638d9e7f88a2bed1f3e731bdc2fdca8` |
| Romanian Voice Add-on ARM64 | 0.1.0, code 1 | 2,101,891 | `46952d4e87fae34ab09c94304f9d04411e46b01cb18be12f91f22ef038a0b9b8` |

Build outputs are `app/build/outputs/apk/ultimate/release/app-ultimate-release.apk` and `voice-addon/build/outputs/apk/release/voice-addon-release.apk`. Both signatures verified against the existing Android Debug development certificate, SHA-256 `d77e623706f0146bc495904affe310cb492d67277ecf70b28455d1f5e138e419`. These are non-debuggable **release variants using a development certificate**, suitable for the explicitly labeled prerelease, not production-signing claims. Debug speech probe Activities are absent from both final packages; Android returned Error type 3 when their launch was attempted.

Both packages contain only ARM64 native libraries. Ultimate retains its six public SQLite databases and three public neural voice models. The approximately 2 MB companion contains a genuine Android `TextToSpeechService`, its small eSpeak runtime/dictionaries, no Bible databases, no neural model, and no Windows binaries. Existing Lite and Windows releases were preserved.

## Baseline findings

The published Ultimate 0.3.0 did complete an audio stream in this emulator, but its saved selection was **Piper Joe / en-US while Romanian Scripture was selected**. Audio completion alone therefore did not establish correct Romanian narration. The old Lite app bound only the default Google engine and reported no Romanian voice. After the genuine Romanian companion passed an explicit framework-client test, old Lite still failed to discover it. These are measured language-selection and engine-discovery defects; they are not proof of the exact cause on the unavailable Vivo.

All three baseline ONNX model entries matched the embedded SHA-256 manifest. No model files were renamed, corrupted or replaced during recovery tests.

## Installed acceptance results

**Speech recovery: 12 passed, 0 failed.** The suite exercised the installed ARM64 debug build with the same release feature code, using DevTools only for observation and repeatable controls:

- Actual GUI selection of the companion engine and Romanian John 3:16 requested unchanged source text and `expected_language=ro`.
- Android MediaPlayer's position advanced; pause held the position, a volume change retained paused state and level, resume progressed, and completion required the native completion callback. System-mode playback did not load Piper JNI or ONNX Runtime in the reader process.
- An English voice explicitly requested for Romanian text was rejected with `VOICE_LANGUAGE_MISMATCH`.
- An **intentionally missing** preferred Piper voice failed, then the real Romanian companion synthesized and completed playback within the bounded recovery plan. This was a controlled negative test, not a reproduced Vivo crash.
- Piper Mihai completed actual Romanian playback. English Joe, German Thorsten and embedded eSpeak Romanian separately produced non-silent audio after the no-exit native repair. The English/German cases were generation checks, not claims of playback or human listening.
- Stop ended active narration without automatic replay; no unhandled WebView exception occurred.

**Reading/research regression: 8 passed, 0 failed.** English and Romanian chapter reading, Romanian search, all three source-attributed research engines, a private three-verse SQLite import/read/search, and PDF/DOCX exports passed. Exported files were independently reopened; genuine Romanian text, references and all lowercase Romanian diacritics survived.

**Restart/offline scenario: passed.** The loopback origin changed, while System mode, the companion's composite voice ID and all seven prior library IDs persisted. A new post-restart native narration completed at 5,640/5,640 ms. The Android system default setting remained unchanged (`null`); engine selection was app-local.

**Companion framework and GUI: passed.** A real Android TTS client bound the exported service, accepted the exact offline `ro-RO` voice, rejected English availability, and produced a non-silent PCM16LE WAV. Its native launcher displayed engine selection, editable Romanian test text and Test/Stop/settings controls. A real Test action finished with AudioTrack frames delivered.

**Final release GUI: passed.** Both final release APKs upgraded the existing installations successfully. The final Ultimate release read Romanian John 3:16 and displayed: `Reading finished. Voice: Android · device voices · com.freebiblereader.voice.ro.ro-RO.espeak`. The companion release logged synthesis with that exact Romanian voice. This verifies release playback completion in the emulator, not physical hearing.

The final release/native sources and APK bytes were frozen after these checks. Earlier harness-readiness/selection failures remain preserved; the accepted suite waits for enabled verse controls and validates the exact requested source text. No product patch was made merely to satisfy those harness corrections.

## Evidence and limitations

Sanitized facts are in `FBR-005-verification.json`. Local raw evidence is retained under ignored `android/evidence/fbr005/`, including baseline screenshots/logs, `recovery-acceptance/results.json`, `reader-regression/results.json`, `restart/result.json`, framework WAV receipts, final package audits and release screenshots. These files contain no public shipment of personal corpus data.

The included Romanian Bible remains a **draft Latin-script New Testament, 27 books**. No complete Romanian Bible or universal voice/device compatibility is claimed. Human listening, the physical Vivo, and every third-party Android TTS engine remain unverified. Original biblical corpus files, unrelated databases and the verified Windows installation were not modified by this Android work.
