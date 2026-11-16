"""Personal annotations and source snapshots, independent of Scripture databases."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from .paths import data_root

TYPES = frozenset({"notes", "highlights", "bookmarks", "collections", "savedsearch", "history", "corrections"})
ALIASES = {"note": "notes", "highlight": "highlights", "bookmark": "bookmarks", "collection": "collections", "savedsearches": "savedsearch", "correction": "corrections"}
MAX_BLOCKS = 1000
MAX_ITEM_CHARS = 500_000
SCHEMA_VERSION = 1


class _PersonalConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class WorkspaceError(ValueError):
    def __init__(self, code, message, *, status=400, details=None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details or {}


def utc():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _id(value):
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise WorkspaceError("INVALID_ID", "A valid item identifier is required.") from None
    if str(parsed) != str(value).lower():
        raise WorkspaceError("INVALID_ID", "A canonical UUID identifier is required.")
    return str(parsed)


def _text(value, name, maximum, *, default=""):
    if value is None:
        value = default
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise WorkspaceError("INVALID_TEXT", f"Invalid {name}.", details={"field": name, "maximum": maximum})
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise WorkspaceError("INVALID_UNICODE", f"Invalid Unicode in {name}.") from None
    return value


def _integer(value, name, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise WorkspaceError("INVALID_POSITION", f"Invalid {name}.")
    return value


def _utf16_slice(text, start, end):
    raw = text.encode("utf-16-le")
    if not 0 <= start <= end <= len(raw) // 2:
        raise WorkspaceError("INVALID_POSITION", "Selection offsets are outside the source text.")
    try:
        return raw[start * 2:end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        raise WorkspaceError("INVALID_POSITION", "Selection offsets split a Unicode surrogate pair.") from None


def validate_source(source):
    """Preserve exact supplied strings; browser offsets are explicitly UTF-16."""
    if source is None:
        return None
    if not isinstance(source, dict):
        raise WorkspaceError("INVALID_SOURCE", "Source provenance must be an object.")
    result = {}
    string_limits = {"edition_id": 120, "edition_name": 500, "language": 80,
                     "book": 120, "end_book": 120, "reference": 500,
                     "label": 500, "edition_version": 200, "selected_text": 100_000,
                     "text": 100_000, "original_text": 100_000, "source_text": 100_000, "sourceTextSha256": 64,
                     "source_text_sha256": 64, "offset_space": 80}
    allowed = set(string_limits) | {"chapter", "end_chapter", "verse_start", "verse_end", "verse", "start_utf16", "end_utf16", "start_scalar", "end_scalar", "origin", "license", "source_record_id"}
    if set(source) - allowed:
        raise WorkspaceError("INVALID_SOURCE", "Unknown source fields.", details={"fields": sorted(set(source) - allowed)})
    native_fields = {"chapter", "end_chapter", "verse_start", "verse_end", "verse"}
    for key, value in source.items():
        if value is None:
            result[key] = None
        elif key in string_limits:
            result[key] = _text(value, key, string_limits[key])
        elif key in {"origin", "license", "source_record_id"}:
            try:
                encoded = _json(value)
                encoded.encode("utf-8")
            except (ValueError, TypeError, UnicodeEncodeError, RecursionError):
                raise WorkspaceError("INVALID_SOURCE", "Source metadata must be valid Unicode JSON.") from None
            if len(encoded) > 20_000:
                raise WorkspaceError("INVALID_SOURCE", "Source metadata exceeds its supported size.")
            result[key] = json.loads(encoded)
        elif key in native_fields and isinstance(value, str):
            result[key] = _text(value, key, 80)
            if not value or any(ord(char) < 32 for char in value):
                raise WorkspaceError("INVALID_POSITION", "A nonempty native label is required.")
        else:
            result[key] = _integer(value, key)
    for key in ("sourceTextSha256", "source_text_sha256"):
        if result.get(key) and not re.fullmatch(r"[0-9a-fA-F]{64}", result[key]):
            raise WorkspaceError("INVALID_SOURCE", "Invalid source text checksum.")
    start, end = result.get("start_utf16"), result.get("end_utf16")
    if (start is None) != (end is None) or (start is not None and end < start):
        raise WorkspaceError("INVALID_POSITION", "Both ordered UTF-16 offsets are required.")
    original = result.get("original_text", result.get("source_text"))
    if result.get("original_text") is not None and result.get("source_text") is not None and result["original_text"] != result["source_text"]:
        raise WorkspaceError("SOURCE_MISMATCH", "Original source text fields disagree.")
    selected = result.get("selected_text", result.get("text"))
    if start is not None:
        result["offset_space"] = "source_original_utf16"
        if original is not None:
            actual = _utf16_slice(original, start, end)
            if selected is not None and actual != selected:
                raise WorkspaceError("SELECTION_MISMATCH", "Selected text does not match its exact source offsets.")
            result["selected_text"] = actual
            prefix = _utf16_slice(original, 0, start)
            result["start_scalar"], result["end_scalar"] = len(prefix), len(prefix) + len(actual)
        elif result.get("start_scalar") is not None or result.get("end_scalar") is not None:
            raise WorkspaceError("UNVERIFIED_SCALAR_OFFSET", "Scalar offsets require the original source text.")
    elif result.get("start_scalar") is not None or result.get("end_scalar") is not None:
        raise WorkspaceError("UNVERIFIED_SCALAR_OFFSET", "Scalar offsets are computed only from an exact UTF-16 selection.")
    if original is not None:
        actual_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
        supplied = result.get("sourceTextSha256", result.get("source_text_sha256"))
        if supplied and supplied.lower() != actual_hash:
            raise WorkspaceError("SOURCE_HASH_MISMATCH", "Original source text checksum does not match.")
        result["sourceTextSha256"] = actual_hash
    return result


def validate_blocks(blocks):
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        raise WorkspaceError("TOO_MANY_BLOCKS", "A maximum of 1000 source blocks is supported.")
    values = [validate_source(block) for block in blocks]
    if any(value is None for value in values) or len(_json(values)) > 2_000_000:
        raise WorkspaceError("ITEM_TOO_LARGE", "Source blocks exceed the supported size.")
    return values


def _connect():
    db = sqlite3.connect(data_root() / "workspace.sqlite", timeout=15, factory=_PersonalConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        db.close()
        raise WorkspaceError("UNSUPPORTED_SCHEMA", "This personal workspace uses a newer schema.")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS WorkspaceItem(
            id TEXT PRIMARY KEY, type TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL, source_json TEXT,
            blocks_json TEXT NOT NULL, color TEXT, tags_json TEXT NOT NULL,
            corrected_text TEXT, data_json TEXT NOT NULL, search_text TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK(revision>0),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS WorkspaceItemType ON WorkspaceItem(type,updated_at);
        CREATE TABLE IF NOT EXISTS CollectionMember(
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL REFERENCES WorkspaceItem(id) ON DELETE CASCADE,
            item_id TEXT REFERENCES WorkspaceItem(id) ON DELETE SET NULL,
            position INTEGER NOT NULL CHECK(position>=0),
            snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(collection_id,position)
        );
        CREATE TABLE IF NOT EXISTS GeneratedArtifact(
            id TEXT PRIMARY KEY, format TEXT NOT NULL, title TEXT NOT NULL,
            filename TEXT NOT NULL UNIQUE, mime TEXT NOT NULL,
            bytes INTEGER NOT NULL CHECK(bytes>=0), sha256 TEXT NOT NULL,
            metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        PRAGMA user_version=1;
    """)
    return db


