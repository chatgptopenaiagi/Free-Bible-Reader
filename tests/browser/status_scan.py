"""Bounded, read-only public hub status vocabulary verification."""
import json,pathlib,sys,datetime
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from bridge import hub
observed={}
def walk(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('status','mapping_status','match_status') and isinstance(item,str):observed.setdefault(key,set()).add(item)
            walk(item)
    elif isinstance(value,list):
        for item in value:walk(item)
reports=[hub.query({'reference':'John1:1','edition_id':edition,'engine':'all','limit':2}) for edition in ['crossreferences:KJV','crossreferences:BSB','crossreferences:AOV']]
reports.append(hub.query({'reference':'John999:1','edition_id':'crossreferences:KJV','engine':'all','limit':2}))
for report in reports:walk(report)
catalogs={code:json.loads((ROOT/'ui-core/i18n'/f'{code}.json').read_text(encoding='utf-8')) for code in ['en','ro','de']}
required=sorted(set().union(*observed.values()))
missing={code:[value for value in required if 'status.'+value not in catalog] for code,catalog in catalogs.items()}
report={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FAIL' if any(missing.values()) else 'PASS','scope':'Actual public hub queries; read-only native databases, not an installed-executable test','queries':4,'codes_by_field':{key:sorted(value) for key,value in observed.items()},'missing_catalog_status_keys':missing}
folder=ROOT/'evidence/browser';folder.mkdir(parents=True,exist_ok=True)
(folder/'visible-status-scan.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
