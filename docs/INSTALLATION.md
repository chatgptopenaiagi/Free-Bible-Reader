# Installing FREE BIBLE READER 0.2.0

1. Download the Windows x64 setup EXE and SHA256SUMS from the [official release](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/tag/v0.2.0).
2. Verify its SHA-256 using `Get-FileHash -Algorithm SHA256` and compare the exact published checksum. The package is unsigned. No security-setting change is required.
3. Close an already running reader through its companion window, then run the ordinary installer. Keep the same destination when upgrading.
4. Open FREE BIBLE READER from Start. Choose the edition, book and chapter. The application includes its runtimes; Python, Node.js and SQL Server are not end-user requirements.

The wizard offers English/German. The reader and companion support English/Romanian/German independently of Scripture language. Default installation is `%LOCALAPPDATA%\Programs\Free Bible Reader`. The server binds to `127.0.0.1` and opens an existing browser; it is not exposed to the network. **Close application** stops the service; closing only the browser tab leaves it running.

## Romanian reading and narration

Select Biblia Liberă in the edition control or select Romanian as the text language. This is a Latin-script **draft New Testament only**, with 27 books; no Old Testament is supplied. Your interface language is independent.

Open **Audio → Voice Manager**. Windows voices shown are the ones the app can actually access. For neural Romanian narration, select Mihai and Install; one approximately 63 MB download is verified before installation. Thereafter it works offline. The bundled eSpeak Romanian fallback is available without that download. Windows voice installation remains a Windows Settings operation. [Audio guide](AUDIO-GUIDE.md).

## Personal library and documents

Use **Library → Import Bible Database** for local supported files, or Download Bible Database for an HTTPS source. Inspect, map, preview and confirm before import. For a large BIBLIA source, use the native Windows picker and choose individual editions. SQL Server requires an explicit Windows-authenticated source and a suitable schema/profile. [Library guide](LIBRARY-GUIDE.md).

Right-click selected Scripture for research, notes, highlights, collections and export. **File → Export PDF / DOCX** provides document settings, a native Save As dialog and a separate browser-download option. [Study guide](STUDIO-GUIDE.md).

## Saved data, upgrade and removal

Personal library snapshots, notes, voices and generated documents are under `%LOCALAPPDATA%\FreeBibleReader\studio`, outside the installed program. The installer/uninstaller does not remove that directory. Export selected personal editions and documents for your own backups.

Appearance and reading position are browser local-storage records for the exact browser profile and local origin, including port. The launcher remembers its last port and normally starts at 48179. Another browser profile/port can show different browser preferences. Clearing site storage removes that browser state, not the separate library database.

Use Windows Installed Apps or the application's registered uninstaller to remove the program. Keep personal data unless you explicitly choose to remove it yourself. No permanent Windows service is installed.

## Troubleshooting

- Keep the companion open; use Open reader or the visible Retry control if the local page fails to load.
- If a voice is missing, inspect provider/installation status rather than assuming a language voice exists.
- An unmapped research edition is a documented data limitation, not an instruction to change Scripture text.
- Large browser uploads are limited to 256 MiB. Use the native file picker for larger SQLite sources; no whole-source copy is required.
- Exact and folded diacritic searches are distinct. A partial result explicitly reports a search budget limitation.

Recorded testing is Windows 11 x64 with Edge. Physical phones, native APK/IPA packages, every speech locale and every possible SQL schema are not certified. See [verification](VERIFICATION.md) and [notices](../THIRD-PARTY-NOTICES.md).