def _kind(value):
    if not isinstance(value, str):
        raise WorkspaceError("INVALID_TYPE", "A personal workspace item type is required.")
    value = ALIASES.get(value, value)
    if value not in TYPES:
        raise WorkspaceError("INVALID_TYPE", "Unknown personal workspace item type.")
    return value


def _payload(payload, existing=None):
    if not isinstance(payload, dict):
        raise WorkspaceError("INVALID_ITEM", "An item object is required.")
    allowed = {"type", "title", "body", "text", "source", "blocks", "color", "tags", "corrected_text", "data", "revision"}
    if set(payload) - allowed:
        raise WorkspaceError("INVALID_ITEM", "Unknown item fields.", details={"fields": sorted(set(payload) - allowed)})
    old = existing or {}
    value = {"title": _text(payload.get("title", old.get("title")), "title", 300),
             "body": _text(payload.get("body", payload.get("text", old.get("body"))), "body", 100_000),
             "source": validate_source(payload.get("source", old.get("source"))),
             "blocks": validate_blocks(payload.get("blocks", old.get("blocks", []))),
             "color": payload.get("color", old.get("color")),
             "tags": payload.get("tags", old.get("tags", [])),
             "corrected_text": payload.get("corrected_text", old.get("corrected_text")),
             "data": payload.get("data", old.get("data", {}))}
    if value["color"] is not None and not (isinstance(value["color"], str) and re.fullmatch(r"(?:#[0-9A-Fa-f]{6}|yellow|green|blue|pink|purple|orange)", value["color"])):
        raise WorkspaceError("INVALID_COLOR", "A supported highlight color is required.")
    if not isinstance(value["tags"], list) or len(value["tags"]) > 32:
        raise WorkspaceError("INVALID_TAGS", "At most 32 tags are supported.")
    value["tags"] = list(dict.fromkeys(_text(tag, "tag", 80) for tag in value["tags"]))
    if value["corrected_text"] is not None:
        value["corrected_text"] = _text(value["corrected_text"], "corrected_text", 100_000)
    if not isinstance(value["data"], dict):
        raise WorkspaceError("INVALID_ITEM", "Additional item data must be an object.")
    try:
        encoded = _json(value)
        encoded.encode("utf-8")
    except (ValueError, TypeError, UnicodeEncodeError, RecursionError):
        raise WorkspaceError("INVALID_ITEM", "Item data must be valid Unicode JSON.") from None
    if len(encoded) > MAX_ITEM_CHARS:
        raise WorkspaceError("ITEM_TOO_LARGE", "Personal item exceeds its supported size.")
    if existing and (value["source"] != old.get("source") or value["blocks"] != old.get("blocks")):
        raise WorkspaceError("IMMUTABLE_SOURCE", "Original source provenance cannot be changed; create a new item instead.")
    return value


