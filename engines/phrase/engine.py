"""Engine C: provenance-bearing phrase references, exact matching, read-only SQLite.

The native dataset and the master corpus remain separate editions. Positions are
Unicode-scalar offsets in the exact text named by offset_space; normalization is
not used. All repeated exact positions are retained and the single span is null.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from free_bible_reader.resources import asset_root
ROOT = asset_root()
DATABASE = ROOT / 'data/xref_phrase.sqlite'
REPOSITORY = 'https://github.com/CrossReferences-org/bible-cross-references'
COMMIT = 'a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653'
OSIS = 'Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev'.split()
BOOK_INDEX = {book: index for index, book in enumerate(OSIS, 1)}
SUPPORTED = {'crossreferences:' + code: code for code in ['KJV', 'BSB', 'AOV']}


def connect(path=DATABASE):
    path = Path(path).resolve()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


def parse_single(reference):
    match = re.fullmatch(r'([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)', str(reference))
    if not match or match[1] not in BOOK_INDEX or int(match[2]) < 1 or int(match[3]) < 1:
        return None
    return match[1], int(match[2]), int(match[3])


def find_all_exact(text, phrase, whole_word=True):
    """All case-sensitive exact spans, with explicitly named Unicode edge policy."""
    if text is None:
        return {'match_status': 'NO_SOURCE_TEXT', 'positions': [], 'start_scalar': None, 'end_scalar': None}
    if phrase is None or phrase == '':
        return {'match_status': 'EMPTY_ANCHOR', 'positions': [], 'start_scalar': None, 'end_scalar': None}
    def word(char):
        return char.isalnum() or char == '_' or unicodedata.category(char).startswith('M')
    positions = []
    start = 0
    while True:
        found = text.find(phrase, start)
        if found < 0:
            break
        end = found + len(phrase)
        left_ok = not (whole_word and word(phrase[0]) and found and word(text[found - 1]))
        right_ok = not (whole_word and word(phrase[-1]) and end < len(text) and word(text[end]))
        if left_ok and right_ok:
            positions.append({'start_scalar': found, 'end_scalar': end})
        start = found + 1  # Preserve overlapping occurrences where edge policy permits them.
    status = 'EXACT' if len(positions) == 1 else ('AMBIGUOUS' if positions else 'NO_MATCH')
    return {'match_status': status, 'positions': positions,
            'start_scalar': positions[0]['start_scalar'] if len(positions) == 1 else None,
            'end_scalar': positions[0]['end_scalar'] if len(positions) == 1 else None,
            'matching_policy': 'case_sensitive_exact_unicode_scalar_substring',
            'boundary_policy': 'unicode_letter_number_mark_underscore_edges' if whole_word else 'none',
            'normalization_applied': False}


def get_native_verse(reference, translation='KJV'):
    """Return reconstructed real native source text; no master-corpus equivalence."""
    code = str(translation).removeprefix('crossreferences:').upper()
    response = {'reference': reference, 'edition': 'crossreferences:' + code,
                'translation': code, 'text': None, 'offset_space': 'native_source_edition'}
    if code not in {'KJV', 'BSB', 'AOV'}:
        return dict(response, status='UNSUPPORTED_EDITION')
    if not parse_single(reference):
        return dict(response, status='UNMAPPED_REFERENCE')
    if not DATABASE.is_file():
        return dict(response, status='NO_SOURCE_DATA')
    connection = connect()
    try:
        row = connection.execute('SELECT * FROM PhraseVerse WHERE edition_code=? AND reference=?', (code, reference)).fetchone()
        if row is None:
            return dict(response, status='NO_SOURCE_DATA', reason='No source verse in the included native edition')
        if row['native_text'] is None:
            return dict(response, status='NO_SOURCE_DATA', reason='AMBIGUOUS_NATIVE_FRAGMENT_ORDER',
                        source_fragment_ids=json.loads(row['source_fragment_ids_json']),
                        reconstruction_policy=row['reconstruction_policy'],
                        source_fragments=json.loads(row['source_fragments_json']))
        return dict(response, status='VALID_RESULT', text=row['native_text'],
                    source={'repository': REPOSITORY, 'commit': COMMIT, 'path': 'json/bible_verses.json',
                            'source_fragment_ids': json.loads(row['source_fragment_ids_json']),
                            'reconstruction': row['reconstruction_policy'], 'native_sort_values': json.loads(row['native_sort_values_json'])})
    finally:
        connection.close()


def anchor_payload(row, edition_id, native_text):
    match = find_all_exact(native_text, row['anchor_text'])
    return dict(match, offset_space='native_source_edition', native_source_text=native_text,
        matched_source_text=native_text, mapping_status='NATIVE_DATASET_EDITION_ONLY',
        master_source_ref=None, id=row['anchor_id'], text=row['anchor_text'],
        translation=row['edition_code'], source_reference=row['source_reference'],
        source_sort=row['source_sort'], source_format=row['source_format'],
        offsets_zero_based=True, offsets_end_exclusive=True)


def query(reference, edition_id='crossreferences:KJV', direction='both', limit=25, **options):
    response = {'engine_id': 'C', 'status': 'NO_SOURCE_DATA', 'reference': reference,
                'edition_id': edition_id, 'results': [], 'anchors': [],
                'supported_editions': list(SUPPORTED), 'engine_policy': 'Preserve source assertion, edition, ordered target group and exact phrase evidence; no theological classifier'}
    if edition_id not in SUPPORTED:
        return dict(response, status='UNSUPPORTED_EDITION')
    parsed = parse_single(reference)
    if parsed is None:
        return dict(response, status='UNMAPPED_REFERENCE', reason='This bounded engine query accepts one normalized OSIS verse; grouped target ranges remain preserved')
    if direction not in {'both', 'incoming', 'outgoing'} or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        return dict(response, status='QUERY_ERROR', error={'code': 'INVALID_QUERY_OPTIONS', 'message': 'direction must be both/incoming/outgoing and limit an integer in 1..1000'})
    if options.get('match_mode', 'exact') != 'exact':
        return dict(response, status='QUERY_ERROR', error={'code': 'UNSUPPORTED_MATCH_MODE', 'message': 'Only exact source-text matching is implemented'})
    if not DATABASE.is_file():
        return response
    code = SUPPORTED[edition_id]
    book, chapter, verse = parsed
    numeric = chapter * 1_000_000 + verse
    connection = None
    try:
        connection = connect()
        edition = connection.execute('SELECT * FROM PhraseEdition WHERE code=?', (code,)).fetchone()
        if edition is None:
            return response
        known_coordinate = connection.execute('SELECT 1 FROM PhraseVerse WHERE edition_code=? AND reference=?', (code,reference)).fetchone()
        if known_coordinate is None:
            known_coordinate = connection.execute('SELECT 1 FROM PhraseAnchor WHERE edition_code=? AND query_eligible=1 AND source_reference=? LIMIT 1', (code,reference)).fetchone()
        if known_coordinate is None:
            known_coordinate = connection.execute('SELECT 1 FROM PhraseTargetReference t JOIN PhraseReferenceRange r ON r.range_id=t.range_id JOIN PhraseAnchor a ON a.anchor_id=r.anchor_id WHERE a.edition_code=? AND a.query_eligible=1 AND t.book_osis=? AND t.start_coordinate<=? AND t.end_coordinate>=? LIMIT 1', (code,book,numeric,numeric)).fetchone()
        if known_coordinate is None:
            return dict(response,status='UNMAPPED_REFERENCE',reason='No edition-qualified coordinate is present in the supplied source data')
        predicates, parameters = [], [code]
        if direction in {'both', 'outgoing'}:
            predicates.append('a.source_reference=?')
            parameters.append(reference)
        if direction in {'both', 'incoming'}:
            predicates.append('EXISTS(SELECT 1 FROM PhraseTargetReference t WHERE t.range_id=r.range_id AND t.book_osis=? AND t.start_coordinate<=? AND t.end_coordinate>=?)')
            parameters.extend([book, numeric, numeric])
        sql = ('SELECT a.*,r.range_id,r.group_ordinal,r.target_references_json,r.target_display,'
               'r.raw_member_ids_json,r.raw_printed_reference,r.mapping_status AS target_mapping_status '
               'FROM PhraseAnchor a JOIN PhraseReferenceRange r ON r.anchor_id=a.anchor_id '
               'WHERE a.edition_code=? AND a.query_eligible=1 AND (' + ' OR '.join(predicates) + ') '
               'ORDER BY a.source_record,a.source_sort,r.group_ordinal LIMIT ?')
        parameters.append(limit + 1)
        rows = connection.execute(sql, parameters).fetchall()
        response['truncated'] = len(rows) > limit
        native_cache = {}
        anchor_cache = {}
        for row in rows[:limit]:
            source_reference = row['source_reference']
            if source_reference not in native_cache:
                native = connection.execute('SELECT native_text FROM PhraseVerse WHERE edition_code=? AND reference=?', (code, source_reference)).fetchone()
                native_cache[source_reference] = native[0] if native else None
            if row['anchor_id'] not in anchor_cache:
                anchor_cache[row['anchor_id']] = anchor_payload(row, edition_id, native_cache[source_reference])
            phrase = anchor_cache[row['anchor_id']]
            target_refs = json.loads(row['target_references_json'])
            actual_direction = 'outgoing' if source_reference == reference else 'incoming'
            response['results'].append({'source_reference': source_reference,
                'target_reference': row['target_display'], 'target_references': target_refs,
                'direction': actual_direction, 'relationship_type': 'CURATED_PHRASE_CROSS_REFERENCE',
                'dataset_source': {'repository': REPOSITORY, 'commit': COMMIT,
                    'path': 'json/cross_references.json' if row['source_format'] == 'JSON' else 'tsv/crossreferences_s21.tsv',
                    'source_record': f"{row['source_format'].lower()}:{row['source_record']}:translation:{code}:group:{row['group_ordinal']}",
                    'source_verse_id': row['source_verse_id'], 'source_member_ids': json.loads(row['raw_member_ids_json'])},
                'phrase_anchor': phrase,
                'evidence': {'assertion': 'Curated source dataset relationship, not generated doctrine or independently proven exegesis',
                    'native_edition': 'crossreferences:' + code, 'target_group_order': row['group_ordinal'],
                    'target_group_preserved': True, 'target_mapping_status': row['target_mapping_status'],
                    'raw_printed_reference': row['raw_printed_reference'], 'reverse_lookup_is_new_assertion': False}})
        # Anchors with no target groups and empty/no-match anchors remain discoverable.
        if direction in {'both', 'outgoing'}:
            for row in connection.execute('SELECT * FROM PhraseAnchor WHERE edition_code=? AND query_eligible=1 AND source_reference=? ORDER BY source_sort,source_record', (code, reference)):
                if row['anchor_id'] not in anchor_cache:
                    native = connection.execute('SELECT native_text FROM PhraseVerse WHERE edition_code=? AND reference=?', (code, reference)).fetchone()
                    anchor_cache[row['anchor_id']] = anchor_payload(row, edition_id, native[0] if native else None)
        response['anchors'] = list(anchor_cache.values())
        response['status'] = 'VALID_RESULT' if response['results'] else 'NO_MATCH'
        response['source_text_available'] = True
        response['edition_mapping_policy'] = 'Native source edition only; no private master-corpus mapping or universal versification equivalence.'
        return response
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
        return dict(response, status='QUERY_ERROR', error={'code': type(error).__name__, 'message': str(error)})
    finally:
        if connection is not None:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    parser.add_argument('--edition', default='crossreferences:KJV')
    parser.add_argument('--direction', default='both', choices=['both', 'incoming', 'outgoing'])
    parser.add_argument('--limit', default=25, type=int)
    parser.add_argument('--native-text', action='store_true')
    args = parser.parse_args()
    answer = get_native_verse(args.reference, args.edition if args.edition != 'eng-kjv' else 'KJV') if args.native_text else query(args.reference, args.edition, args.direction, args.limit)
    print(json.dumps(answer, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if answer['status'] == 'QUERY_ERROR' else 0


if __name__ == '__main__':
    raise SystemExit(main())
