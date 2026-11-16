import contextlib,hashlib,io,json,os,pathlib,sqlite3,tempfile,threading,unittest,zipfile
from urllib.parse import urlsplit
from unittest.mock import patch
from studio import library,importers,search,downloads

class PersonalLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=pathlib.Path(self.tmp.name);self.env=patch.dict(os.environ,{'FBR_STUDIO_DIR':str(self.home/'profile')});self.env.start()
        self.mapping={'table':'rows','book':'book','chapter':'chapter','verse':'verse','text':'text','source_record_id':'id'}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def source(self,rows,name='verses.jsonl'):
        p=self.home/name;p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');return p
    def row(self,i,text='La început Dumnezeu',book='John',chapter='3',verse=None):return {'id':i,'book':book,'chapter':chapter,'verse':verse or str(i),'text':text}
    def import_(self,rows,mapping=None,name='Personal test'):
        info=library.inspect_source(self.source(rows));job=library.create_import(info['inspection_id'],mapping or self.mapping,{'name':name,'language':'ro','source_edition_id':'actual-source-test'},confirmed=True)
        while job['status']!='COMPLETE':job=library.run_import(job['id'],2)
        return job
    def test_required_existing_reader_chapters_are_counts_not_labels(self):
        cases=[('Gen',1,31),('Ps',23,6),('Matt',5,48),('John',1,51),('John',3,36),('Rom',8,39),('Rev',21,27)]
        for ed in ('web','kjv','bsb'):
            for book,ch,count in cases:
                data=library.chapter(ed,book,ch);self.assertEqual(len(data['verses']),count);self.assertEqual(data['chapter'],ch)
        john=next(b for b in library.catalog('web')['books'] if b['id']=='John');self.assertEqual(john['chapter_labels'],list(range(1,22)));self.assertNotEqual(john['chapters'],john['chapter_labels'])
    def test_romanian_nt_draft_exact_source_and_absent_old_testament(self):
        ed=next(e for e in library.list_editions() if e['id']=='ronbl');self.assertTrue(ed['metadata']['draft']);self.assertEqual(ed['metadata']['coverage'],'New Testament only');self.assertEqual(len(library.catalog('ronbl')['books']),27)
        data=library.chapter('ronbl','John',3);v=next(v for v in data['verses'] if v['label']=='16');self.assertIn('Fiindcă atât de mult',v['text']);self.assertEqual(hashlib.sha256(v['text'].encode()).hexdigest(),v['text_sha256'])
        with self.assertRaisesRegex(ValueError,'REFERENCE_NOT_FOUND'):library.chapter('ronbl','Gen',1)
    def test_confirmation_required_and_no_partial_catalog(self):
        info=library.inspect_source(self.source([self.row(1)]));self.assertTrue(library.preview_import(info['inspection_id'],self.mapping)['valid'])
        with self.assertRaisesRegex(ValueError,'CONFIRMATION'):library.create_import(info['inspection_id'],self.mapping,{'name':'x'})
        job=library.create_import(info['inspection_id'],self.mapping,{'name':'x'},confirmed=True);self.assertNotIn(job['edition_id'],{e['id'] for e in library.list_editions()})
    def test_cancel_resume_atomic_checkpoint_without_duplicates(self):
        info=library.inspect_source(self.source([self.row(i) for i in range(1,5)]));job=library.create_import(info['inspection_id'],self.mapping,{'name':'x'},confirmed=True)
        job=library.run_import(job['id'],1);self.assertEqual((job['cursor'],job['inserted']),(1,1));library.cancel_import(job['id']);self.assertEqual(library.run_import(job['id'])['status'],'CANCELLED');library.resume_import(job['id'])
        job=library.run_import(job['id'],10);self.assertEqual((job['cursor'],job['inserted'],job['status']),(4,4,'COMPLETE'));self.assertEqual(len(library.chapter(job['edition_id'],'John',3)['verses']),4)
    def test_failed_batch_does_not_advance_cursor(self):
        # First preview must be valid; invalid data beyond its bounded sample is
        # encountered only during an actual later batch.
        p=self.source([self.row(i) for i in range(1,10)]+[self.row(10,text=7)],'bad.jsonl');info=library.inspect_source(p);job=library.create_import(info['inspection_id'],self.mapping,{'name':'x'},confirmed=True)
        job=library.run_import(job['id'],9)
        with self.assertRaisesRegex(ValueError,'INVALID_TEXT'):library.run_import(job['id'],10)
        job=library.import_status(job['id']);self.assertEqual((job['cursor'],job['inserted'],job['status']),(9,9,'FAILED'));self.assertNotIn(job['edition_id'],{e['id'] for e in library.list_editions()})
    def test_native_ranges_suffixes_and_noncontinuous_chapters(self):
        job=self.import_([self.row(1,chapter='Prologue',verse='a'),self.row(2,chapter='1',verse='1-2'),self.row(3,chapter='3',verse='3a')])
        cat=library.catalog(job['edition_id']);self.assertEqual(cat['books'][0]['chapter_labels'],['Prologue',1,3]);v=library.chapter(job['edition_id'],'John',1)['verses'][0];self.assertEqual((v['label'],v['nativeVerseStart'],v['nativeVerseEnd']),('1-2',1,2));self.assertEqual(library.chapter(job['edition_id'],'John',1)['next']['chapter'],3)
        p=self.source([{**self.row(1),'end':None}],name='nullable-end.jsonl');info=library.inspect_source(p);self.assertEqual(library.preview_import(info['inspection_id'],{**self.mapping,'end_verse':'end'})['sample'][0]['verse'],'1')
    def test_exact_unicode_nul_supplementary_and_original_normalization(self):
        texts=['In the beginning','La început','Am Anfang','בראשית','Ἐν ἀρχῇ','في البدء','t\u0326ară\x00😀']
        job=self.import_([self.row(i,t) for i,t in enumerate(texts,1)]);actual=library.chapter(job['edition_id'],'John',3)['verses'];self.assertEqual([v['text'] for v in actual],texts)
        self.assertTrue(all(v['text_sha256']==hashlib.sha256(t.encode()).hexdigest() for v,t in zip(actual,texts)))
    def test_source_mutation_rejected_and_bundled_removal_forbidden(self):
        info=library.inspect_source(self.source([self.row(1)]));p=pathlib.Path(info['path']);p.write_text(p.read_text()+' ',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):library.preview_import(info['inspection_id'],self.mapping)
        with self.assertRaisesRegex(ValueError,'PERSONAL_EDITION'):library.remove_edition('web',confirmed=True)
    def test_sqlite_source_readonly_and_actual_version_selector(self):
        p=self.home/'source.db3'
        with contextlib.closing(sqlite3.connect(p)) as c,c:
            c.executescript('CREATE TABLE version(id TEXT,language TEXT,language_english TEXT,vernacular_title TEXT,english_title TEXT,territory TEXT);CREATE TABLE verse(id INTEGER PRIMARY KEY,version_id TEXT,book TEXT,chapter INTEGER,start_verse INTEGER,end_verse INTEGER,text TEXT);')
            c.execute('INSERT INTO version VALUES(?,?,?,?,?,?)',('real-key','Română','Romanian','Titlu','Title','Romania'));c.execute('INSERT INTO verse VALUES(1,?,?,?,?,?,?)',('real-key','Luke',1,1,2,'Text original'))
        before=importers.sha256(p);info=library.inspect_source(p,copy=False);es=library.list_source_editions(info['inspection_id'],query='Romanian');self.assertEqual(es['editions'][0]['source_edition_id'],'real-key');self.assertEqual(library.list_source_editions(info['inspection_id'],source_edition_id='real-key')['editions'][0]['row_count'],1)
        mapping={**es['mapping_template'],'edition_value':'real-key'};self.assertEqual(library.preview_import(info['inspection_id'],mapping)['sample'][0]['verse'],'1-2');self.assertEqual(before,importers.sha256(p))
    def test_csv_and_json_incremental_sources(self):
        csvp=self.home/'test.csv';csvp.write_text('id,book,chapter,verse,text\n1,John,1,1,"Început, cuvânt"\n',encoding='utf-8');info=library.inspect_source(csvp);self.assertEqual(library.preview_import(info['inspection_id'],self.mapping)['sample'][0]['text'],'Început, cuvânt')
        jp=self.home/'test.json';jp.write_text(json.dumps([self.row(1),self.row(2)],ensure_ascii=False),encoding='utf-8');info=library.inspect_source(jp);self.assertEqual(len(library.preview_import(info['inspection_id'],self.mapping)['sample']),2)
        for bad in ('[{"x":1},, {"x":2}]','[{"x":1},]','[{"x":1}{"x":2}]'):
            with self.assertRaises(ValueError):list(importers._json_array_rows(io.StringIO(bad)))
    def test_safe_sql_dump_literal_data_never_executes_commands(self):
        text="CREATE TABLE verses(id INTEGER,book TEXT,chapter TEXT,verse TEXT,text TEXT); INSERT INTO verses VALUES(1,'John','3','16','Dumnezeu; O''Brien');"
        p=self.home/'safe.sql';p.write_text(text,encoding='utf-8');info=library.inspect_source(p);mapping={**self.mapping,'table':'verses'};self.assertEqual(library.preview_import(info['inspection_id'],mapping)['sample'][0]['text'],"Dumnezeu; O'Brien")
        for bad in ('ATTACH DATABASE \'evil\' AS x;','CREATE TRIGGER x AFTER INSERT ON verses BEGIN DELETE FROM verses; END;','SELECT load_extension(\'x\');','PRAGMA writable_schema=ON;'):
            p=self.home/'bad.sql';p.write_text(text+bad,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SQL_STATEMENT_NOT_ALLOWLISTED'):library.inspect_source(p)
    def test_zip_member_selection_traversal_and_limits(self):
        p=self.home/'safe.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('folder/source.jsonl',json.dumps(self.row(1)))
        choices=library.inspect_source(p);self.assertTrue(choices['requires_member_selection']);info=library.inspect_source(p,member=choices['members'][0]);self.assertTrue(library.preview_import(info['inspection_id'],self.mapping)['valid'])
        for name in ('../escape.csv','C:/escape.csv','/escape.csv'):
            with zipfile.ZipFile(self.home/'bad.zip','w') as z:z.writestr(name,'book,chapter,verse,text')
            with self.assertRaisesRegex(ValueError,'UNSAFE_ZIP_PATH'):library.inspect_source(self.home/'bad.zip')
    def test_search_exact_folded_boolean_prefix_scopes_pagination(self):
        job=self.import_([self.row(1,'La început Dumnezeu iubește'),self.row(2,'La inceput Dumnezeu iertare'),self.row(3,'La început rău'),self.row(4,'A different loving verse')]);ed=job['edition_id']
        self.assertEqual(search.search('început',ed,diacritics='exact')['total'],2);self.assertEqual(search.search('inceput',ed,diacritics='folded')['total'],3)
        self.assertEqual(search.search('"La început" AND Dumnezeu NOT rău',ed,mode='boolean')['total'],1);self.assertEqual(search.search('iub',ed,mode='prefix')['total'],1)
        a=search.search('Dumnezeu',ed,limit=1);b=search.search('Dumnezeu',ed,limit=1,offset=1);self.assertNotEqual(a['results'][0]['reference'],b['results'][0]['reference']);self.assertEqual(a['total'],2)
        self.assertEqual(search.search('Dumnezeu',ed,testament='OT')['total'],0);self.assertEqual(search.search('Dumnezeu',ed,testament='NT')['total'],2)
        with self.assertRaises(ValueError):search.search('word AND )',ed,mode='boolean')
    def test_search_cancellation_and_bounded_partial_count(self):
        event=threading.Event();event.set();self.assertEqual(search.search('God','web',cancel_event=event)['status'],'CANCELLED');r=search.search('God','web',max_scan_rows=1);self.assertEqual(r['status'],'PARTIAL');self.assertFalse(r['total_exact']);self.assertEqual(r['scanned_rows'],1)
    def test_public_https_target_validation_blocks_internal_and_mixed_dns(self):
        def resolver(ip):return lambda *a,**k:[(2,1,6,'',(ip,443))]
        for url in ('http://example.org/data.zip','https://user:password@example.org/a','https://localhost/a','https://example.org:444/a'):
            with self.assertRaises(ValueError):downloads.public_target(url,resolver('8.8.8.8'))
        for ip in ('127.0.0.1','10.0.0.1','169.254.169.254','::1'):
            with self.assertRaises(ValueError):downloads.public_target('https://public.example/a',resolver(ip))
        self.assertEqual(downloads.public_target('https://example.org/data.zip?token=hidden',resolver('8.8.8.8'))[1],'example.org')
        mixed=lambda *a,**k:[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('10.0.0.1',443))]
        with self.assertRaises(ValueError):downloads.public_target('https://example.org/a',mixed)
    def test_authenticated_download_stages_only_and_never_persists_credentials(self):
        calls=[];body=b'book,chapter,verse,text\nJohn,1,1,Original\n'
        class Response:
            status=200
            def getheader(self,name):return str(len(body)) if name=='Content-Length' else None
            def read(self,size):value=getattr(self,'remaining',body);self.remaining=b'';return value
        class Connection:
            def __init__(self,host,ip):self.host=host
            def request(self,method,target,headers):calls.append(headers)
            def getresponse(self):return Response()
            def close(self):pass
        target=downloads.public_target('https://example.org/source.csv?private=query',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
        with patch.object(downloads,'public_target',return_value=target),patch.object(downloads,'_PinnedHTTPS',Connection):
            r=downloads.stage_download('https://example.org/source.csv?private=query',auth={'type':'bearer','token':'synthetic-test-value'},expected_sha256=hashlib.sha256(body).hexdigest())
        self.assertEqual(r['status'],'DOWNLOADED_ONLY');self.assertEqual(pathlib.Path(r['path']).read_bytes(),body);self.assertTrue(r['requires_inspection_and_confirmation']);self.assertTrue(calls[0]['Authorization'].startswith('Bearer '))
        saved=pathlib.Path(r['path']).with_suffix('.csv.receipt.json').read_text();self.assertNotIn('synthetic-test-value',saved);self.assertNotIn('private=query',saved);self.assertNotIn('Authorization',saved);self.assertFalse(library.library_path().exists())
    def test_cross_origin_redirect_does_not_forward_auth_and_cancel_removes_partial(self):
        calls=[]
        class Response:
            def __init__(self,status):self.status=status
            def getheader(self,name):return 'https://other.example/result.csv' if name=='Location' and self.status==302 else '4' if name=='Content-Length' else None
            def read(self,size):out=getattr(self,'remaining',b'data');self.remaining=b'';return out
        class Connection:
            def __init__(self,host,ip):self.host=host
            def request(self,method,target,headers):calls.append((self.host,headers))
            def getresponse(self):return Response(302 if self.host=='one.example' else 200)
            def close(self):pass
        def target(url):return urlsplit(url),urlsplit(url).hostname,['8.8.8.8']
        with patch.object(downloads,'public_target',side_effect=target),patch.object(downloads,'_PinnedHTTPS',Connection):
            downloads.stage_download('https://one.example/a.csv',auth={'type':'basic','username':'test-user','password':'synthetic-only'})
        self.assertIn('Authorization',calls[0][1]);self.assertNotIn('Authorization',calls[1][1]);event=threading.Event();event.set();before=set((self.home/'profile/downloads').iterdir())
        with patch.object(downloads,'public_target',side_effect=target),patch.object(downloads,'_PinnedHTTPS',Connection):
            with self.assertRaisesRegex(ValueError,'DOWNLOAD_CANCELLED'):downloads.stage_download('https://other.example/a.csv',cancel_event=event)
        self.assertEqual(set((self.home/'profile/downloads').iterdir()),before)
    def test_sqlserver_rejects_connection_injection_without_executing_helper(self):
        from studio import sqlserver
        with patch.object(sqlserver,'_process',side_effect=AssertionError('helper must not run')):
            with self.assertRaisesRegex(ValueError,'HOST'):sqlserver.inspect_sqlserver('host;password=bad','database')
            with self.assertRaisesRegex(ValueError,'DATABASE'):sqlserver.inspect_sqlserver('host','')
            with self.assertRaisesRegex(ValueError,'UUID'):sqlserver.stage_sqlserver('host','database','corpus','TextUnit','SourceRecordId',profile='biblia-corpus-lab',edition_value='not-a-uuid')
    def test_selected_edition_export_exact_reopen_and_excludes_other_private_data(self):
        one=self.import_([self.row(1,'La început 😀',chapter='Prologue',verse='a'),self.row(2,'בראשית',chapter='3',verse='1-2')],name='Exported edition')
        two=self.import_([self.row(9,'Other private edition must not leak')],name='Other private edition')
        with self.assertRaisesRegex(ValueError,'CONFIRMATION'):library.export_edition(one['edition_id'])
        before=importers.sha256(library.library_path());artifact=library.export_edition(one['edition_id'],confirmed=True);self.assertEqual(artifact['records'],2);self.assertEqual(before,importers.sha256(library.library_path()));self.assertEqual(importers.sha256(artifact['path']),artifact['sha256'])
        with contextlib.closing(library.open_readonly(artifact['path'])) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(db.execute('SELECT COUNT(*) FROM Edition').fetchone()[0],1);self.assertEqual(db.execute('SELECT id FROM Edition').fetchone()[0],one['edition_id']);self.assertEqual(db.execute('SELECT COUNT(*) FROM ImportJob').fetchone()[0],0);rows=db.execute('SELECT chapter,verse,text,source_record_id FROM Verse ORDER BY sort_order').fetchall();self.assertEqual([tuple(r) for r in rows],[('Prologue','a','La început 😀','1'),('3','1-2','בראשית','2')]);self.assertEqual(db.execute("SELECT COUNT(*) FROM PersonalSearch WHERE PersonalSearch MATCH 'început'").fetchone()[0],1)
        stats=library.edition_stats(one['edition_id']);self.assertEqual((stats['books'],stats['chapters'],stats['verses']),(1,2,2));self.assertGreater(stats['text_utf8_bytes'],0)
        info=library.inspect_source(artifact['path']);editions=library.list_source_editions(info['inspection_id']);self.assertEqual(editions['total'],1);self.assertEqual(editions['editions'][0]['source_edition_id'],one['edition_id']);self.assertEqual(len(library.preview_import(info['inspection_id'],{**editions['mapping_template'],'edition_value':one['edition_id']})['sample']),2)
        with self.assertRaises(ValueError):library.export_path('../../source')

if __name__=='__main__':unittest.main()
