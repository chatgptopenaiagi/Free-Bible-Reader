#pragma once
// Synchronous PCM-only eSpeak. No playback driver, Piper, ONNX or Sonic.
#define HAVE_MKSTEMP 0
#define USE_ASYNC 0
#define USE_KLATT 1
#define USE_LIBPCAUDIO 0
#define USE_LIBSONIC 0
#define USE_MBROLA 0
#define USE_SPEECHPLAYER 0
#define PACKAGE_VERSION "1.53.0-fbr-ro"
