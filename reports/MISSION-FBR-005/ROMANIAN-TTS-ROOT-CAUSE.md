# Romanian speech recovery — evidence and root cause

## Owner report and physical-device status

The owner reports Romanian narration failure on a Vivo V2450. No physical Android device was connected during initial ADB discovery: **PHYSICAL_VIVO_TESTING_NOT_AVAILABLE**. Android version, on-device voice data, memory-pressure events and crash logs could not be inspected. The exact Vivo-specific failure is therefore not established.

## Confirmed defects in published 0.3.0

1. **Wrong-language saved voice retained.** On the unmodified installed Ultimate APK, the Romanian `ronbl` edition was selected while the player retained Piper Joe `en-US`. Playback produced digital AudioTrack frames and finished, but that was not evidence of a correct Romanian voice. The existing chooser accepted an installed saved voice before checking the source language.
2. **Only the default Android TTS engine was inspected.** Old Lite reported no Romanian voice even after the new independent Romanian TTS service was installed and a real Android framework client successfully used it. The old reader remained bound to Google only. Installing a second engine alone did not make it visible to that client.
3. **Source-confirmed lifecycle and validation weaknesses.** A shared initialization latch was not reset on Activity recreation; voice identifiers lacked engine identity; selected language and `setVoice` results were not adequately validated. These are source-confirmed defects, not proof of the owner's exact phone error.
4. **Optional native runtime loaded during catalog discovery.** Merely opening the voice catalog could load Piper/ONNX and inspect eSpeak natively, coupling the independent Android system path to optional JNI initialization.

## Evidence against unsupported explanations

All three bundled model hashes match the published manifests. The eleven bundled ARM64 shared libraries have ELF LOAD alignment of at least 16 KiB. No missing model, ABI mismatch or 16-KiB alignment fault was reproduced in the baseline APK. No physical Vivo memory-kill or crash evidence is available. These possibilities are not presented as established causes.

## Focused repair

- Match the voice to the language of actual source text, independently of interface language; reject English Joe for Romanian.
- Discover installed Android engine packages and enumerate engine-specific voices with composite identities. Initialize clients asynchronously, verify selected voice/locale, report missing Romanian data and leave system defaults unchanged.
- Offer bundled Piper, Android system TTS and automatic recovery. Recovery tries at most three compatible same-language candidates and reports the engine that actually completed narration. Cancellation never initiates fallback.
- Use a native Android MediaPlayer with speech/media audio attributes, audio focus, pause/resume/stop and actual completion tracking; generating a WAV alone is not counted as completed narration.
- Discover bundled resources without loading optional native libraries. Load JNI only when its provider is used. Avoid eSpeak process exit on initialization errors via the explicit no-exit option.
- Provide an independent small eSpeak-only Romanian TextToSpeechService, without Piper, ONNX, Python, Bible databases or network permission.
- Reuse verified immutable reading resources across a speech-only update; preserve separate personal libraries and preferences.

Final runtime results, release signatures and limitations are reported separately. No human loudspeaker listening or physical Vivo success is inferred from PCM files, callbacks or AudioTrack frame delivery.
