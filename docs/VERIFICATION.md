# Release 0.1.0 verification

Verified on Windows 11 x64 on 15 November 2026. These are observed tests of this release, not a promise that every device or browser has been certified.

## Installed Windows application

| Check | Observed result |
|---|---|
| Isolated per-user installer run | Exit 0 |
| Installed file hashes compared with the tested build | All ten principal executable, data, runtime and translation files matched |
| Installed executable self-test | 9/9 passed: actual reading editions, chapter retrieval, search, final-book navigation, UI assets and all three research engines |
| Clean host-runtime test | The same 9/9 passed with host Python/Node removed from PATH and Python/Node module overrides cleared |
| Installed-runtime Edge acceptance suite | 24/24 passed |
| Isolated uninstallation | Exit 0; test application executable removed |
| Ordinary owner installation | Exit 0; no reboot |
| Normal desktop launch and shutdown | Companion opened the browser; English/German companion controls were observed; GUI Close application stopped the owned listener |

The installed browser tests verified the running executable’s identity and hash. They exercised real chapters and book transitions, local search, native verse numbering, edition selection, 108 sampled verse-text comparisons, language/theme/typography changes, preference persistence, the three research engines and source provenance. The offline browser scenario made no external requests. No JavaScript exceptions or missing-translation warnings were observed in the final run.

The Windows executable SHA-256 is `c4ac9ee9f78e819fd9bed06aa2a41633486d80e26e67b65d998dc23855e67bc0`. The installer SHA-256 is `8c156b7941de2731de1f47a39182c5a18e8aa6626cbfcf0cf986e5466d8d5fcd`. Compare the downloaded installer with the [release checksum file](https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/v0.1.0/SHA256SUMS.txt).

## Source and data checks

- 28/28 Python tests: twelve reading/navigation/search checks and sixteen public research/integrity/asset-restoration checks.
- 24/24 Node UI-core tests and fifteen localization checks, with matching 503-key English, Romanian and German catalogs.
- All 93,307 packaged reading rows compared exactly with their source records. Three editions each have 66 books and 1,189 chapters. Native verse boundaries remain edition-specific.
- SQLite integrity and foreign-key checks passed for the packaged reader and the four specialized research models.
- Public research models exclude private corpus mappings, private host paths, user caches and S21/French source content. Dataset derivations retain their own provenance and notices.

Run the commands in [DEVELOPMENT.md](DEVELOPMENT.md) to reproduce source checks. `tests/browser/acceptance.mjs` accepts `READER_URL`, `READER_RUNTIME_STATE` and `READER_RUNTIME_KIND`; use an installed executable for installed-runtime claims. Browser automation uses the installed Edge browser through Playwright Core, rather than downloading a second browser.

## Adaptive interface regression

The precursor engineering workbench retained all 100 Python engine tests and all seventeen original browser checks. Its adaptive interface passed 58 browser checks, six focused accessibility checks, nine optional-browser-API fallback checks and five panel-navigation regression checks. These workbench results are distinct from the 24 installed-product browser checks above.

Responsive rendering was checked at 320×568, 375×667, 390×844, 430×932, 768×1024, 820×1180, 1024×768, 1280×800, 1440×900, 1920×1080, 2560×1440 and 3840×2160 CSS pixels. Equivalent 200%/400% reflow conditions, keyboard interaction, reduced motion, settings dialogs, contrast advisories and increased text sizes were exercised. Thirteen engineering screenshots and the eight public screenshots are actual rendered captures.

## Limits

Only Windows x64 and the recorded Edge browser runtime were tested. Responsive phone/tablet viewports are emulation, not physical Android or iPhone verification. WebKit, physical-device behavior, assistive-technology certification and native Android/iOS packages remain unverified or unbuilt. The accessibility work targets applicable WCAG 2.2 AA behavior and does not constitute independent WCAG certification.

The package is unsigned. The installer wizard is English/German; the reader and companion support English/Romanian/German. The reading editions are English, even when interface controls use another language. Locally available font glyph coverage varies. Cross-reference links remain source assertions rather than automatic textual or theological equivalence.

The original private multi-gigabyte corpus and SQL Server databases are not release inputs or runtime requirements. They are not included in Git or release assets.
