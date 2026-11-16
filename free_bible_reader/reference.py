"""Strict, offline, stdlib reference parser for canonical KJV66 coordinates.

This is a deliberately bounded fallback, not an implementation of the complete
upstream Bible Passage Reference Parser grammar. One book/chapter/verse or one
same-book range is accepted. Source-native numbering remains a separate layer.
"""
from __future__ import annotations
import contextlib
from functools import lru_cache
import json
import re
import sqlite3
import unicodedata
from .resources import asset_path

# Ordered KJV66 book names; historical translations do not acquire this canon
# merely by using one of these aliases. Aliases identify coordinates only.
_BOOK_NAMES = """
Gen|Genesis|Geneza|1 Mose
Exod|Exodus|Exodul|2 Mose
Lev|Leviticus|Leviticul|3 Mose
Num|Numbers|Numeri|4 Mose
Deut|Deuteronomy|Deuteronomul|5 Mose
Josh|Joshua|Iosua|Josua
Judg|Judges|Judecători|Richter
Ruth|Ruth|Rut|Rut
1Sam|1 Samuel|1 Samuel|1 Samuel
2Sam|2 Samuel|2 Samuel|2 Samuel
1Kgs|1 Kings|1 Împărați|1 Könige
2Kgs|2 Kings|2 Împărați|2 Könige
1Chr|1 Chronicles|1 Cronici|1 Chronik
2Chr|2 Chronicles|2 Cronici|2 Chronik
Ezra|Ezra|Ezra|Esra
Neh|Nehemiah|Neemia|Nehemia
Esth|Esther|Estera|Ester
Job|Job|Iov|Hiob
Ps|Psalms|Psalmii|Psalmen
Prov|Proverbs|Proverbe|Sprüche
Eccl|Ecclesiastes|Eclesiastul|Prediger
Song|Song of Solomon|Cântarea Cântărilor|Hohelied
Isa|Isaiah|Isaia|Jesaja
Jer|Jeremiah|Ieremia|Jeremia
Lam|Lamentations|Plângerile lui Ieremia|Klagelieder
Ezek|Ezekiel|Ezechiel|Hesekiel
Dan|Daniel|Daniel|Daniel
Hos|Hosea|Osea|Hosea
Joel|Joel|Ioel|Joel
Amos|Amos|Amos|Amos
Obad|Obadiah|Obadia|Obadja
Jonah|Jonah|Iona|Jona
Mic|Micah|Mica|Micha
Nah|Nahum|Naum|Nahum
Hab|Habakkuk|Habacuc|Habakuk
Zeph|Zephaniah|Țefania|Zefanja
Hag|Haggai|Hagai|Haggai
Zech|Zechariah|Zaharia|Sacharja
Mal|Malachi|Maleahi|Maleachi
Matt|Matthew|Matei|Matthäus
Mark|Mark|Marcu|Markus
Luke|Luke|Luca|Lukas
John|John|Ioan|Johannes
Acts|Acts|Faptele Apostolilor|Apostelgeschichte
Rom|Romans|Romani|Römer
1Cor|1 Corinthians|1 Corinteni|1 Korinther
2Cor|2 Corinthians|2 Corinteni|2 Korinther
Gal|Galatians|Galateni|Galater
Eph|Ephesians|Efeseni|Epheser
Phil|Philippians|Filipeni|Philipper
Col|Colossians|Coloseni|Kolosser
1Thess|1 Thessalonians|1 Tesaloniceni|1 Thessalonicher
2Thess|2 Thessalonians|2 Tesaloniceni|2 Thessalonicher
1Tim|1 Timothy|1 Timotei|1 Timotheus
2Tim|2 Timothy|2 Timotei|2 Timotheus
Titus|Titus|Tit|Titus
Phlm|Philemon|Filimon|Philemon
Heb|Hebrews|Evrei|Hebräer
Jas|James|Iacov|Jakobus
1Pet|1 Peter|1 Petru|1 Petrus
2Pet|2 Peter|2 Petru|2 Petrus
1John|1 John|1 Ioan|1 Johannes
2John|2 John|2 Ioan|2 Johannes
3John|3 John|3 Ioan|3 Johannes
Jude|Jude|Iuda|Judas
Rev|Revelation|Apocalipsa|Offenbarung
"""


