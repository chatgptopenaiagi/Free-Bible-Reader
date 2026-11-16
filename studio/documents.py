"""Bounded, text-only PDF/DOCX generation and persistent artifact history."""
from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import uuid
from bisect import bisect_right
from pathlib import Path

from .paths import data_root, public_root
from . import workspace as w

MAX_BLOCKS = 1000
MAX_TOTAL_CHARS = 500_000
MAX_ARTIFACT_BYTES = 30_000_000
SHAPES = frozenset({"selection", "verses", "chapter", "multichapter", "searchcomparison", "collection", "notes"})
MIMES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
_FONT_LOCK = threading.Lock()
_renderer = None

def configure_renderer(renderer=None):
    """Inject a native renderer for validated, source-preserving requests."""
    global _renderer
    if renderer is not None and not callable(renderer):
        raise TypeError('Document renderer must be callable')
    _renderer = renderer
_FONTS = {"sans": ("DejaVuSans.ttf", "DejaVu Sans", "7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954"),
          "serif": ("DejaVuSerif.ttf", "DejaVu Serif", "42d1edeb7952f31b1f96d767ed7030b08a39e0c372b0071641518864e2bffb51"),
          "mono": ("DejaVuSansMono.ttf", "DejaVu Sans Mono", "b4a6c3e4faab8773f4ff761d56451646409f29abedd68f05d38c2df667d3c582"),}
_ALIASES = {"system": "sans", "segoeui": "sans", "arial": "sans", "calibri": "sans", "verdana": "sans", "tahoma": "sans", "notosans": "sans", "dejavusans": "sans", "georgia": "serif", "timesnewroman": "serif", "palatino": "serif", "notoserif": "serif", "dejavuserif": "serif", "consolas": "mono", "dejavusansmono": "mono"}


class DocumentError(w.WorkspaceError):
    pass


def _text(value, name, maximum):
    value = w._text(value, name, maximum)
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise DocumentError("INVALID_DOCUMENT_TEXT", "Document text contains unsupported control characters.")
    return value


