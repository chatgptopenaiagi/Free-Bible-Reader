# Personal workspace and document exports

FREE BIBLE READER keeps personal notes, highlights, bookmarks, collections and corrected copies separate from the Bible texts. Exported PDF and DOCX documents use the content you choose; selecting a phrase does not automatically export its whole chapter.

## Save a selection

Select words in the reader, then right-click or use Shift+F10 to open the study menu. Choose a note, highlight, bookmark or collection action. The captured selection excludes verse-number buttons and retains its edition, native reference and exact text.

- **Notes** attach your own writing to the captured source. You can also create a note without an attached passage.
- **Highlights** save the selected range and a color. Supported browsers draw a highlight without rewriting the source text; annotation buttons provide an additional way to open the record. The text foreground adapts to the highlight color for readability.
- **Bookmarks** save the chosen source reference and text.
- **Corrected copies** keep your alternative wording in a separate personal field. The editor displays the original selection separately and never replaces the reader's original text.

Open the **Documents** menu to find these records. Filter by type, search personal items, edit their titles/text/tags or delete an unwanted item. An original source snapshot cannot be edited into a different passage; create a new item for another selection. Opening an attached passage uses that record's own edition and native coordinates.

Saved searches retain the query and selected search options. **Open saved search** reopens the advanced search dialog with those values. Reading history records opened chapters; search history records submitted searches. An opened chapter is not a claim that it was read completely.

## Assemble a collection

Choose **Add to collection** for a selection. Pick an existing collection or create one. A collection can contain several source blocks and personal notes. Open it from **Documents → Collections** to edit its title, inspect/remove members or export it.

Collection members are snapshots. Editing or deleting the original personal note does not silently rewrite a copy already saved in a collection. Remove that member separately if it is no longer wanted. Source editions and native labels stay attached to the copied material.

## Choose the export content

Open **File → Export PDF/DOCX**, the context-menu export action, or a personal item's **Export document** action. The export dialog offers:

| Content choice | Meaning |
|---|---|
| Exact selected text | Only the captured phrase or selected source blocks. |
| Current verse | The native verse associated with the captured selection or selected reader verse. |
| Current chapter | All verses in the current native chapter, chosen explicitly. |
| Several chapters | An ordered range in the current book, up to twenty native chapters. |
| Current search results | The available search-result set captured when the export dialog opens. |
| Native-coordinate comparison | Actual texts at the chosen coordinate, with an explicit warning about differing verse boundaries. |
| Personal collection | The chosen collection's stored source blocks and notes. |
| Personal notes | Attached notes or the bounded personal-note set. |

The preview displays the first five source blocks; the generated document uses the complete chosen set. Missing native comparison text is identified explicitly. Matching reference labels do not establish textual or versification equivalence.

## Set the document appearance

Choose PDF or editable DOCX, a title, serif/sans-serif/monospaced family, font size, A4/Letter paper, margins, paragraph alignment, header/footer and page numbering. Reference labels, source labels and personal notes can be shown or hidden independently. Hiding a displayed citation does not erase its stored provenance from the generated-document record.

PDF embeds a licensed DejaVu font. DOCX names a font family and uses the installed document application's fallbacks. The selected source text and its Unicode characters are preserved in the personal record. Romanian selectable-text exports were tested; complex-script shaping and universal font coverage are not certified. Unsupported PDF characters produce an explicit export failure rather than a silent claim of correct rendering; DOCX is an alternative to try.

Exports are deliberately bounded: at most 1,000 source/note blocks, a bounded text/provenance budget, and a 30 MB generated-file limit. Long headers/footers must fit within their allocated space. Split a very large selection into smaller documents when the application reports a size limit. This is not a whole-corpus export tool.

## Save the generated file

After **Generate document**, the document remains in **Generated documents** history.

- **Windows Save As** uses the desktop companion's real save dialog. Choose a destination and filename there. Cancelling that dialog keeps the generated document in history.
- **Browser download** is a separate action using the browser's own download behavior. It does not claim that a native Windows dialog was used.

Windows Save As is unavailable when the application is deliberately run headless without its desktop companion; the dialog explains that browser download remains available. Document generation and saving are different steps. An old download action is cleared while a new document is being generated.

The application resolves generated files by artifact identifier and does not accept an arbitrary caller-supplied file path. Its save dialog also protects registered source files and application files from accidental overwrite.

## Storage and source limits

Personal data normally lives under `%LOCALAPPDATA%\FreeBibleReader\studio`, outside the installation. An isolated test/profile override can use another studio directory. Themes and the last reader position are separate browser-origin preferences.

The personal SQLite store contains annotations, source snapshots, collection members and generated-document metadata. Generated files are in its document directory. Uninstalling application program files does not promise to erase this personal data. Close the application before making a backup of the studio folder.

Native chapter/verse identifiers can include zero, suffixes, ranges or nonnumeric labels. They are retained as supplied rather than forced into another edition's numbering. Browser selection offsets are stored as UTF-16 positions; scalar positions are derived only when exact original text is available. A personal annotation is not an assertion of cross-edition alignment.

See the [document and font notices](../licenses/studio-documents-NOTICES.md) for export-library and font attribution. The [main verification guide](VERIFICATION.md) describes the project's testing conventions; release-specific checks remain distinct from these feature instructions.
