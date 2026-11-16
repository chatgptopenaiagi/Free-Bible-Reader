import json, sqlite3, time, pathlib, sys, sysconfig

def run(root):
    started = time.perf_counter()
    output = []
    for filename, edition in [('reader.sqlite','web'),('romanian.sqlite','ronbl')]:
        db = sqlite3.connect(pathlib.Path(root, 'data', filename).resolve().as_uri()+'?mode=ro', uri=True)
        verses = db.execute('SELECT verse,text FROM Verse WHERE edition=? AND book=? AND chapter=? ORDER BY rowid',(edition,'John',3)).fetchall()
        hits = db.execute('SELECT count(*) FROM Verse WHERE edition=? AND text LIKE ?', (edition,'%dragoste%' if edition=='ronbl' else '%love%')).fetchone()[0]
        output.append({'edition':edition,'chapter_count':len(verses),'sample':verses[15] if len(verses)>15 else None,'search_count':hits})
        db.close()
    memory = sqlite3.connect(':memory:')
    try:
        memory.execute('CREATE VIRTUAL TABLE f USING fts5(text)')
        fts5 = True
    except sqlite3.OperationalError: fts5 = False
    return json.dumps({'status':'PASS','engine':'chaquopy-python3.14','python':sys.version,'build_abi':sysconfig.get_config_var('HOST_GNU_TYPE'),'results':output,'fts5':fts5,'elapsed_ms':(time.perf_counter()-started)*1000},ensure_ascii=False)