def _search_text(value):
    return "\n".join([value["title"], value["body"], value["corrected_text"] or "", _json(value["source"]), _json(value["blocks"]), " ".join(value["tags"])]).casefold()


def _row(row):
    if row is None:
        raise WorkspaceError("NOT_FOUND", "Personal item was not found.", status=404)
    value = dict(row)
    for field in ("source", "blocks", "tags", "data"):
        raw = value.pop(field + "_json")
        value[field] = json.loads(raw) if raw is not None else None
    value.pop("search_text")
    return value


def _members(db, collection_id):
    values = []
    for row in db.execute("SELECT * FROM CollectionMember WHERE collection_id=? ORDER BY position,id", (collection_id,)):
        value = dict(row)
        value["snapshot"] = json.loads(value.pop("snapshot_json"))
        values.append(value)
    return values


def get_item(item_id):
    with _connect() as db:
        value = _row(db.execute("SELECT * FROM WorkspaceItem WHERE id=?", (_id(item_id),)).fetchone())
        if value["type"] == "collections":
            value["members"] = _members(db, value["id"])
        return value


def list_items(item_type=None, query=None, limit=100, offset=0, *, edition_id=None, book=None, chapter=None):
    limit, offset = _integer(limit, "limit", 200), _integer(offset, "offset", 1_000_000)
    if limit < 1:
        raise WorkspaceError("INVALID_LIMIT", "The page size must be at least one.")
    clauses, params = [], []
    if item_type:
        clauses.append("type=?")
        params.append(_kind(item_type))
    if query is not None:
        query = _text(query, "query", 300)
        clauses.append("instr(search_text,?)>0")
        params.append(query.casefold())
    source_filters = [(key, value) for key, value in (("edition_id", edition_id), ("book", book), ("chapter", chapter)) if value is not None]
    if source_filters:
        terms, values = [], []
        for key, value in source_filters:
            terms.append("CAST(json_extract({source},'$." + key + "') AS TEXT)=?")
            values.append(_text(str(value), key, 120))
        source_term = " AND ".join(term.format(source="source_json") for term in terms)
        block_term = " AND ".join(term.format(source="block.value") for term in terms)
        clauses.append("((" + source_term + ") OR EXISTS(SELECT 1 FROM json_each(blocks_json) AS block WHERE " + block_term + "))")
        params.extend(values + values)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as db:
        total = db.execute("SELECT count(*) FROM WorkspaceItem" + where, params).fetchone()[0]
        rows = db.execute("SELECT * FROM WorkspaceItem" + where + " ORDER BY updated_at DESC,id LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
        return {"items": [_row(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def search_items(query, item_type=None, limit=100, offset=0):
    return list_items(item_type, query, limit, offset)


def create_item(item_type, payload=None):
    if isinstance(item_type, dict) and payload is None:
        payload, item_type = item_type, item_type.get("type")
    kind, value = _kind(item_type), _payload(payload or {})
    if kind in {"highlights", "bookmarks", "corrections"} and not (value["source"] or value["blocks"]):
        raise WorkspaceError("SOURCE_REQUIRED", "This item requires original source provenance.")
    if kind == "corrections" and value["corrected_text"] is None:
        raise WorkspaceError("CORRECTION_REQUIRED", "A separate corrected text value is required.")
    item_id, created = str(uuid.uuid4()), utc()
    with _connect() as db:
        db.execute("INSERT INTO WorkspaceItem VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (item_id, kind, value["title"], value["body"], _json(value["source"]) if value["source"] is not None else None, _json(value["blocks"]), value["color"], _json(value["tags"]), value["corrected_text"], _json(value["data"]), _search_text(value), 1, created, created))
    return get_item(item_id)


def update_item(item_id, patch, expected_revision=None):
    if not isinstance(patch, dict):
        raise WorkspaceError("INVALID_ITEM", "An item patch object is required.")
    item_id = _id(item_id)
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = _row(db.execute("SELECT * FROM WorkspaceItem WHERE id=?", (item_id,)).fetchone())
        if "type" in patch and _kind(patch["type"]) != old["type"]:
            raise WorkspaceError("IMMUTABLE_TYPE", "An item type cannot be changed.")
        expected = expected_revision if expected_revision is not None else patch.get("revision")
        if expected is not None and expected != old["revision"]:
            raise WorkspaceError("REVISION_CONFLICT", "The item changed; reload it before saving.", status=409)
        value = _payload(patch, old)
        db.execute("UPDATE WorkspaceItem SET title=?,body=?,source_json=?,blocks_json=?,color=?,tags_json=?,corrected_text=?,data_json=?,search_text=?,revision=revision+1,updated_at=? WHERE id=?", (value["title"], value["body"], _json(value["source"]) if value["source"] is not None else None, _json(value["blocks"]), value["color"], _json(value["tags"]), value["corrected_text"], _json(value["data"]), _search_text(value), utc(), item_id))
    return get_item(item_id)


def delete_item(item_id, expected_revision=None):
    item_id = _id(item_id)
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = _row(db.execute("SELECT * FROM WorkspaceItem WHERE id=?", (item_id,)).fetchone())
        if expected_revision is not None and old["revision"] != expected_revision:
            raise WorkspaceError("REVISION_CONFLICT", "The item changed; reload it before deleting.", status=409)
        db.execute("DELETE FROM WorkspaceItem WHERE id=?", (item_id,))
    return {"id": item_id, "deleted": True}


def add_collection_item(collection_id, payload):
    collection_id = _id(collection_id)
    if not isinstance(payload, dict):
        raise WorkspaceError("INVALID_MEMBER", "A collection member object is required.")
    item_id = _id(payload["item_id"]) if payload.get("item_id") else None
    if item_id:
        snapshot = get_item(item_id)
        if snapshot["type"] == "collections":
            raise WorkspaceError("NESTED_COLLECTION", "Nested collections are not supported.")
    elif payload.get("blocks"):
        snapshot = {"type": "source_blocks", "blocks": validate_blocks(payload["blocks"]), "title": _text(payload.get("title"), "title", 300)}
    elif payload.get("note") is not None:
        note = payload["note"]
        snapshot = {"type": "note", "body": _text(note.get("text") if isinstance(note, dict) else note, "note", 100_000)}
    else:
        raise WorkspaceError("INVALID_MEMBER", "A source item, source blocks or note is required.")
    member_id = str(uuid.uuid4())
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        collection = _row(db.execute("SELECT * FROM WorkspaceItem WHERE id=?", (collection_id,)).fetchone())
        if collection["type"] != "collections":
            raise WorkspaceError("NOT_COLLECTION", "The destination is not a collection.")
        count = db.execute("SELECT count(*) FROM CollectionMember WHERE collection_id=?", (collection_id,)).fetchone()[0]
        size = db.execute("SELECT coalesce(sum(length(snapshot_json)),0) FROM CollectionMember WHERE collection_id=?", (collection_id,)).fetchone()[0]
        if count >= 1000 or size + len(_json(snapshot)) > 1_000_000:
            raise WorkspaceError("COLLECTION_FULL", "A collection supports at most 1000 members.")
        position = db.execute("SELECT coalesce(max(position),-1)+1 FROM CollectionMember WHERE collection_id=?", (collection_id,)).fetchone()[0]
        db.execute("INSERT INTO CollectionMember VALUES(?,?,?,?,?,?)", (member_id, collection_id, item_id, position, _json(snapshot), utc()))
        db.execute("UPDATE WorkspaceItem SET revision=revision+1,updated_at=? WHERE id=?", (utc(), collection_id))
    return get_item(collection_id)


def remove_collection_item(collection_id, member_id):
    collection_id, member_id = _id(collection_id), _id(member_id)
    with _connect() as db:
        if not db.execute("DELETE FROM CollectionMember WHERE collection_id=? AND id=?", (collection_id, member_id)).rowcount:
            raise WorkspaceError("NOT_FOUND", "Collection member was not found.", status=404)
        db.execute("UPDATE WorkspaceItem SET revision=revision+1,updated_at=? WHERE id=?", (utc(), collection_id))
    return get_item(collection_id)


def collection_items(collection_id):
    value = get_item(collection_id)
    if value["type"] != "collections":
        raise WorkspaceError("NOT_COLLECTION", "The item is not a collection.")
    return {"items": value["members"], "total": len(value["members"])}
