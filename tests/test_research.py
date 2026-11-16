"""Portable public research acceptance; actual datasets and negative boundaries."""
import contextlib,hashlib,importlib,json,pathlib,re,sqlite3,sys,tempfile,unittest,zipfile,io
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge import hub,reference,corpus_adapter
from engines.fetch_research_assets import archive_plan
from engines import fetch_research_assets


class PublicResearchTests(unittest.TestCase):
    def test_01_three_real_engines_john(self):
        result=hub.query({'reference':'John1:1','limit':4})
        self.assertEqual(result['status'],'VALID_RESULT')
        for name in('A','B','C'):
            self.assertEqual(result['engines'][name]['status'],'VALID_RESULT')
            self.assertTrue(result['engines'][name]['results'])
        self.assertEqual(result['source_mapping']['mapping_status'],'NATIVE_SOURCE')
        self.assertIsNone(result['source_mapping']['units'][0]['ref'])

    def test_02_actual_first_john_has_results(self):
        result=hub.query({'reference':'1John3:16','limit':4})
        self.assertEqual(result['reference'],'1John.3.16')
        self.assertTrue(all(result['engines'][name]['status']=='VALID_RESULT'for name in('A','B','C')))

    def test_03_bsb_and_aov_use_native_c_only(self):
        for edition in('crossreferences:BSB','crossreferences:AOV'):
            result=hub.query({'reference':'John1:1','edition_id':edition,'limit':3})
            self.assertEqual(result['engines']['A']['status'],'UNSUPPORTED_EDITION');self.assertEqual(result['engines']['B']['status'],'UNSUPPORTED_EDITION')
            self.assertEqual(result['engines']['C']['status'],'VALID_RESULT')
            self.assertEqual(result['source_mapping']['edition_id'],edition)
            self.assertTrue(all(row['phrase_anchor']['offset_space']=='native_source_edition'for row in result['engines']['C']['results']))

    def test_04_only_three_native_editions_exposed(self):
        self.assertEqual({item['edition_id']for item in hub.editions()},{'crossreferences:KJV','crossreferences:BSB','crossreferences:AOV'})
        self.assertEqual(hub.query({'reference':'John1:1','edition_id':'crossreferences:S21'})['status'],'UNSUPPORTED_EDITION')

    def test_05_parser_is_real_pinned_vendor_and_read_only(self):
        self.assertEqual(reference.parse_reference('Ioan1:1','ro')['normalized'],['John.1.1'])
        self.assertEqual(reference.parse_reference('Johannes1,1','de')['normalized'],['John.1.1'])
        with contextlib.closing(reference.connect_registry())as db:
            self.assertEqual(db.execute('PRAGMA query_only').fetchone()[0],1)
            with self.assertRaises(sqlite3.OperationalError):db.execute("INSERT INTO ParserResolution(input)VALUES('must-not-write')")

    def test_06_reference_seed_has_no_private_user_rows(self):
        with contextlib.closing(reference.connect_registry())as db:
            for table in('ParserResolution','ParserTestCase','EditionReferenceMap','ReferenceRange'):self.assertEqual(db.execute('SELECT COUNT(*)FROM '+table).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*)FROM BookRegistry').fetchone()[0],84)

    def test_07_actual_counts_and_three_native_editions(self):
        with contextlib.closing(sqlite3.connect((ROOT/'data/xref_visual.sqlite').as_uri()+'?mode=ro',uri=True))as db:self.assertEqual(db.execute('SELECT COUNT(*)FROM VisualEdge').fetchone()[0],344799)
        with contextlib.closing(sqlite3.connect((ROOT/'data/xref_aggregate.sqlite').as_uri()+'?mode=ro',uri=True))as db:self.assertEqual(db.execute('SELECT COUNT(*)FROM GraphEdgeSource').fetchone()[0],730514)
        with contextlib.closing(sqlite3.connect((ROOT/'data/xref_phrase.sqlite').as_uri()+'?mode=ro',uri=True))as db:
            self.assertEqual(db.execute('SELECT COUNT(*)FROM PhraseAnchor').fetchone()[0],190989)
            self.assertEqual({r[0]for r in db.execute('SELECT code FROM PhraseEdition')},{'KJV','BSB','AOV'})
            self.assertEqual(db.execute("SELECT COUNT(*)FROM PhraseMapping WHERE target_edition_id='eng-kjv'").fetchone()[0],0)

    def test_08_s21_fields_removed_from_remaining_json_and_fragments(self):
        def has_s21(value):
            if isinstance(value,dict):return any('s21'in key.lower()or has_s21(child)for key,child in value.items())
            return isinstance(value,list)and any(has_s21(child)for child in value)
        with contextlib.closing(sqlite3.connect((ROOT/'data/xref_phrase.sqlite').as_uri()+'?mode=ro',uri=True))as db:
            for column,table in [('original_anchor_json','PhraseAnchor'),('source_fragments_json','PhraseVerse')]:
                for row in db.execute('SELECT '+column+' FROM '+table):self.assertFalse(has_s21(json.loads(row[0])))

    def test_09_native_range_retains_whole_source_units(self):
        result=corpus_adapter.resolve_reference('John.1.1-John.1.3')
        self.assertEqual(result['mapping_status'],'NATIVE_SOURCE');self.assertEqual(len(result['units']),3)
        self.assertFalse(result['coverage']['fragmentation_applied'])

    def test_10_input_faults_are_bounded(self):
        for request in(None,[],{'reference':'John1:1','limit':0},{'reference':'John1:1','limit':101},{'reference':'John1:1','offset':401},{'reference':'John1:1','engine':'X'}):self.assertEqual(hub.query(request)['status'],'QUERY_ERROR')
        self.assertNotEqual(hub.query({'reference':'John999:1'})['status'],'VALID_RESULT')

    def test_11_engine_failure_does_not_stop_other_engines_or_leak_error_path(self):
        def loader(name):
            if name=='A':raise RuntimeError('PRIVATE_SENTINEL_PATH')
            return hub.load_engine(name)
        result=hub.query({'reference':'John1:1','limit':2},engine_loader=loader)
        self.assertEqual(result['status'],'VALID_RESULT');self.assertEqual(result['engines']['A']['status'],'QUERY_ERROR')
        self.assertNotIn('PRIVATE_SENTINEL_PATH',json.dumps(result))

    def test_12_parser_runtime_failure_is_honest(self):
        # Universal Python now has a deliberately bounded stdlib fallback;
        # an absent optional Node runtime must not disable canonical research.
        with mock.patch.dict('os.environ',{'FBR_PARSER':'auto'}),mock.patch.object(reference,'node_executable',side_effect=RuntimeError('unavailable')):
            result=hub.query({'reference':'John1:1'})
        self.assertEqual(result['status'],'VALID_RESULT')
        self.assertEqual(result['parser']['parser_backend'],'portable-strict')
        # Explicit full-upstream requests still report an unavailable runtime.
        with mock.patch.dict('os.environ',{'FBR_PARSER':'upstream'}),mock.patch.object(reference,'node_executable',side_effect=RuntimeError('unavailable')):
            result=hub.query({'reference':'John1:1'})
        self.assertEqual(result['status'],'QUERY_ERROR')

    def test_13_independent_results_have_public_provenance(self):
        result=hub.query({'reference':'John1:1','direction':'incoming','limit':3})
        text=json.dumps(result)
        self.assertIsNone(re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]',text))
        self.assertNotIn('master_package',text)
        for engine in result['engines'].values():
            for row in engine['results']:self.assertTrue(row['dataset_source']['repository'].startswith('https://github.com/'))

    def test_14_native_aov_ambiguous_text_stays_withheld(self):
        result=corpus_adapter.resolve_reference('Acts.10.31','crossreferences:AOV')
        self.assertEqual(result['mapping_status'],'UNMAPPED');self.assertEqual(result['units'],[])

    def test_15_zip_slip_rejected_by_explicit_asset_helper(self):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w')as archive:archive.writestr('../outside.sqlite','invalid')
        with zipfile.ZipFile(io.BytesIO(output.getvalue()))as archive:
            with self.assertRaises(ValueError):archive_plan(archive)

    def test_16_asset_restore_reuses_seed_and_preserves_reader(self):
        with tempfile.TemporaryDirectory(prefix='asset-restore-',dir=ROOT/'tests')as folder:
            folder=pathlib.Path(folder);(folder/'data').mkdir();reader=folder/'data/reader.sqlite';reader.write_bytes(b'READER_MUST_REMAIN_UNTOUCHED')
            seed=folder/'data/xref_reference.sqlite'
            with contextlib.closing(sqlite3.connect(seed))as db:db.execute('CREATE TABLE Fixture(value INTEGER)');db.commit()
            archive_path=folder/'assets.zip'
            with zipfile.ZipFile(archive_path,'w')as archive:
                for name in fetch_research_assets.ASSETS:archive.write(seed,'data/'+name)
            digest=hashlib.sha256(archive_path.read_bytes()).hexdigest()
            with mock.patch.object(fetch_research_assets,'ROOT',folder):result=fetch_research_assets.install(archive_path,digest)
            self.assertEqual(len(result['assets']),3);self.assertEqual(result['reused_identical_assets'],['data/xref_reference.sqlite'])
            self.assertEqual(reader.read_bytes(),b'READER_MUST_REMAIN_UNTOUCHED')


if __name__=='__main__':unittest.main(verbosity=2)
