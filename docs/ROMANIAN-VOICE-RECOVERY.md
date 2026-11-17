# Romanian voice recovery

The Android repair release is `v0.3.1-beta.1`. It updates **Ultimate** and supplies
an independently installable **Romanian Voice Add-on 0.1.0**. The add-on is a real
Android text-to-speech engine, not a model file or settings-only utility.

## Recommended recovery

1. Download and install the small **Romanian Voice Add-on** from the release.
2. Open it and press **Test**. Its one voice is Romanian, `ro-RO`, with basic
   eSpeak formant synthesis. The voice works offline and needs no Bible database.
3. Install the Ultimate update over the existing official preview. Keep the
   application installed and retain its data; do not clear storage.
4. Open the Romanian Bible and **Audio → Voice Manager**. Choose **Android system
   TTS**, select **Free Bible Reader Romanian Voice Add-on**, and choose its
   Romanian voice. Refresh the list after installing an engine if necessary.
5. Select Ioan/John 3:16 and press Play. Check media volume and the intended audio
   output. Pause, resume and stop control the app's native Android player.

Engine selection is local to Ultimate. The application does not change Android's
preferred TTS engine or system media volume. The add-on offers only Romanian;
selecting it inside Ultimate avoids changing the English voice used by other apps.

## Three modes

- **Piper · bundled voices:** uses the bundled neural models. Choose Mihai for
  Romanian. The voice must match the source text language.
- **Android system TTS:** uses an explicitly discovered installed engine and
  voice. The supplied add-on is the tested offline Romanian choice. Other engines
  appear only when installed and their voices are actually reported.
- **Automatic recovery:** tries the selected compatible voice, then compatible
  alternatives, with at most three candidates. Cancellation stops recovery. The
  interface identifies the voice that actually completes narration.

A generated WAV is not treated as completed narration. The Android player must
report completion for that playback instance. Native engine, locale, missing-data
and playback failures produce errors and recovery instructions.

## What changed

The published 0.3.0 reader could retain English Piper Joe while displaying the
Romanian edition. Its native adapter also inspected only the default system
engine, so another installed Romanian engine could remain invisible. The repair
checks source language, engine identity and voice locale; initializes clients
asynchronously; keeps system TTS independent of optional Piper initialization;
and uses native MediaPlayer playback with audio focus and cleanup.

The update reuses verified public databases and voice resources. Original Bible
texts, personal notes and imported editions are not replaced by the repair.
The Romanian bundled text remains the Latin-script draft New Testament only.

## Installation identity and preservation

- Ultimate: `com.freebiblereader.ultimate`, version `0.3.1-beta.1`, code 301.
- Add-on: `com.freebiblereader.voice.ro`, version `0.1.0`.
- Ultimate retains its existing ID. Lite remains `com.freebiblereader.lite`.
- Both new APKs use the existing Android Debug development certificate. These
  are testing/prerelease packages, not production-signed or Play Store releases.

The certificate matches the previously published official Ultimate APK. An
unseen phone's installation cannot be inspected when disconnected. If Android
rejects an update for signature mismatch, **do not uninstall or clear storage to
bypass it**. Keep the current installation and export important libraries/notes
before any separately planned migration.

Older Lite/Ultimate clients inspect the default engine only. Installing the add-on
alone does not prove those old clients will discover it. Their use may require
the user to choose a preferred engine in Android settings and restart the app.
The repaired Ultimate can select the add-on directly without that global change.

## Evidence and limitations

The physical Vivo V2450 was not connected: **PHYSICAL_VIVO_TESTING_NOT_AVAILABLE**.
Its precise failure, Android version, memory state and speaker output could not be
measured. The confirmed wrong-language/default-engine defects were reproduced
in the existing Android emulator. They are not asserted to be the owner's exact
phone-specific cause.

Actual ARM64 code runs through the API 37 x86_64 emulator's native bridge. The
tested paths include a real Android TTS service, Romanian PCM, native player
progress/completion, pause/resume/stop, bounded fallback and offline restart.
No physical-phone or human listening certification is claimed. Read the release's
test results and known limitations for the exact final artifact scope.

## Source and optional engines

First-party changes and the complete add-on source are in the release Git tag.
The small speech source supplement explicitly requires the unchanged full native
source archive from v0.3.0-beta.1; its manifest provides the exact URL and SHA-256.
It is a source supplement, not a voice installer.

Optional upstream installation links are supplied in the release. RHVoice,
eSpeak NG or SherpaTTS need an actually installed compatible Romanian voice; no
third-party APK is renamed or bundled by this repair. One working engine is enough.
