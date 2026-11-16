# Library and search guide

FREE BIBLE READER keeps its bundled reading texts separate from your personal editions and research workspace. You can read the included editions offline. Getting a new source over HTTPS requires an internet connection; reading a completed local import does not.

## Included Romanian text

**Biblia Liberă is a Latin-script Romanian New Testament draft**, not a complete Romanian Bible. It contains 27 books, 260 chapters and 7,958 native records. Its edition name and reading notice identify the draft and partial coverage. Genesis and the rest of the Old Testament are not included in this edition. [The publisher's current details](https://ebible.org/details.php?id=ronbl) identify the selected text as public domain and under revision. Another edition with a similar name or a different script must not be assumed to have the same text or permissions.

## Import a local edition

1. Open **Library → Import**. The BIBLIA-corpus action opens the same guided process with instructions for an existing personal corpus; it does not include that corpus in the application.
2. Choose a local file with the Windows picker, or use browser upload. The source is inspected read-only. Browser upload is limited to 256 MiB; use the native picker for a larger local SQLite file, up to 16 GiB.
3. If an archive contains several supported files, choose one member. If a known source contains multiple editions, search its actual source IDs, names or languages and explicitly choose the intended dataset.
4. Select the source table and map **book, chapter, verse/start label and original text**. Optional fields include end-verse label, original record ID and edition-filter column/value. Supply a name, language/dialect, source and rights note for your personal edition. An optional book-label mapping changes locator labels only; it does not establish equal verse boundaries between editions.
5. Preview the mapped records and original characters. Confirm the edition only after reviewing the preview. Changing the mapping or metadata invalidates the confirmation and requires a fresh preview.
6. Start the confirmed import. Progress shows committed records. Cancel retains completed checkpoints; unfinished editions stay out of normal reading/search until completion. Resume continues the same inspected source. If that source changes, choose and inspect it again.

Closing a dialog does not cancel a running task; use its Cancel control. Imported editions receive explicit local identifiers while retaining an original source identifier when supplied. Source metadata alone does not prove that every dataset is a distinct published edition or establish redistribution rights.

### Supported input shapes

- **SQLite:** ordinary source tables with mappable columns, including `.sqlite`, `.sqlite3`, `.db` and `.db3`. Known version-table corpora and selected-edition packages have edition selectors. Original databases are never edited. A live WAL database needs a closed/exported snapshot first; do not change an unrelated database's journal settings for this import.
- **CSV:** UTF-8 with a unique header row and consistent column counts.
- **JSON:** a top-level array of row objects. **JSONL/NDJSON:** one row object per line. Nested custom document formats need an appropriate export to rows first.
- **SQL dumps:** a restricted SQLite-style data subset with supported CREATE TABLE declarations and literal INSERT values. Commands, triggers, attachments, extension loading and arbitrary SQL are never executed. Unsupported dialect/control statements are rejected; export the source as SQLite, CSV or JSON instead.
- **ZIP:** bounded supported member files. Unsafe paths, symbolic links, nested executable/archive content and excessive expansion are rejected. Choose a member explicitly. Expanded content is limited to 256 MiB; ordinary nonSQLite source files are limited to 512 MiB.

Example row shape only—replace this synthetic text with your own authorized source:

```json
{"id":"source-row-1","book":"Example","chapter":"Prologue","verse":"a","text":"Original source text"}
```

Native labels can be noncontinuous or nonnumeric. A verse range remains one original record; the importer does not invent separate text for each verse inside it. Unicode characters and original text are preserved rather than silently rewritten or accent-normalized.

## Download a source without automatically importing it

Open **Library → Download** and provide a public HTTPS address. Optionally enter the publisher's SHA-256 checksum. Basic or Bearer authentication can be supplied in the dedicated fields when appropriate for that source. Credentials stay in memory, are not saved in preferences or receipts, and are not forwarded to a different redirect origin. URL passwords are not accepted; saved receipts omit URL queries.

Only public HTTPS destinations on port 443 are allowed. The application does not use this feature to contact loopback, private/internal addresses or local metadata endpoints. A completed download is staged only. Choose **Inspect and preview** and complete the separate confirmation process before any edition is imported. Unsupported publisher formats remain unsupported even when their download succeeds.

## Read an explicitly selected SQL Server database

The optional Windows adapter uses the existing Windows SQL client provider and your current Windows identity. Enter the server/instance and exact database name. It performs read-only metadata inspection and SELECT queries; it does not create databases, change services, elevate to administrator or change server settings.

Encryption defaults on. The separate certificate-trust checkbox is off by default; selecting it means the server certificate's identity is not verified. Generic imports require a selected table and a stable unique source-order column. An optional edition filter is parameterized. A recognized BIBLIA relational profile offers actual source editions/revisions and joins their native reference hierarchy instead of treating internal chapter IDs as chapter labels.

Rows are staged privately before the same mapping, preview and explicit confirmation workflow. The default staging limit is 100,000 rows, configurable up to 500,000; choose an edition/filter or export a suitable subset for larger tables. An unavailable client/provider or connection is reported without modifying the source or installing software automatically.

## Inspect, export or remove one personal edition

Your library displays actual book, chapter and native-record counts. UTF-8 text payload bytes are identified separately from physical database size; a multi-edition database's total size is not presented as one edition's share.

Choose **Export this edition as SQLite** and confirm the intended edition. The resulting package includes only that edition's text, native labels, source metadata and search index. Other private editions, notes and workspace items are excluded. The original source is retained. Use Windows SaveAs or the browser-download fallback, and keep the reported SHA-256 if you need to compare copies. Exporting a private package does not itself grant permission to redistribute its contents.

Removing a personal edition requires confirmation and leaves the original external source intact. It does not remove a bundled edition. The personal search-index rebuild action applies only to the personal library.

## Advanced search

Open **Search → Advanced search** to select current/one/all installed editions, optional books, Old/New Testament scope and matching mode:

| Mode | Meaning |
|---|---|
| Words | Every complete search word must occur. |
| Phrase | A contiguous phrase must match under the selected comparison policy. |
| Prefix | Words may begin with the supplied prefixes. |
| Boolean | Combine uppercase `AND`, `OR`, `NOT`, parentheses, quoted phrases and suffix `*`. |

Comparison is case-insensitive with Unicode NFC. **Preserve diacritic differences** keeps accents distinct; **Ignore combining diacritics** explicitly folds combining marks for matching. Returned source text remains unchanged. These are lexical aids, not morphology or proof of theological/philosophical equivalence. Unknown private book labels are not guessed into a testament.

Queries are limited to 200 characters. If longer selected text is used as a starting point, the dialog visibly identifies the shortened prefill; review it before pressing Search. Paging retains the submitted query/options even if you edit the draft fields. Cancel stops the current search. History records submitted searches; SaveSearch keeps reusable settings in your private workspace.

The advanced matcher currently scans bounded original text to maintain its explicit Unicode policy. A real FTS5 index exists and can be rebuilt, but the advanced matcher does not use a tokenizer prefilter that could omit Unicode matches. Default execution is bounded to 10 seconds / 500,000 records, with a maximum configured scan of 1,000,000 records. If a budget is reached, **PARTIAL** and a nonexact count are explicit; narrow the edition/book scope for a complete count. Partial results are not represented as a complete corpus search.

Each result can open its original passage, comparison, collection or export workflow. Check several results to save/export attributed source blocks together. Matching reference labels alone do not establish equal verse boundaries across editions. Personal notes and corrections remain separate from original Scripture text.

See [installation](INSTALLATION.md) and the [project overview](../README.md) for the supported release platform and distribution details.
