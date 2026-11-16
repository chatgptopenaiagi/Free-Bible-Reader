# Installing FREE BIBLE READER

The Windows x64 package includes the application runtime, local parser, three English reading editions and three research engines. End users need an installed web browser, not Python, Node.js, SQL Server or a separate Bible library.

Version 0.1.1 passed reading, search, research, startup-recovery, integrity and actual uninstall/reinstall checks. Use the official [0.1.1 release](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/tag/v0.1.1) and its exact checksum.

## Download and install

1. Open the official [release page](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases). Confirm that the desired version has actually been published.
2. Download its complete Windows x64 setup EXE. The release filename is `Free-Bible-Reader-0.1.1-windows-x64-setup.exe`. The separate 0.1.0 research-data ZIP is a source-development input; installer users do not need to download or extract it.
3. Compare the downloaded file's SHA-256 with the checksum published for that exact release asset. For example:

   ```powershell
   Get-FileHash -LiteralPath '.\Free-Bible-Reader-0.1.1-windows-x64-setup.exe' -Algorithm SHA256
   ```

4. Run the installer. The wizard offers English/German and normally installs per user in `%LOCALAPPDATA%\Programs\Free Bible Reader`, with a Start menu entry and optional desktop shortcut.
5. Open **FREE BIBLE READER**. Your default browser displays the local reader. The companion window supplies **Open reader**, **Close application** and its own language selector.

The package is unsigned. Windows may display unknown-publisher or reputation information. Use the official release and exact checksum; these instructions require no change to Windows security settings. The installer metadata permits compatible x64 Windows builds from 17763, but recorded tests are on Windows 11 x64, not every older build. R3 production uninstall/reinstall returned exit 0, nine installed self-tests and 180 file-hash comparisons passed, and no restart was required. Final production browser checks passed 68/68 reading, 24/24 existing acceptance and 8/8 startup recovery, as recorded in [VERIFICATION.md](VERIFICATION.md).

## Updating from 0.1.0

Close the running application through its companion before running the newer ordinary installer. Do not uninstall the current application merely to prepare an update. Use the production setup EXE rather than a developer verification installer.

Appearance preferences remain in the browser's local storage for the exact reader origin. The new reading-position record is separate. Because 0.1.0 did not save that record, the first 0.1.1 reading session cannot recover a position that was never stored. After a successful chapter load, the application remembers the native edition, chapter and visible or selected verse. The update does not change the distributed Scripture or research data.

## Reading and comparison

Choose WEB, KJV or BSB, then a book and chapter. The chapter button opens a grid; previous/next controls are available above and below the text. Reading focus hides surrounding tools without resetting preferences. Keyboard shortcuts are `[` for the previous chapter, `]` for the next chapter and `/` for search; they are ignored while typing in fields or using a dialog.

Select a verse to open its research or compare its coordinate in WEB/KJV/BSB. Comparison shows actual source text. A shared reference label is not a guarantee of identical verse segmentation. If a requested position is absent in the new edition, the application reports that limitation and shows the available chapter.

Search belongs to its selected edition and optional book filter. Each result page keeps the query context that produced it; editing the input does not silently change an existing result set. Queries are limited to 200 characters. Selecting a result opens its own edition and passage.

## Appearance and languages

The reader and companion offer English, Romanian and German controls, independently of the installer's English/German wizard. Interface language does not translate Scripture. Settings include six theme modes, palettes/custom colors, separate interface and Scripture fonts/scales, spacing, reading width and workspace controls. Twelve font stacks use locally available fallbacks; no fonts are downloaded.

Custom colors are retained even when their contrast is poor. The advisory recommends high contrast or restoring defaults. Essential close/reset controls have a separate readable surface. The revised settings allow ordinary scrolling in narrow portrait and short landscape layouts, including the recorded large-text cases.

## Research editions

The visual and aggregate research graphs use KJV coordinates. Phrase research also has native BSB and Afrikaans AOV records. AOV is not a fourth main-reader edition. Unsupported mappings are reported rather than inferred from matching labels. WEB reading and KJV research are separate source choices.

## Offline operation and saved state

After a complete installation, included reading, search and research operate locally. The application listens only on `127.0.0.1`; no permanent Windows service or SQL service is needed. The launcher initially prefers port `48179`, remembers its successful port and chooses an available port if another application occupies it.

Browser preferences and reading position belong to the precise origin, including port and browser profile. A different profile or port can show separate state. Clearing reader site data removes the saved browser state. If storage is blocked, the page remains usable for that session with a safe fallback; persistence is not promised.

The companion stores its runtime state, remembered origin and launcher language under `%LOCALAPPDATA%\FreeBibleReader`. **Close application**, or the companion's close button, stops its local server. Closing only the browser tab leaves it running. **Open reader** reopens the current page. A stopped tab may remain visible until you close it.

If startup cannot load a local component, the application provides a readable Retry surface. Keep the companion open and use Retry to reload the page; this action does not clear saved settings or position. If the bootstrap itself cannot load, literal three-language retry text is still present. All eight final installed failure/retry scenarios passed.

## Troubleshooting and removal

| Symptom | Check |
|---|---|
| No browser page | Use **Open reader** and check the default browser setting. |
| An old tab cannot connect | Start the companion and use its current reader link. |
| Reading or display state appears reset | Check the browser profile, local port, private browsing and site-storage policy. No old reading position exists before the first 0.1.1 save. |
| An edition lacks the selected verse | Use the available chapter and the native-position notice; do not assume another edition's boundaries. |
| Research is unsupported/unmapped | Check the independently selected source edition and coverage. |
| Font looks different | The requested font may be absent; fallback glyph coverage varies. |
| A source clone lacks research data | Follow [DEVELOPMENT.md](DEVELOPMENT.md). The complete installer already supplies that data. |

Uninstall through Windows **Settings → Apps → Installed apps → FREE BIBLE READER → Uninstall**, or its installed uninstaller. Installed program files, browser-origin state and companion state are separate; this guide does not promise that uninstall removes saved browser settings. Do not remove unrelated browser data.

For reproducible problems, report the application version, Windows version, edition and steps through the [issue tracker](https://github.com/chatgptopenaiagi/Free-Bible-Reader/issues). Exclude private profiles and credentials. [Third-party notices](../THIRD-PARTY-NOTICES.md) describe source attribution.
