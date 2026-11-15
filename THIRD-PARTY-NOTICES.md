# Third-party notices

FREE BIBLE READER combines its own application code with separately licensed Scripture texts, research datasets, parser code and packaged runtimes. The application’s [MIT license](LICENSE) does not replace the rights or attribution requirements of these materials. No upstream project endorses this application by being listed here.

## Reading editions

| Included edition | Source and attribution | Rights statement carried with this distribution |
|---|---|---|
| World English Bible, Protestant Edition (WEB) | [eBible.org published verse-per-line edition](https://ebible.org/Scriptures/engwebp_vpl.zip); [edition information](https://ebible.org/find/details.php?id=engwebp) | The publisher identifies the text as public domain. “World English Bible” is an eBible.org trademark; retaining this name identifies the source edition rather than a modified translation. |
| King James Version (KJV), CrossReferences source edition | [CrossReferences.org repository at the pinned source revision](https://github.com/CrossReferences-org/bible-cross-references/tree/a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653); [KJV territorial notice](https://ebible.org/Scriptures/details.php?id=eng-kjv2006) | The KJV is public domain outside the United Kingdom. The source notice identifies a separate United Kingdom rights position; this application does not claim worldwide unrestricted ownership of the KJV. |
| Berean Standard Bible (BSB), CrossReferences source edition | The same pinned CrossReferences.org source; [Berean Bible terms](https://berean.bible/terms.htm) | The publisher dedicates the BSB text to the public domain under CC0. The included edition label identifies the actual source text. |

The reader contains 31,103 WEB rows, 31,102 KJV rows and 31,102 BSB rows. These are source edition counts, not a claim that every translation has identical verse segmentation. WEB’s source Romans 14:24–26 and its Romans 16 ending at verse 25 are preserved. Text was compared against all 93,307 included source records without normalizing the wording into another edition.

## Cross-reference research and reference parser

The detailed derivation record is [research-PROVENANCE.md](licenses/research-PROVENANCE.md). Source identifiers and record locators remain attached to results. Source-curated links are research assertions; inclusion does not establish theological equivalence, historical dependence or an automatic reverse relationship.

| Component | Pinned upstream source | Notices and applicable layers |
|---|---|---|
| Visual cross-reference graph | [Oleksii Trekhleb’s bible-cross-references](https://github.com/trekhleb/bible-cross-references/tree/23bf0908858c949e519abe7a4ce7f4492f5fb3ba) | Upstream application code: [MIT notice](licenses/research-visual-MIT.txt). Supplied graph: OpenBible.info cross-reference attribution under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), credited through the upstream dataset. |
| Aggregate cross-reference graph | [NEUU bible-crossrefs-dataset](https://github.com/neuu-org/bible-crossrefs-dataset/tree/8aa012820f5881a787e87d71005a22f52844c4fb) | NEUU’s consolidation/data/scripts: [CC BY 4.0 notice](licenses/research-aggregate-CC-BY.txt). The source identifies Torrey’s historical *Treasury of Scripture Knowledge* as public domain. The bundled SoulLiberty electronic source distribution includes a separate [GPL 2 notice](licenses/research-tsk-source-GPL2.txt), retained for that source/code/curation layer. These are separate layers; the entire collection is not relicensed as MIT. The pinned repository provides the upstream source materials and processing code. |
| Phrase-level cross-references and native source texts | [CrossReferences.org bible-cross-references](https://github.com/CrossReferences-org/bible-cross-references/tree/a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653) | Repository research data: [CC BY 4.0 text](licenses/research-phrase-CC-BY.txt). This is an explicitly derived public subset containing native KJV, BSB and AOV source records. The source identifies Afrikaans Ou Vertaling (AOV) as public domain; that source declaration is retained, without extending the application’s MIT license to the translation. |
| Bible passage reference parser | [Stephen Smith / OpenBible.info Bible-Passage-Reference-Parser](https://github.com/openbibleinfo/Bible-Passage-Reference-Parser/tree/15c9f0993267014d9d3aa81256b9ff5565e58856) | [MIT notice](licenses/research-parser-MIT.txt), also retained with vendored parser files. The included package metadata reports version 4.0.0; the pinned commit’s subject mentions a later alpha, which is not used as the installed package version. |

Public derivations include SQLite indexing and packaging; removal of S21/French data and nested S21 fields from the phrase dataset; removal of private build-path metadata and private mapping records; and a public-only SQLite journal-header change for the aggregate graph. Graph directions, source weights and missing-versus-zero vote distinctions are preserved. The public reference seed contains structural metadata without prior user resolutions or private edition mappings. AOV’s unresolved duplicate-sort coordinate has its text withheld rather than guessed.

These changes are described more precisely in the provenance record. Upstream file hashes identify upstream inputs; they are not represented as hashes of changed public records. The public assets have their own hashes. The research subset is not a promise that every source is mapped to every reading edition: the visual and aggregate graphs use KJV coordinates, while BSB/AOV research uses the phrase engine. WEB is a reading edition and has no silently inferred KJV research alignment.

## Packaged runtime components

| Component | Use | License notice included here |
|---|---|---|
| Python | Frozen application runtime and standard library | [Python / PSF license and bundled notices](licenses/PYTHON-LICENSE.txt) |
| Node.js | Executes the bundled reference parser locally | [Node.js license and its bundled third-party notices](licenses/NODE-LICENSE.txt) |
| Tcl | Tk companion window runtime | [Tcl license](licenses/TCL-LICENSE.txt) |
| Tk | Small desktop companion window | [Tk license](licenses/TK-LICENSE.txt) |
| PyInstaller | Executable bootloader and runtime hooks used in the frozen build | [PyInstaller COPYING](licenses/PYINSTALLER-COPYING.txt), including its GPL licensing terms and bootloader exception. That exception permits distribution of the combined application without imposing PyInstaller’s license on the application’s own code. |

SQLite is used through Python’s bundled SQLite support. [SQLite’s project declaration](https://www.sqlite.org/copyright.html) places its deliverable code in the public domain. This statement concerns the database engine, not the separately licensed contents of the database files.

The application names system font families as optional local font choices. It does not redistribute Microsoft, Noto or other font files, and a named font may be unavailable on a particular computer. The browser resolves the documented fallback stack.

## Redistribution

Keep this document and the applicable files in `licenses/` with redistributed packages. Attribute the named dataset creators, retain their source links and indicate changes when distributing derived CC BY material. Consult the relevant upstream notices for the electronic TSK source layer and for translation-specific territorial terms. Third-party copyright holders retain their rights; no additional rights are asserted by FREE BIBLE READER.