def _key(value):
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in normalized if c.isalnum() and not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _registry():
    with contextlib.closing(sqlite3.connect(asset_path("data/xref_reference.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        return {r[0]: json.loads(r[1]) for r in db.execute("SELECT osis,chapters_json FROM BookRegistry")}


@lru_cache(maxsize=3)
def _aliases(language):
    result = {}
    index = {"en": 1, "ro": 2, "de": 3}[language]
    for line in _BOOK_NAMES.strip().splitlines():
        parts = line.split("|")
        for alias in (parts[0], parts[index]):
            result[_key(alias)] = parts[0]
    extras = {
        "en": {"Psalm": "Ps", "Psa": "Ps", "Jn": "John", "Mt": "Matt", "Mk": "Mark", "Lk": "Luke", "Revelations": "Rev", "Song of Songs": "Song", "Philemon": "Phlm"},
        "ro": {"Psalm": "Ps", "Psalmi": "Ps", "Fapte": "Acts", "Apocalipsa lui Ioan": "Rev", "1 Împăraţi": "1Kgs", "2 Împăraţi": "2Kgs"},
        "de": {"Psalm": "Ps", "Joh": "John", "Mt": "Matt", "Mk": "Mark", "Lk": "Luke", "Apg": "Acts", "Röm": "Rom", "Offb": "Rev", "Ezechiel": "Ezek"},
    }
    result.update({_key(k): v for k, v in extras[language].items()})
    return result


def parse_reference(reference, language="en"):
    answer = {"status": "UNRECOGNIZED", "input": reference, "language": language, "normalized": [], "osis": "",
              "reference_system": "openbibleinfo-kjv", "parser_version": "fbr-strict-1",
              "parser_backend": "portable-strict", "indices": [], "entities": [],
              "scope": "One KJV66 book, chapter, verse or same-book range; EN/RO/DE names and OSIS. Not the full upstream grammar.",
              "note": "Reference coordinates do not establish edition or theological equivalence."}
    if language not in {"en", "ro", "de"}:
        return dict(answer, status="UNSUPPORTED_LANGUAGE")
    if not isinstance(reference, str) or len(reference) > 1000:
        return dict(answer, status="INVALID", errors=["Bounded string reference required"])
    value = reference.strip()
    if not value:
        return answer
    translations = []
    annotation = re.search(r"\s+(KJV|BSB|WEB)$", value, re.IGNORECASE)
    if annotation:
        translations = [annotation[1].upper()]
        value = value[:annotation.start()].strip()
    # Do not fish a valid substring out of invalid input or prose. A sequence or
    # cross-book range requires the optional upstream/platform parser.
    if ";" in value or ("," in value and language == "en"):
        return dict(answer, status="AMBIGUOUS", errors=["One contiguous reference required"])
    value = value.replace("–", "-").replace("—", "-")
    if language in {"ro", "de"}:
        value = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ":", value)
    match = re.fullmatch(r"(.+?)(?:[\s.]*(\d+)(?:\s*[:.]\s*(\d+))?)?(?:\s*-\s*(.+))?", value)
    if not match:
        return answer
    book_name, chapter, verse, endpoint = match.groups()
    # Explicit OSIS uses a dot; the general grammar otherwise includes the dot
    # in the name for short books, so normalize separators at the alias edge.
    book = _aliases(language).get(_key(book_name.rstrip(". ")))
    if not book:
        return answer
    lengths = _registry().get(book)
    if not lengths:
        return dict(answer, status="INVALID", errors=["Book outside KJV66 registry"])
    chapter = int(chapter) if chapter is not None else None
    verse = int(verse) if verse is not None else None
    if chapter is None:
        if endpoint:
            return dict(answer, status="INVALID", errors=["Range start requires a chapter"])
        start, end = (1, 1), (len(lengths), lengths[-1])
    elif not 1 <= chapter <= len(lengths) or (verse is not None and not 1 <= verse <= lengths[chapter - 1]):
        return dict(answer, status="INVALID", errors=["Chapter or verse outside declared KJV66 coordinates"])
    else:
        start, end = (chapter, verse or 1), (chapter, verse or lengths[chapter - 1])
        if endpoint:
            same_book = re.fullmatch(r"([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)", endpoint)
            if same_book:
                if same_book[1] != book:
                    return dict(answer, status="AMBIGUOUS", errors=["Cross-book ranges need full parser"])
                end = (int(same_book[2]), int(same_book[3]))
            elif re.fullmatch(r"\d+\s*[:.]\s*\d+", endpoint):
                ec, ev = re.split(r"\s*[:.]\s*", endpoint)
                end = (int(ec), int(ev))
            elif endpoint.isdigit():
                end = (chapter, int(endpoint)) if verse is not None else (int(endpoint), lengths[int(endpoint) - 1] if 1 <= int(endpoint) <= len(lengths) else 0)
            else:
                return dict(answer, status="AMBIGUOUS", errors=["Endpoint outside strict parser grammar"])
            if not 1 <= end[0] <= len(lengths) or not 1 <= end[1] <= lengths[end[0] - 1]:
                return dict(answer, status="INVALID", errors=["Range endpoint outside declared KJV66 coordinates"])
            if end < start:
                return dict(answer, status="AMBIGUOUS", errors=["Reversed range; no automatic correction"])
    first, last = f"{book}.{start[0]}.{start[1]}", f"{book}.{end[0]}.{end[1]}"
    osis = first if first == last else first + "-" + last
    return dict(answer, status="VALID", normalized=[osis], osis=osis,
                indices=[{"osis": osis, "translations": translations, "indices": [0, len(reference)]}])


def parse_many(requests):
    if not isinstance(requests, list) or len(requests) > 100:
        raise ValueError("PARSER_REQUEST_BOUND")
    answers = []
    for value in requests:
        if not isinstance(value, dict):
            raise ValueError("PARSER_REQUEST_OBJECT_REQUIRED")
        if value.get("operation") == "metadata" or value.get("apocrypha"):
            answers.append({"status": "UNSUPPORTED_OPERATION", "normalized": [], "parser_backend": "portable-strict",
                            "reason": "Use the full upstream or explicit platform parser for this operation."})
        else:
            answers.append(parse_reference(value.get("reference", ""), value.get("language", "en")))
    return answers
