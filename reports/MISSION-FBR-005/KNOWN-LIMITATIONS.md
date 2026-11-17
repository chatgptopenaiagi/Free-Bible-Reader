# Known limitations

- PHYSICAL_VIVO_TESTING_NOT_AVAILABLE. No Vivo Android version, on-device crash/memory evidence, installed certificate, speaker output or physical voice availability was measured. The precise phone-specific cause remains unconfirmed.
- Confirmed software defects were reproduced: English Joe retained for Romanian text and default-only Android engine discovery. The repair was tested through actual Android narration completion, not inferred solely from a model file or WAV.
- Actual ARM64 application code ran through the API37 x86_64 emulator's native bridge. This is not a physical Vivo or native ARM64-host certification.
- No human loudspeaker/pronunciation assessment. Digital PCM, native playback progress and completion were verified. English/German regression checks covered generation, not human listening.
- The Romanian add-on is reliable basic eSpeak formant speech, not the neural Mihai voice. It advertises Romanian only and rejects English requests.
- Other installed Android engines can be selected, but RHVoice, SherpaTTS and every device voice were not individually tested. Missing Romanian data must be installed through their own interfaces; no silent English substitute is accepted.
- Android's public TTS API identifies the explicitly requested engine and returned voice/locale; it does not expose process attestation. The add-on's unique voice name and real cross-app tests establish that tested path.
- Both APKs use the existing development certificate; no production signing or Play Store claim. If a phone installation has another certificate, preserve its data and do not force uninstall.
- The included Romanian Bible remains the Latin-script draft New Testament only. Biblical texts, reference semantics and source databases were not changed.
- Existing Lite and Python/Windows packages are not rebuilt by this release. Personal corpus and owner phone storage were not imported or cleared.
