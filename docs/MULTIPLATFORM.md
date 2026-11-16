# FREE BIBLE READER 0.3.0 multiplatform preview

This first Android/Python delivery preserves the Windows v0.2.0 product. It does
not promise feature parity between the two Android apps, Windows and the CLI.
The GitHub prerelease is `v0.3.0-beta.1`; package version strings are `0.3.0`.

## Choose a product

| Product | Purpose | Offline content | Runtime |
|---|---|---|---|
| Android Lite | Comfortable reading, navigation, search, bookmarks | WEB, KJV, BSB and Biblia Liberă draft NT | Embedded Python core, Android WebView, device TTS when available |
| Android Ultimate | Reading, research, personal library and documents | Lite texts plus visual, aggregate, phrase and reference databases; Romanian/English/German voice resources | Embedded Python core with native Android storage, PDF/DOCX and speech adapters |
| Python wheel | Reusable services and CLI | All six public databases; no private corpus or neural voice weights | Python 3.11+, tested with Python 3.14 on Windows and Linux |
| Windows v0.2.0 | Existing installed desktop studio | Existing verified Windows release | Standalone Windows installer; unchanged by this delivery |

The applications preserve original wording and edition-specific identifiers.
Biblia Liberă is a Latin-script Romanian **draft New Testament**: 27 books,
260 chapters and 7,958 source text units. No Romanian Old Testament is bundled.
The three English editions each have 66 books. The datasets' native verse counts
and mappings are retained, rather than fabricated to agree across editions.

## Install Android

1. Download the **ARM64** Lite or Ultimate APK from the prerelease. Compare its
   SHA-256 with `SHA256SUMS.txt` if desired.
2. Open the APK on an Android 8.0 / API 26 or newer ARM64 device. Permit installation
   from the file manager/browser only when Android asks for that specific source.
3. Launch the app and allow first-use integrity verification and extraction to
   finish. Ultimate needs substantially more free space and takes longer.
4. Select an edition, book and chapter. Basic reading requires no account, PC,
   XAMPP, external Python installation or internet connection.

Both apps can coexist: `com.freebiblereader.lite` and
`com.freebiblereader.ultimate`. Their icons, resource bundles, interfaces and
private storage differ. Lite does not contain the large research or neural voice
bundle. Ultimate carries those public assets inside its own package.

These APKs use the Android development certificate. They are suitable for
explicit sideload testing and are not production-signed or Play Store builds.
A later production certificate can require uninstalling this preview first;
export important personal work before uninstalling any app. Android uninstall
normally removes that app's private data.

The test device is an Android API 37 x86_64 emulator with ARM64 native translation.
The installed APK's actual primary ABI is ARM64. No physical Vivo test or general
Android hardware certification is claimed. Device-native voices vary: the app
lists voices it actually discovers and distinguishes network-dependent voices.

## Read and study

Lite opens directly into Scripture. Change the edition/book/chapter using the
top controls, select a verse, search from the bottom bar, and bookmark a passage.
Appearance and language live under the settings button. Interface language and
Bible language are independent. SharedPreferences preserves reading/UI settings
even though the app's private loopback port changes after restart.

Ultimate retains the study menus and adds Android navigation for Bible, research,
library, documents and audio. Choose **Audio → Voice Manager** to inspect native
voices and bundled Piper/eSpeak providers. Narration uses the selected edition's
text. PDF contains selectable text; DOCX is editable OpenXML, not a screenshot.
Save and import actions use Android's document picker; sharing uses Android's
Share Sheet. Native Windows SQL Server authentication is unavailable on Android;
use a compatible SQLite/CSV/JSON/SQL export instead.

Cross-references retain source, direction, weight and translation/phrase mapping
limitations. A link is a dataset assertion, not proof that two verses or editions
are equivalent. Android/Python use the documented bounded portable reference
parser; the full upstream Node parser remains available in the Windows product.

## Install Python from the downloaded wheel

```sh
python -m venv fbr-env
# Windows: fbr-env\Scripts\activate
# Linux/macOS: . fbr-env/bin/activate
python -m pip install ./free_bible_reader-0.3.0-py3-none-any.whl
fbr --help
fbr catalog
fbr read "John 3:16" --edition ronbl
fbr read --help
fbr search "Dumnezeu" --edition ronbl --limit 5
fbr serve
```

Use the actual CLI help for command arguments. The wheel's code/data are portable;
the user's Python interpreter, SQLite build and optional dependencies remain
platform-specific. Optional document export:

```sh
python -m pip install './free_bible_reader-0.3.0-py3-none-any.whl[documents]'
fbr export --edition ronbl --reference "John 3" --format docx --output study.docx
```

Python's local server binds only to `127.0.0.1`; it is not an Android remote-server
requirement. Personal libraries live outside the installed package. The wheel
contains no Windows executable, native Android binary, private corpus, personal
notes or neural voice model. Linux was tested in an isolated Docker Python
environment; macOS has not been tested.

## Private libraries and the optional personal corpus

Import only databases you choose. Preview the schema, map actual columns, select
an edition, confirm import and inspect its measured coverage. The original source
is not overwritten. Private copies, notes and downloaded datasets stay local.
Do not upload them to the public repository or release.

`tools/build_personal_android_library.py` creates an explicitly private selected
edition package or complete-source ZIP under ignored `build-support/private-corpus`.
It does not add the corpus to a public APK. A complete private corpus pack can be
transferred offline and selected in Ultimate's library importer. This is an
optional workflow, not a claim that a full multi-gigabyte import was tested on a
physical phone. See its `--help`; never copy private output into Git history.

## Verification and limitations

Release assets include `VERIFIED-FEATURES.md`, `KNOWN-LIMITATIONS.md` and checksums
with the actual final build results. Earlier experiments and source-only tests
are distinguished from final package installation tests. Detailed sanitized
receipts live in `docs/verification/`.

## Rebuild the preview

The source repository contains the shared services, UI and Android adapters.
Large public reference databases are distributed in the wheel rather than Git.
To restore them, extract the verified wheel as a ZIP into a temporary directory
and copy the six files under `free_bible_reader/assets/data/*.sqlite` into the
checkout's `data/` directory. Check them against `PUBLIC-ASSET-MANIFEST.json`.
Do not substitute a personal library or the private BIBLIA corpus.

The tested Android build uses JDK 21, Gradle 9.3.1, Android SDK 36, NDK
28.2.13676358, CMake 3.22.1 and Chaquopy 17.2 with Python 3.14. Use the SDK/JDK
and build-Python configuration described in `android/`; these are build tools,
not prerequisites on the phone. `tools/stage_android_assets.py all` constructs
the public allowlisted resource bundles. Ultimate additionally uses
`android/speech/prepare_native.py` and `prepare_assets.py` for pinned native
sources, dictionaries and the three verified public voice models. The speech
README describes the host compiler requirement and exact model/source pins.

Build the `lite` and `ultimate` release variants with `targetAbi=arm64-v8a`.
The current release signing configuration intentionally uses the development
certificate; replace that configuration with your own protected production
signing process for a production distribution. Never commit a signing key.
The separate Android speech source archive and the Git tag together supply the
application/native source used by this preview. No private database is needed
to build the public products.

First-party source remains MIT licensed. Datasets, fonts, voices, Chaquopy,
Android libraries and native dependencies keep their individual licenses.
Ultimate includes GPL speech components; its combined distribution is supplied
with GPL-compatible notices and the corresponding speech source archive.