def _number(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lower <= value <= upper:
        raise DocumentError("INVALID_DOCUMENT_SETTING", f"Invalid {name}.")
    return float(value)


def _settings(raw):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise DocumentError("INVALID_DOCUMENT_SETTING", "Document settings must be an object.")
    allowed = {"font", "font_size", "paper", "margins_mm", "header", "footer", "page_numbers", "alignment", "include_notes", "include_references", "include_source_labels"}
    if set(raw) - allowed:
        raise DocumentError("INVALID_DOCUMENT_SETTING", "Unknown document settings.", details={"fields": sorted(set(raw) - allowed)})
    font = _text(raw.get("font", "serif"), "font", 80)
    key = re.sub(r"[\s_-]", "", font).casefold()
    family = key if key in _FONTS else _ALIASES.get(key)
    if not family:
        raise DocumentError("INVALID_FONT", "Choose a supported document font.")
    paper, alignment = raw.get("paper", "A4"), raw.get("alignment", "left")
    if paper not in {"A4", "Letter"} or alignment not in {"left", "center", "right", "justify"}:
        raise DocumentError("INVALID_DOCUMENT_SETTING", "Unsupported paper size or alignment.")
    margin = raw.get("margins_mm", 20)
    if isinstance(margin, (int, float)) and not isinstance(margin, bool):
        margin = dict.fromkeys(("top", "right", "bottom", "left"), margin)
    if not isinstance(margin, dict) or set(margin) != {"top", "right", "bottom", "left"}:
        raise DocumentError("INVALID_DOCUMENT_SETTING", "Margins must specify top, right, bottom and left in millimetres.")
    margin = {key: _number(value, "margin", 10, 50) for key, value in margin.items()}
    result = {"font": font, "font_family": family, "font_size": _number(raw.get("font_size", 12), "font size", 8, 24),
              "paper": paper, "margins_mm": margin, "header": _text(raw.get("header", ""), "header", 300),
              "footer": _text(raw.get("footer", ""), "footer", 300), "alignment": alignment}
    for field, default in (("page_numbers", True), ("include_notes", True), ("include_references", True), ("include_source_labels", True)):
        value = raw.get(field, default)
        if not isinstance(value, bool):
            raise DocumentError("INVALID_DOCUMENT_SETTING", f"{field} must be a boolean.")
        result[field] = value
    return result


def _blocks(raw):
    if not isinstance(raw, list) or len(raw) > MAX_BLOCKS:
        raise DocumentError("TOO_MANY_BLOCKS", "Export supports at most 1000 blocks.")
    result = []
    for value in raw:
        if not isinstance(value, dict):
            raise DocumentError("INVALID_DOCUMENT_BLOCK", "Each document block must be an object.")
        chosen = value.get("selected_text") if value.get("selected_text") is not None else value.get("text", "")
        text = _text(chosen, "block text", 100_000)
        reference = _text(value.get("reference", ""), "reference", 500)
        label = _text(value.get("edition_name") or value.get("label", value.get("edition_id", "")), "source label", 500)
        kind = value.get("kind", "scripture")
        if kind not in {"scripture", "note", "correction", "heading"}:
            raise DocumentError("INVALID_DOCUMENT_BLOCK", "Unknown document block kind.")
        # Store the exact original object as provenance; never execute markup or fetch URLs.
        try:
            source = json.loads(w._json(value))
            w._json(source).encode("utf-8")
        except (ValueError, TypeError, UnicodeEncodeError, RecursionError):
            raise DocumentError("INVALID_DOCUMENT_BLOCK", "Block provenance must be valid Unicode JSON.") from None
        if len(w._json(source)) > 250_000:
            raise DocumentError("DOCUMENT_TOO_LARGE", "A source block exceeds its supported size.")
        if value.get("source") is not None:
            w.validate_source(value["source"])
        if value.get("start_utf16") is not None or value.get("end_utf16") is not None:
            allowed = {key: item for key, item in value.items() if key in {"edition_id", "book", "chapter", "verse_start", "verse_end", "reference", "label", "selected_text", "text", "original_text", "sourceTextSha256", "start_utf16", "end_utf16"}}
            w.validate_source(allowed)
        result.append({"text": text, "reference": reference, "label": label, "kind": kind, "source_block": source})
    return result


def _request(payload):
    if not isinstance(payload, dict):
        raise DocumentError("INVALID_EXPORT", "An export request object is required.")
    if set(payload) - {"format", "title", "shape", "blocks", "settings", "notes"}:
        raise DocumentError("INVALID_EXPORT", "Unknown export request fields.")
    output_format, shape = payload.get("format"), payload.get("shape", "selection")
    if output_format not in MIMES or shape not in SHAPES:
        raise DocumentError("INVALID_EXPORT", "Choose PDF/DOCX and a supported export shape.")
    blocks = _blocks(payload.get("blocks", []))
    notes_input = payload.get("notes", [])
    if not isinstance(notes_input, list):
        raise DocumentError("INVALID_EXPORT", "Notes must be an array.")
    notes = _blocks([{"text": note, "kind": "note"} if isinstance(note, str) else {**note, "text": note.get("text", note.get("body", "")), "kind": "note"} for note in notes_input if isinstance(note, (str, dict))])
    if len(notes) != len(notes_input):
        raise DocumentError("INVALID_EXPORT", "Notes must contain text or note objects.")
    settings = _settings(payload.get("settings"))
    title = _text(payload.get("title", "Scripture study"), "title", 300)
    total = len(title) + len(w._json(blocks)) + len(w._json(notes))
    if total > MAX_TOTAL_CHARS or len(blocks) + len(notes) > MAX_BLOCKS:
        raise DocumentError("DOCUMENT_TOO_LARGE", "Export exceeds 1000 blocks or 500000 characters; choose a smaller selection.")
    if not blocks and not (settings["include_notes"] and notes):
        raise DocumentError("EMPTY_EXPORT", "Choose source text or notes to export.")
    return {"format": output_format, "shape": shape, "title": title, "blocks": blocks, "notes": notes, "settings": settings}


def _font(settings):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    family = settings["font_family"]
    name, label, expected = _FONTS[family]
    path = public_root() / "studio" / "fonts" / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise DocumentError("MISSING_EXPORT_FONT", "The bundled Unicode export font is missing or changed.", status=503)
    identifier = "FBR-" + family
    with _FONT_LOCK:
        if identifier not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(identifier, str(path)))
    return identifier, label


