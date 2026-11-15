# FREE BIBLE READER 0.1.0

An installable, offline Windows Bible reader with WEB, KJV and BSB, native book/chapter/verse navigation, local full-text search, three cross-reference research views and an adaptive multilingual interface.

## Install

Download **Free-Bible-Reader-0.1.0-windows-x64-setup.exe** and compare its SHA-256 with **SHA256SUMS.txt**. Run the per-user installer, then open **FREE BIBLE READER** from the Start menu. No Python, Node.js or SQL Server installation is required. The included application runs only on `127.0.0.1` and opens your default browser. Use the companion window’s **Close application** action to stop it.

## Included

- Three English reading editions, 93,307 source-verified verse records, 66 books per edition.
- Book/chapter navigation, verse selection, search and edition-native numbering.
- Visual, weighted graph and phrase-level research with source attribution.
- English, Romanian and German interface controls; six themes, seven palettes, custom colors and separate Scripture typography.
- Persistent settings, flexible research panels, keyboard interaction and responsive layouts.

## Verified

Actual installer, installed-runtime self-test (9/9), file-hash comparison, isolated uninstall and normal desktop launch/GUI Close application passed on Windows 11 x64. Installed Edge acceptance: **24/24**. Source checks: **28 Python**, **24 UI-core** and **15 localization** checks passed. All 93,307 reading records passed exact source comparison. See [the verification record](https://github.com/chatgptopenaiagi/Free-Bible-Reader/blob/v0.1.0/docs/VERIFICATION.md).

## Assets and limits

- The **setup EXE** is the complete end-user application.
- The **research-data ZIP** is an optional, checksum-verified source-development input; installer users do not need to extract it.
- **SHA256SUMS.txt** identifies both assets.
- The build is **unsigned**. The installer wizard is English/German; reader and companion controls are English/Romanian/German.
- Phone/tablet viewports were browser-emulated. Physical Android/iPhone and native APK/IPA builds are not certified or included.
- Main reading editions are English. Research models have explicitly different edition and reference coverage.

Application code is MIT licensed; Scripture, datasets and runtimes retain their separate [attribution and notices](https://github.com/chatgptopenaiagi/Free-Bible-Reader/blob/v0.1.0/THIRD-PARTY-NOTICES.md). The private original corpus, credentials and SQL Server databases are excluded.
