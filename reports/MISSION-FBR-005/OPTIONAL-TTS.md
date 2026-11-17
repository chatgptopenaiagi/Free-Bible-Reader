# Optional Android TTS engines

One working Romanian engine is enough. The small Free Bible Reader Romanian Voice Add-on is the tested offline option supplied with this repair. It is an independent basic eSpeak engine, not the neural Mihai voice. Installing it does not change the global Android default.

Other Android engines can be selected by package and voice in Ultimate when they actually report a compatible installed Romanian voice. No third-party APK is renamed, modified or bundled in this release. The following primary upstream pages were inspected on 2026-11-17:

- **RHVoice:** [official binaries and Android links](https://github.com/RHVoice/RHVoice/blob/master/doc/en/Binaries.md). Romanian voice availability was not established on a tested RHVoice installation; do not assume installing the engine supplies Romanian.
- **eSpeak NG:** [official releases](https://github.com/espeak-ng/espeak-ng/releases) and [Android build/install documentation](https://github.com/espeak-ng/espeak-ng/blob/master/docs/building.md). Use an Android package distributed by its upstream channels, not a desktop binary.
- **SherpaTTS:** [official project](https://github.com/woheller69/ttsEngine) and [releases](https://github.com/woheller69/ttsEngine/releases). Its own model manager supports offline use after installation. Its documented custom Piper format requires converted models and tokens; the reader's raw model/config pair is not automatically interchangeable.

These are upstream installation links, not claims of physical Vivo verification, redistribution permission for every voice, or a requirement to install all engines. Use the engine's own voice installer and then refresh Ultimate's Voice Manager. Missing Romanian data must be reported rather than silently replaced by English.

Android API references used for this implementation: [TextToSpeech](https://developer.android.com/reference/android/speech/tts/TextToSpeech) and [TextToSpeechService](https://developer.android.com/reference/android/speech/tts/TextToSpeechService). Actual installed-app tests, rather than the existence of these APIs, establish the supplied add-on's runtime capability.
