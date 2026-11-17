# FBR-005 verified build and delivery

The focused repair provides Ultimate 0.3.1-beta.1 and the independent Romanian Voice Add-on 0.1.0. The add-on is a genuine offline Android TextToSpeechService using basic Romanian eSpeak synthesis. It is not merely a settings utility.

Confirmed defects were a saved English voice retained for Romanian Scripture and default-only engine discovery. The exact cause reported on the physical Vivo remains unconfirmed. The repair adds explicit per-engine discovery, strict language checks, independent Android system speech, native playback completion and bounded recovery. Piper Mihai remains included and passed Romanian playback on the tested runtime.

Speech acceptance: **12 passed, 0 failed**. Reading/research/import/document acceptance: **8 passed, 0 failed**. Adapter/policy tests: **16 passed**. Voice-selection/localization tests: **13 passed**. Restart, offline native completion and both final release installations passed. All three research engines and six public databases remain present. Seven previous personal library identifiers survived the upgrade/restart tests.

The test environment was Android API37 in the existing x86_64 emulator running the APKs' ARM64 code through Android's native bridge. **PHYSICAL_VIVO_TESTING_NOT_AVAILABLE**. No human loudspeaker-listening or pronunciation judgment is claimed. English/German regression checks establish audio generation only.

| Package | Bytes | SHA-256 |
|---|---:|---|
| Ultimate 0.3.1-beta.1 ARM64 | 446400281 | ad8504f7f3caff5f58c5805de11a41547638d9e7f88a2bed1f3e731bdc2fdca8 |
| Romanian Voice Add-on 0.1.0 ARM64 | 2101891 | 46952d4e87fae34ab09c94304f9d04411e46b01cb18be12f91f22ef038a0b9b8 |

Both are non-debuggable release variants signed with the existing development certificate. Ultimate retains com.freebiblereader.ultimate; the add-on uses com.freebiblereader.voice.ro. The certificate matches the previously published Ultimate preview. No uninstall, storage clear, global TTS default change or private corpus inclusion was used.

Use the release's INSTALLATION.md and KNOWN-LIMITATIONS.md. The release asset manifest identifies the exact source commit and checksums; independent public-download results are retained with the local delivery evidence. The speech source supplement requires the explicitly linked, unchanged full native source archive from v0.3.0-beta.1. Windows, Python and Lite releases are preserved.

Release: https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/tag/v0.3.1-beta.1
