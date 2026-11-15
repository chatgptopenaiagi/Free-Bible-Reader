# Installing FREE BIBLE READER

The Windows x64 desktop package includes its own Python runtime, local reference parser, three reading editions and three research engines. End users do not need a Python, Node.js or SQL Server installation. An installed web browser displays the reader.

## Download and install

1. Open the official [Free-Bible-Reader release page](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/latest).
2. Download [Free-Bible-Reader-0.1.0-windows-x64-setup.exe](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/v0.1.0/Free-Bible-Reader-0.1.0-windows-x64-setup.exe). It already contains the research assets; the separate research-data ZIP is only needed for source development.
3. Compare its SHA-256 with the value published for that exact asset. In PowerShell, `Get-FileHash -LiteralPath '.\Free-Bible-Reader-0.1.0-windows-x64-setup.exe' -Algorithm SHA256` calculates the local checksum.
4. Run the installer and choose its wizard language: **English or German**, using the official translations bundled with the installer compiler. The normal destination is `%LOCALAPPDATA%\Programs\Free Bible Reader`. Installation is per user, with an optional desktop shortcut and a Start menu entry.
5. Open **FREE BIBLE READER** from the shortcut or Start menu. The default browser opens the reader, and a small companion window provides **Open reader**, **Close application** and the launcher language selector.

This release build is unsigned. Windows can display publisher or reputation information accordingly. Use the official release location and the published checksum to assess the exact file; no change to Windows security settings is required by these instructions.

The installer’s platform metadata permits x64-compatible Windows versions from build 17763. Current verification is on Windows 11 x64; that metadata is not a claim that every older Windows build has been tested. Actual isolated installation, uninstallation and ordinary per-user installation each returned exit code 0, with no restart required. Reading, search, navigation and all three research engines passed installed-runtime tests. See [VERIFICATION.md](VERIFICATION.md).

## First reading session

Select **WEB**, **KJV** or **BSB**, then a book and chapter. Previous and next chapter navigation follows the chosen edition’s own book order and chapter metadata. Search runs against the selected edition; book filtering narrows the same local text index.

Settings offer English, Romanian or German interface text, reading width, separate interface and Scripture font sizes, line and paragraph spacing, workspace layouts, themes and custom colors. The companion window also offers all three languages; the installer wizard’s English/German choices are separate. Interface language does not translate Scripture. Twelve font stacks are selectable; the system uses fallbacks when a requested font is absent. No additional fonts are downloaded.

Custom colors are retained even when a combination has poor contrast. The app displays a contrast advisory and keeps essential restore controls on a separate readable surface. Use the high-contrast theme or reset settings when needed.

## Research editions

The visual and aggregate research graphs use KJV coordinates. The phrase research engine also provides its own BSB and Afrikaans AOV source records. AOV is not an additional main-reader edition. Unsupported mappings are reported rather than created from matching labels. Reading WEB and selecting KJV research are separate source choices; reference labels alone do not establish equivalent text.

## Offline operation and application data

After installation, ordinary reading, search and included research work without an internet connection. The application listens only on `127.0.0.1`; no public listener, permanent Windows service or SQL service is needed.

The launcher prefers local port `48179`, records the actual successful port and reuses it on later launches. If that port is occupied by another application, it selects an available port. Browser preferences belong to the precise local browser origin, including the port, so a different browser profile or a changed port can present separate settings.

The companion stores its runtime state, remembered origin and launcher language under `%LOCALAPPDATA%\FreeBibleReader`. Themes, panel settings and typography are stored in the browser’s local storage for the local reader origin. If storage is blocked or unavailable, settings continue for the current page session. Clearing the browser’s site data resets that browser’s saved settings.

Use **Close application** or close the companion window to stop the owned local server. Closing only the browser tab leaves the companion and server running. **Open reader** reopens the current local page. A stopped reader tab can remain visible in the browser until it is closed.

## Troubleshooting

| Symptom | Useful check |
|---|---|
| Browser tab did not open | Use **Open reader** in the companion window and verify that a default browser is configured. |
| Existing tab says the local site is unavailable | Start the application again and use the current link opened by the companion. The previous local server may have been stopped. |
| Settings appear reset | Check whether the browser profile or local port changed, private browsing is in use, or browser site storage was cleared or blocked. |
| Research says unsupported or unmapped | Confirm the selected source edition. KJV, BSB and AOV research have different coverage; WEB has no automatically asserted KJV alignment. |
| A selected typeface looks different | That font may be absent. The fallback stack preserves a readable family but cannot guarantee every historical-language glyph on every PC. |
| Source checkout reports missing research assets | A source clone is different from the complete installer. Follow the explicit asset instructions in [DEVELOPMENT.md](DEVELOPMENT.md). |

## Uninstalling and support

Use Windows **Settings → Apps → Installed apps → FREE BIBLE READER → Uninstall**, or its installed uninstaller. Browser-origin preferences and the launcher’s per-user state are distinct from installed program files; this guide does not promise their deletion by the uninstaller. No unrelated browser data should be removed to uninstall the reader.

Report reproducible issues at the [project issue tracker](https://github.com/chatgptopenaiagi/Free-Bible-Reader/issues), including the release version, Windows version, relevant source edition and steps. Do not include private browser profiles or credentials. See [third-party notices](../THIRD-PARTY-NOTICES.md) for translation and dataset attribution.