def _wrap(text, width, font, size):
    """Bounded wrapping retaining every original character in the rendered runs."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    widths = {}
    for logical in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not logical:
            yield "", True
            continue
        positions = [0.0]
        for char in logical:
            if char not in widths:
                widths[char] = stringWidth("    " if char == "\t" else char, font, size)
            positions.append(positions[-1] + widths[char])
        start = 0
        while start < len(logical):
            end = max(start + 1, bisect_right(positions, positions[start] + width, lo=start + 1) - 1)
            if end < len(logical):
                last_space = logical.rfind(" ", start, end)
                if last_space > start:
                    end = last_space + 1
            yield logical[start:end].replace("\t", "    "), end == len(logical)
            start = end


def _pdf(request):
    from reportlab.lib import pagesizes
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen.canvas import Canvas
    settings = request["settings"]
    font, rendered = _font(settings)
    included = request["blocks"] + (request["notes"] if settings["include_notes"] else [])
    text = request["title"] + settings["header"] + settings["footer"] + "".join(block["text"] + block["reference"] + block["label"] for block in included)
    available = pdfmetrics.getFont(font).face.charToGlyph
    missing = sorted({ord(char) for char in text if char not in "\n\r\t" and ord(char) not in available})
    if missing:
        raise DocumentError("MISSING_GLYPHS", "The selected PDF font cannot render some characters; choose DOCX or a different supported font.", details={"codepoints": [f"U+{code:04X}" for code in missing[:30]]})
    page_width, page_height = pagesizes.A4 if settings["paper"] == "A4" else pagesizes.letter
    margin = {key: value * mm for key, value in settings["margins_mm"].items()}
    left, right = margin["left"], page_width - margin["right"]
    width, size = right - left, settings["font_size"]
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=(page_width, page_height), pageCompression=1, invariant=1)
    canvas.setTitle(request["title"])
    canvas.setAuthor("FREE BIBLE READER")
    y, page_number = page_height - margin["top"], 1

    def furniture():
        canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont(font, 8)
        header = list(_wrap(settings["header"], width, font, 8))
        footer_width = width - (55 if settings["page_numbers"] else 0)
        footer = list(_wrap(settings["footer"], footer_width, font, 8))
        if len(header) > 2 or len(footer) > 2:
            raise DocumentError("HEADER_FOOTER_TOO_LONG", "The header/footer must fit within two lines.")
        for index, (line, _) in enumerate(header):
            canvas.drawString(left, page_height - 11 - index * 9, line)
        for index, (line, _) in enumerate(footer):
            canvas.drawString(left, 11 + (len(footer) - index - 1) * 9, line)
        if settings["page_numbers"]:
            canvas.drawRightString(right, 11, str(page_number))

    def paragraph(text, font_size, *, spacing=6, alignment=None):
        nonlocal y, page_number
        leading = font_size * 1.35
        for line, last in _wrap(text, width, font, font_size):
            if y - leading < margin["bottom"]:
                canvas.showPage()
                page_number += 1
                furniture()
                y = page_height - margin["top"]
            y -= leading
            canvas.setFont(font, font_size)
            align = alignment or settings["alignment"]
            measured = pdfmetrics.stringWidth(line, font, font_size)
            if align == "center":
                canvas.drawString(left + (width - measured) / 2, y, line)
            elif align == "right":
                canvas.drawRightString(right, y, line)
            elif align == "justify" and not last and line.count(" "):
                run = canvas.beginText(left, y)
                run.setFont(font, font_size)
                run.setWordSpace(max(0, width - measured) / line.count(" "))
                run.textLine(line)
                canvas.drawText(run)
            else:
                canvas.drawString(left, y, line)
        y -= spacing

    furniture()
    paragraph(request["title"], min(24, size + 6), spacing=12, alignment="left")
    for block in included:
        label = " · ".join(part for part in (block["reference"] if settings["include_references"] else "", block["label"] if settings["include_source_labels"] else "") if part)
        if block["kind"] == "correction":
            label = "Personal corrected copy" + (" · " + label if label else "")
        elif block in request["notes"]:
            label = "Personal note" + (" · " + label if label else "")
        if label and y - size * 4 < margin["bottom"]:
            canvas.showPage()
            page_number += 1
            furniture()
            y = page_height - margin["top"]
        if label:
            paragraph(label, max(8, size - 1), spacing=3, alignment="left")
        paragraph(block["text"], size, spacing=10)
    canvas.save()
    return output.getvalue(), {"pages": page_number, "rendered_font": rendered}


def _docx(request):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt, RGBColor
    settings = request["settings"]
    requested = settings["font"]
    font = {"sans": "Arial", "serif": "Georgia", "mono": "Consolas"}.get(requested, requested)
    document = Document()
    document.core_properties.title = request["title"]
    document.core_properties.author = "FREE BIBLE READER"
    section = document.sections[0]
    section.page_width, section.page_height = (Mm(210), Mm(297)) if settings["paper"] == "A4" else (Mm(215.9), Mm(279.4))
    for key, value in settings["margins_mm"].items():
        setattr(section, key + "_margin", Mm(value))
    section.header_distance = Mm(4)
    section.footer_distance = Mm(4)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = document.styles[name]
        style.font.name = font
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(settings["font_size"] if name == "Normal" else min(24, settings["font_size"] + (6 if name == "Title" else 1)))
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for attribute in list(fonts.attrib):
            if "theme" in attribute.casefold():
                del fonts.attrib[attribute]
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn("w:" + attribute), font)
        for border in list(style.element.findall(".//" + qn("w:pBdr"))):
            border.getparent().remove(border)
    document.styles["Title"].font.bold = False
    document.styles["Title"].font.underline = False
    document.add_paragraph(request["title"], "Title")
    align = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}[settings["alignment"]]
    section.header.paragraphs[0].text = settings["header"]
    section.header.paragraphs[0].style = document.styles["Normal"]
    footer = section.footer.paragraphs[0]
    footer.style = document.styles["Normal"]
    footer.text = settings["footer"]
    for paragraph in (section.header.paragraphs[0], footer):
        for run in paragraph.runs:
            run.font.name = font
            run.font.size = Pt(8)
    if settings["page_numbers"]:
        content_width = section.page_width - section.left_margin - section.right_margin
        footer.paragraph_format.tab_stops.add_tab_stop(content_width, WD_TAB_ALIGNMENT.RIGHT)
        footer.add_run("\t")
        for kind, value in (("begin", None), (None, "PAGE"), ("end", None)):
            element = OxmlElement("w:fldChar" if kind else "w:instrText")
            if kind:
                element.set(qn("w:fldCharType"), kind)
            else:
                element.text = value
                element.set(qn("xml:space"), "preserve")
            footer.add_run()._r.append(element)
    included = request["blocks"] + (request["notes"] if settings["include_notes"] else [])
    for block in included:
        label = " · ".join(part for part in (block["reference"] if settings["include_references"] else "", block["label"] if settings["include_source_labels"] else "") if part)
        if block["kind"] == "correction":
            label = "Personal corrected copy" + (" · " + label if label else "")
        elif block in request["notes"]:
            label = "Personal note" + (" · " + label if label else "")
        if label:
            paragraph = document.add_paragraph(label, "Heading 2")
            paragraph.paragraph_format.keep_with_next = True
        paragraph = document.add_paragraph()
        paragraph.alignment = align
        paragraph.add_run(block["text"])
        paragraph.paragraph_format.space_after = Pt(8)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue(), {"rendered_font": font, "editable": True}


def _summary(row, *, details=False):
    if row is None:
        raise DocumentError("ARTIFACT_NOT_FOUND", "Generated document was not found.", status=404)
    value = dict(row)
    metadata = json.loads(value.pop("metadata_json"))
    artifact_id = value.pop("id")
    value["artifact_id"] = artifact_id
    value["filename"] = metadata["download_filename"]
    value["download_url"] = "/api/studio/documents/" + artifact_id + "/download"
    value["shape"] = metadata["shape"]
    value["source_count"] = len(metadata["blocks"])
    value["settings"] = metadata["settings"]
    value["rendering"] = metadata["rendering"]
    if details:
        value["blocks"], value["notes"] = metadata["blocks"], metadata["notes"]
    return value


def create_export(payload):
    request = _request(payload)
    try:
        raw, rendering = _renderer(request) if _renderer is not None else (_pdf(request) if request["format"] == "pdf" else _docx(request))
    except ImportError as error:
        raise DocumentError("EXPORT_UNAVAILABLE", "This application package lacks a required document component.", status=503) from error
    if not raw or len(raw) > MAX_ARTIFACT_BYTES:
        raise DocumentError("DOCUMENT_TOO_LARGE", "Generated document exceeds the 30 MB limit.")
    artifact_id = str(uuid.uuid4())
    internal_name = artifact_id + "." + request["format"]
    friendly = re.sub(r"[^\w .-]", "_", request["title"], flags=re.UNICODE).strip(" .-")[:80] or "Document"
    request["download_filename"] = friendly + "-" + artifact_id[:8] + "." + request["format"]
    request["rendering"] = rendering
    folder = data_root() / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / internal_name
    with path.open("xb") as target:
        target.write(raw)
    try:
        with w._connect() as db:
            db.execute("INSERT INTO GeneratedArtifact VALUES(?,?,?,?,?,?,?,?,?)", (artifact_id, request["format"], request["title"], internal_name, MIMES[request["format"]], len(raw), hashlib.sha256(raw).hexdigest(), w._json(request), w.utc()))
    except Exception:
        path.unlink()
        raise
    return get_artifact(artifact_id)


def get_artifact(artifact_id):
    with w._connect() as db:
        return _summary(db.execute("SELECT * FROM GeneratedArtifact WHERE id=?", (w._id(artifact_id),)).fetchone(), details=True)


def list_artifacts(limit=100, offset=0):
    limit, offset = w._integer(limit, "limit", 200), w._integer(offset, "offset", 1_000_000)
    if not limit:
        raise DocumentError("INVALID_LIMIT", "The page size must be positive.")
    with w._connect() as db:
        count = db.execute("SELECT count(*) FROM GeneratedArtifact").fetchone()[0]
        rows = db.execute("SELECT * FROM GeneratedArtifact ORDER BY created_at DESC,id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return {"items": [_summary(row) for row in rows], "total": count, "limit": limit, "offset": offset}


def artifact_file(artifact_id):
    value = get_artifact(artifact_id)
    folder = (data_root() / "documents").resolve()
    path = (folder / (value["artifact_id"] + "." + value["format"])).resolve()
    if path.parent != folder or not path.is_file():
        raise DocumentError("ARTIFACT_NOT_FOUND", "Generated document file was not found.", status=404)
    if path.stat().st_size > MAX_ARTIFACT_BYTES or path.stat().st_size != value["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != value["sha256"]:
        raise DocumentError("ARTIFACT_CHANGED", "Generated document has changed; export a new copy.", status=409)
    return path


def read_artifact(artifact_id):
    value = get_artifact(artifact_id)
    return artifact_file(artifact_id).read_bytes(), value


def delete_artifact(artifact_id):
    path = artifact_file(artifact_id)
    with w._connect() as db:
        db.execute("DELETE FROM GeneratedArtifact WHERE id=?", (w._id(artifact_id),))
        path.unlink()
    return {"artifact_id": artifact_id, "deleted": True}
