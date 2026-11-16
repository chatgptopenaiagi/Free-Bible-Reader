# Offline speech components and source provenance

The application's own license does not replace the licenses of its bundled speech components. Piper and eSpeak NG retain **GPL-3.0-or-later** terms, their original notices and the accompanying COPYING files. Other bundled dependencies retain their own licenses. This document identifies the actual components and source versions; it is not a claim that the entire distributed bundle is MIT licensed.

## Piper

Piper **1.8.0** comes from [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl/releases/tag/v1.8.0). The Windows CPython ABI3 wheel SHA-256 is `5da9bfdb05dfe15da3536859d422e605483ffa6d2b3ec2c5b9593bae6b5aa6a4`. Installation used that pinned publisher digest. [Original license](PIPER-COPYING.txt), [upstream licensing documentation](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/docs/LICENSING.md).

The repository source archive is retained rather than relying only on the Python source distribution, which omitted native bridge build inputs. Piper's v1.8.0 CMake configuration uses eSpeak NG commit **724808c5a83f9ef95fdd0db886ba7ba537ff224a** for its embedded phonemizer; that exact source archive is also included in the staged source bundle. It is a different component version from the standalone eSpeak engine below.

## Standalone eSpeak NG

The standalone **1.52.0** runtime was obtained from the [official Windows MSI release](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0), SHA-256 `7f673c709ea5dd579d3b5ebb98688cc575328a6ab7438d2bc405b88cedaeafb9`. Existing 7-Zip statically extracted its CAB; read-only MSI File/Component/Directory tables supplied the destination mapping. No installer actions or global registration were performed. Its actual DLL reports 1.52.0, although the upstream MSI ProductVersion property says 1.51.0. [Original license](ESPEAK-NG-COPYING.txt).

The official asset supplied no publisher checksum and is unsigned; its recorded acquisition rests on the canonical HTTPS project release and observed bytes. The installed runtime manifest records every extracted file hash. The upstream CLI's `--version` command crashed in the observed Windows environment; version discovery instead used `espeak_Info` with a valid output pointer. Actual voice enumeration and Romanian WAV synthesis succeeded. No binary patch or substituted unofficial runtime was used.

## Source archive delivery

The staged release source asset is named **Free-Bible-Reader-0.2.0-tts-sources.zip**. [TTS-SOURCES.json](TTS-SOURCES.json) gives canonical upstream URLs, revisions, sizes and SHA-256 values for the three source archives and the staged ZIP. It also distinguishes staged delivery from actual publication. The ZIP includes the relevant original COPYING files and verifies its embedded source-archive bytes. No personal files, voice recordings or downloaded user voice models are included.

These are upstream source archives for the redistributed components, plus the published application adapters. The upstream wheel/MSI binaries were functionally tested; no independently reproduced, byte-identical upstream source build is claimed.

## Inference dependencies and build

The verified Windows inference stack is Piper 1.8.0, ONNX Runtime 1.32.0, NumPy 2.5.5, pathvalidate 3.3.1, protobuf 7.36.2, flatbuffers 25.12.19 and packaging 26.3. [requirements-tts.txt](../requirements-tts.txt) pins all seven wheel hashes, including transitive requirements in an otherwise empty environment. No training, GPU, Torch or TensorFlow package is required.

PyInstaller packaging collects `piper`, `onnxruntime` and `numpy`, preserves their package data and metadata, and includes the application `studio` assets and standalone eSpeak runtime. An independent frozen worker passed real Romanian CPU synthesis with only Windows directories in its child PATH and an external managed model. The final application installer and GUI are verified separately.

## Downloaded voices

Piper voice models are **not bundled in the application installer**. The managed voice manifest pins the Romanian Mihai, English Joe and German Thorsten medium models to repository revision **e9ab671f2a0e50a701b34361136ba3e6a3a9eb0c**, with model/config/model-card size and SHA-256 checks. Their selected model cards identify CC0 dataset/base declarations; the Piper engine license does not itself grant rights to arbitrary other voice models. The individual pinned model cards accompany each download. Models remain under the user's separate local studio voice directory.

Windows SAPI and Windows.Media voices are provided by Windows and are discovered at runtime. They are not redistributed by this application; installing or removing them remains a Windows settings operation.
