# Free Bible Reader Android 0.3.0 prerelease verification

Two distinct Android applications were built and installed: `com.freebiblereader.lite` and `com.freebiblereader.ultimate`. They coexist with separate private storage, names, icons and interfaces. The final APKs are ARM64 Android packages, not Windows executables. Both are **release build variants signed with the development Android Debug certificate**. They are not production-signed or Google Play releases.

## Final artifacts

| App | APK bytes | SHA-256 |
|---|---:|---|
| Lite | 39,545,760 | `51673b0928ae5b85275cc153a9d25d26dcbdf2b10408baea66b2b2e5791d184b` |
| Ultimate | 446,393,687 | `84cb59e763fcb68cfa60c8bbce0321f2aafdddcb90bc3a3e67da0f5b6e9f170f` |

Local build paths are `app/build/outputs/apk/lite/release/app-lite-release.apk` and `app/build/outputs/apk/ultimate/release/app-ultimate-release.apk`. Root delivery tooling supplies the public filenames. Version name is 0.3.0, version code 300, minimum Android API 26, target API 36. APK signature verification passed. Certificate SHA-256: `d77e623706f0146bc495904affe310cb492d67277ecf70b28455d1f5e138e419`.

The final release applications are not debuggable. The debug speech probe Activity is absent; an explicit attempt to launch it returned Android Error type 3. Test-only `native_operation` and `poc` branches are guarded by `BuildConfig.DEBUG`. Runtime WebView debugging is disabled in release builds.

## Actual runtime and scope

Tests used a dedicated Android 17/API 37 Google Play x86_64 emulator on Windows. Its installed native bridge reports ARM64 support. APKs were installed with `adb install --abi arm64-v8a`; Android reports `primaryCpuAbi=arm64-v8a`, and the embedded Python reports `aarch64-unknown-linux-android`. This establishes actual ARM64 translation execution, not physical Vivo verification or a native ARM64 host. The emulator was in airplane mode for offline tests. No physical phone was connected.

The final release APKs both installed successfully and opened real reading interfaces. Final Lite screenshots show retained Romanian Bible, Romanian UI, dark theme and reading preferences following update from the tested debug build. Final Ultimate screenshots show its separate research-studio identity and real Romanian John 1. Native system-bar insets were corrected and visually inspected. Android Back closed the foreground reader Activity and returned to the previous Activity. Full functional tests below used the corresponding installed ARM64 debug builds, allowing DevTools inspection; release builds use the same Python/UI/native feature code with debug test surfaces removed.

## Functional evidence

| Installed Android check | Result |
|---|---|
| Lite essential suite | 8/8 passed: startup, English John 3 all 36 verses, next/previous chapters, Romanian John 3 and diacritics, 27-book draft-NT notice, search-result navigation, bookmark/customization, persistence after quit/reopen with a different random loopback origin, no unhandled JavaScript exceptions. |
| Ultimate essential suite | 8/8 passed: distinct startup, English/Romanian chapter reading, all three offline research engines, bundled voice catalog, Romanian search, private SQLite import/read/search, PDF/DOCX exports, no unhandled JavaScript exceptions. |
| Research | John 1:1 returned five meaningful source-attributed results from each of A, B and C in the bounded query. This does not imply identical coverage or theological equivalence. |
| Personal import | A private verification SQLite file containing three unchanged public Romanian NT verses was inspected, previewed, confirmed and imported. All three records reopened correctly; imported text search returned results. The fixture remains outside public assets. |
| Documents | Real Romanian John 3:16 exported through the installed Android HTTP/native renderer. Downloaded PDF and DOCX reopened independently with pypdf and python-docx. Source text, reference and Romanian diacritics were preserved. PDF text is selectable; DOCX is editable OpenXML. |
| Piper ARM64 | Romanian Mihai, English Joe and German Thorsten generated non-silent offline WAVs. Final chunks were consumed. Romanian: 4.957 s, RMS 1885; English: 4.679 s, RMS 1400; German: 3.216 s, RMS 1806. German used an explicitly non-scriptural voice-test sentence. |
| eSpeak ARM64 | Romanian John 3:16 generated a 9.768-second non-silent WAV, RMS 2572. |
| Cancellation | A long genuine-text narration test returned CANCELLED. Continuous chapter playback and a physical loudspeaker listening check were not included in the compact final suite. |

Windows-native TTS was not copied to Android. Android voices are discovered through the platform API and labeled by their actual network requirements. Native voice enumeration is not proof that every enumerated voice synthesizes correctly; local Piper/eSpeak generation above provides the verified offline voice path for Ultimate.

Initial test harness errors used `status` instead of the existing job `state`, and `id` instead of the document `artifact_id`. Their failed receipts were retained, then the harness was corrected; no product change was needed for those assertions. Earlier actual native issues are recorded in `RESUME-CHECKPOINT.md`: initial ONNX 1.31 ARM64 native-bridge initialization failure, repaired with matching ONNX 1.22; and a final Piper chunk consumption defect, repaired before the successful tests.

## Bundled resources and privacy

Lite contains the two public reading SQLite databases: reader.sqlite and romanian.sqlite, representing WEB, KJV, BSB and the Romanian draft New Testament. Curated public resource payload: 37,614,346 bytes before APK compression. It does not contain research databases or neural voice models.

Ultimate contains six public SQLite databases, all three research engines, three pinned public Piper models, matching eSpeak dictionaries and notices. The main curated resources total approximately 935 MB before compression; the separately verified speech resource set is 220,566,461 bytes. APK inspection confirmed all six SQLite files and all three ONNX model files. Both APKs contain only ARM64 native libraries and no Windows EXE, DLL or MSI files. Installed disk consumption was not independently measured; compressed APK size is not an installed-storage claim.

No original personal corpus, private notes, credentials or downloaded personal model cache was bundled. Existing Windows 0.2.0 installation and release artifacts were not modified by Android work. Public resource staging uses explicit allowlists and SHA-256 manifests.

## Remaining limits

- No physical Vivo/device compatibility or battery/performance claim.
- No production signing, Play Store validation or AAB delivery.
- Android SAF import/Save As/Share adapters are implemented; their complete native-dialog journeys were not part of the compact final acceptance suite. SQLite import and actual document generation/download were tested independently.
- Offline neural synthesis is verified; continuous playback, every native device voice and long-session narration remain broader testing work.
- Existing reference compatibility limitations remain visible. A reference match does not assert cross-edition text equivalence.
- The Romanian included edition remains a Latin-script **draft New Testament, 27 books**, not a complete Romanian Bible.

## Rebuilding

Use JDK 21, Gradle 9.3.1, Android SDK 36/build-tools 36.0.0, existing NDK 28.2.13676358 and CMake 3.22.1. No Windows runtime is used by the APK. Set `JAVA_HOME` and optionally `GRADLE_HOME`; `gradlew.bat` first respects that Gradle installation, then its verified local fallback. Set `FBR_BUILD_PYTHON` or Gradle `-PbuildPython=<path>` to a Python 3.14 executable. The current machine's verified Python path is only a fallback.

Stage allowlisted public resources with `tools/stage_android_assets.py all`, prepare speech dependencies using the pinned speech tooling, then run from android:

```powershell
.\gradlew.bat :app:assembleLiteRelease :app:assembleUltimateRelease '-PtargetAbi=arm64-v8a' '-PspeechOrtVersion=1.22.0' --console=plain
```

Local raw evidence is retained in `android/evidence/`; it is excluded from public Git candidates. Sanitized package facts are in `verification.json`. No commit or publication was performed by the Android runtime agent.
