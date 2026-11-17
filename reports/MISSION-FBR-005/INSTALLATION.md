# Install the Romanian speech repair

## Recommended route for Vivo and other ARM64 Android phones

1. Install `Free-Bible-Reader-Romanian-Voice-Addon-0.1.0-arm64.apk` (about2.1MB). Open it and press Test to check its basic Romanian voice. It is a real offline Android TTS engine, independent of Piper.
2. Update the official Ultimate app with `Free-Bible-Reader-ULTIMATE-0.3.1-beta.1-arm64.apk`. Keep the existing app installed; do not clear storage.
3. Open the Romanian edition, select Ioan/John3 and verse16 using the verse-number control.
4. Open Audio → Voice Manager. Choose Android system TTS, then Free Bible Reader Romanian Voice Add-on and its ro-RO voice.
5. Press Play. Check media volume and the intended audio output. The player supports pause, resume, stop and speaking speed.

Piper mode uses bundled Mihai for Romanian. Automatic recovery tries at most three compatible voices and identifies the engine that completed narration. Android system mode does not load optional Piper/ONNX libraries.

The application does not change Android's preferred TTS engine or system volume. The add-on offers Romanian only. Select it inside Ultimate rather than changing other apps' English voices globally. After installing an engine, refresh Voice Manager or restart Ultimate if needed.

## Upgrade identity

- Ultimate: com.freebiblereader.ultimate, version0.3.1-beta.1/code301.
- Add-on: com.freebiblereader.voice.ro, version0.1.0/code1.
- Android minimum API26/8.0, ARM64. Both release variants are non-debuggable but use the existing Android Debug development certificate, SHA256 d77e623706f0146bc495904affe310cb492d67277ecf70b28455d1f5e138e419.

Signatures match the previously published official Ultimate preview. On an unseen phone this cannot be inspected remotely. If Android reports a signing mismatch, do not uninstall or erase data to force an upgrade. Keep the old app and export important notes/libraries before a separately planned migration.

These are development-signed testing/prerelease APKs, not Play Store/production-signed packages. They were installed and exercised on an Android emulator using ARM64 translation. PHYSICAL_VIVO_TESTING_NOT_AVAILABLE: the Vivo was not connected. No physical success is claimed.

## Existing products

Lite, Windowsv0.2.0, Pythonv0.3.0 and the old0.3.0-beta.1 release remain available unchanged. Older Lite inspects only the system default engine; installing a second engine alone does not make it visible there. Any Android global preferred-engine change must be made by the user.

## Integrity and source

Compare downloaded files with SHA256SUMS.txt or PACKAGE-MANIFEST.json. Source is supplied by the release Git tag and a small speech-source supplement. The supplement explicitly requires the unchanged full native source archive fromv0.3.0-beta.1; it is not itself a complete standalone native source archive or a voice installer. No personal Bible data, notes, private keys or phone logs are included.
