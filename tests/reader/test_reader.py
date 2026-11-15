import contextlib,hashlib,pathlib,sqlite3,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reader import service
class ReaderTests(unittest.TestCase):
 def test_complete_catalog_three_source_editions(self):
  c=service.catalog();self.assertEqual({e['id'] for e in c['editions']},{'web','kjv','bsb'});self.assertEqual(len(c['books']),66);self.assertEqual(sum(len(b['chapters']) for b in c['books']),1189)
 def test_first_and_last_chapters(self):
  a=service.chapter(book='Gen',chapter=1);b=service.chapter(book='Rev',chapter=22)
  self.assertEqual(len(a['verses']),31);self.assertIsNone(a['previous']);self.assertIsNone(b['next']);self.assertEqual(b['verses'][-1]['reference'],'Rev.22.21')
 def test_real_reading_not_one_verse(self):
  c=service.chapter(book='John',chapter=3);self.assertEqual(len(c['verses']),36);self.assertIn('For God so loved the world',c['verses'][15]['text']);self.assertEqual([v['number'] for v in c['verses']],list(range(1,37)))
 def test_chapter_and_book_transition(self):
  c=service.chapter(book='Gen',chapter=50);self.assertEqual(c['next'],{'book':'Exod','chapter':1});self.assertEqual(service.chapter(book='Exod',chapter=1)['previous'],{'book':'Gen','chapter':50})
 def test_editions_independent(self):
  a=service.chapter('web','Gen',1)['verses'][0]['text'];b=service.chapter('kjv','Gen',1)['verses'][0]['text'];self.assertNotEqual(a,b);self.assertIn('heavens',a);self.assertIn('heaven and',b)
 def test_versification_not_forced(self):
  self.assertEqual(service.chapter('web','Rom',14)['verses'][-1]['number'],26);self.assertEqual(service.chapter('kjv','Rom',14)['verses'][-1]['number'],23)
  self.assertEqual(service.chapter('web','Rom',16)['verses'][-1]['number'],25);self.assertEqual(service.chapter('kjv','Rom',16)['verses'][-1]['number'],27)
 def test_parameterized_queries(self):
  for query in ["' OR 1=1 --",'"; DROP TABLE Verse;--']:
   self.assertEqual(service.search(query)['status'],'NO_MATCH')
  self.assertEqual(len(service.catalog()['books']),66)
 def test_search_and_pagination(self):
  a=service.search('love',limit=4);b=service.search('love',limit=4,offset=4);self.assertGreater(a['total'],4);self.assertEqual(a['total'],b['total']);self.assertTrue(set(r['reference'] for r in a['results']).isdisjoint(r['reference'] for r in b['results']))
 def test_quoted_phrase_and_book_filter(self):
  r=service.search('"God so loved"',book='John');self.assertTrue(any(x['reference']=='John.3.16' for x in r['results']));self.assertTrue(all(x['book']=='John' for x in r['results']))
 def test_invalid_query_limits(self):
  for kwargs in [{'query':''},{'query':'x','limit':1000},{'query':'x','offset':-1},{'query':'x','edition':'unknown'}]:
   with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):service.search(**kwargs)
 def test_invalid_native_references(self):
  for args in [('web','Unknown',1),('web','John',99),('unknown','Gen',1)]:
   with self.subTest(args=args),self.assertRaises(ValueError):service.chapter(*args)
 def test_readonly_exact_unicode_hash(self):
  with service.DATABASE.open('rb') as f:before=hashlib.file_digest(f,'sha256').hexdigest()
  for e in ['web','kjv','bsb']:
   for v in service.chapter(e,'John',3)['verses']:self.assertEqual(hashlib.sha256(v['text'].encode()).hexdigest(),v['text_sha256'])
  with service.DATABASE.open('rb') as f:self.assertEqual(hashlib.file_digest(f,'sha256').hexdigest(),before)
if __name__=='__main__':unittest.main(verbosity=2)
