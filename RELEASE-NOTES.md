# FREE BIBLE READER 0.1.1

This update keeps the three English editions and research data unchanged while improving reading continuity, navigation and startup recovery. The final production package passed its recorded application and installation checks.

## Reading improvements

- Resume the last native edition, chapter and visible or selected verse after reload.
- Change WEB/KJV/BSB without returning to John 1 when the native position is available; missing positions have an explicit notice.
- Choose a chapter from a grid, use previous/next controls at both ends of the chapter, and toggle reading focus.
- Keep book and chapter selectors visible after choosing a book, on desktop and narrow screens.
- Compare a selected coordinate using actual WEB/KJV/BSB text and a native-versification warning.
- Keep pagination tied to the submitted query, edition and book filter. Newer navigation wins over late responses.
- Reach search and study tools on demand, with a quieter sidebar and keyboard shortcuts that ignore text fields/dialogs.
- Reach settings at large text sizes on narrow portrait and short landscape layouts.

English, Romanian and German catalogs each have **521 matching keys**: eighteen new reader labels and the existing 503 values preserved. Interface localization does not translate Scripture.

## Startup recovery

A catalog-independent EN/RO/DE startup surface provides readable feedback and explicit Retry if a local component fails to load. It works without application CSS, clears no stored state and performs no automatic reload loop. The local server pending queue is 128. Controlled tests support the queue repair under the tested conditions without proving the cause of every earlier incident.

## Verified final production application

- **68/68** reading-experience and **24/24** existing browser acceptance checks passed on the actual installed executable.
- **8/8** injected startup/retry scenarios passed; the final repeated-start diagnostic saw **16/16** ready pages and no refused requests in 120 bounded static requests.
- Source checks passed **29 Python**, **24 UI-core**, **14 focused reader** and **15 localization** checks.
- Seven required chapters across all three editions made **714 exact UTF-8 verse comparisons**; eighteen real searches were checked.
- Eight CSS viewports and nine large-text settings cases passed. Each large-text case checked all 31 settings/color/footer controls.
- Isolated installation, clean-runtime self-test, actual production update/uninstall/reinstall and normal restart passed. All **180** bundle files matched; nine installed self-tests passed; no restart was required.
- Reading and appearance state survived real production reinstall/restart and a separate persistent-browser close/reopen without storage injection.

See [VERIFICATION.md](docs/VERIFICATION.md), the [historical 0.1.0 record](docs/verification/v0.1.0.md), and actual production [reading](screenshots/v0.1.1/production-reading-final/main.png), [comparison](screenshots/v0.1.1/production-reading-final/comparison.png) and [mobile](screenshots/v0.1.1/production-reading-final/mobile-reading.png) captures.

## Package, data and limits

The setup EXE is **171,933,773 bytes**, SHA-256 `690b384125667c1816b579f7ab006e52b6bd001bdc3153cd7a4d97b916b02059`. [Download the Windows x64 installer](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/v0.1.1/Free-Bible-Reader-0.1.1-windows-x64-setup.exe) from the [0.1.1 release](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/tag/v0.1.1), and compare its exact checksum.

All **93,307** reading records and the five SQLite snapshots retain their 0.1.0 hashes. The existing 0.1.0 research ZIP remains a source-development input; complete-installer users do not need another large download. Packaging uses portable pinned inputs and separate build, isolated verification and ordinary installation phases.

The Windows x64 package is unsigned. Installer controls are English/German; reader and companion controls are English/Romanian/German. Reading editions are English. Phone/tablet checks are browser emulation, with no native Android/iOS package, physical-device certification or independent WCAG certification. Matching references and cross-reference links do not prove textual or theological equivalence. Application code is MIT licensed; separate [data/runtime notices](THIRD-PARTY-NOTICES.md) remain applicable.
