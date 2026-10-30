"""Runnable examples for the non-paper engineering posts."""
from collections import defaultdict
import hashlib,json,sqlite3
from pathlib import Path

def deduplicate(records):
    unique={}
    for item in records:
        text=' '.join(item['text'].split())
        key=hashlib.sha256(text.encode()).hexdigest()
        if key not in unique:unique[key]={'text':text,'sources':[]}
        unique[key]['sources'].append(item['source'])
    return list(unique.values())

def parent_lookup():
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE parents(id INTEGER PRIMARY KEY,text TEXT)')
        db.executemany('INSERT INTO parents VALUES(?,?)',[(1,'Within 7 days AND unopened.'),(2,'Warranty policy.')])
        hits=[{'parent_id':2},{'parent_id':1},{'parent_id':2}]
        ids=list(dict.fromkeys(hit['parent_id'] for hit in hits))
        marks=','.join('?' for _ in ids)
        rows=db.execute(f'SELECT id,text FROM parents WHERE id IN ({marks})',ids).fetchall()
        by_id=dict(rows)
        return [{'id':i,'text':by_id[i]} for i in ids]

def validate_task(text):
    obj=json.loads(text)
    if not isinstance(obj,dict):raise ValueError('object required')
    if not isinstance(obj.get('title'),str) or not obj['title'].strip():raise ValueError('title required')
    if obj.get('priority') not in {'low','normal','high'}:raise ValueError('invalid priority')
    return obj

def budget_check(spent,budget,input_tokens,max_output_tokens,input_price,output_price):
    upper=(input_tokens*input_price+max_output_tokens*output_price)/1_000_000
    if spent+upper>budget:raise RuntimeError('batch budget exceeded')
    return upper

if __name__=='__main__':
    records=[{'text':'device  token','source':'a'},{'text':' device token ','source':'b'},{'text':'audio PCM','source':'c'}]
    clean=deduplicate(records)
    assert len(clean)==2 and clean[0]['sources']==['a','b']
    assert [x['id'] for x in parent_lookup()]==[2,1]
    assert validate_task('{"title":"Write","priority":"high"}')['priority']=='high'
    for bad in ['[]','{"title":"","priority":"high"}','{"title":"Write","priority":"urgent"}']:
        try:validate_task(bad)
        except ValueError:pass
        else:raise AssertionError('invalid data was accepted')
    assert budget_check(0,1,4000,500,1,4)==.006
    try:budget_check(1,1,4000,500,1,4)
    except RuntimeError:pass
    else:raise AssertionError('budget gate failed')
    result={'dedup':{'before':3,'after':len(clean),'records':clean},'parent_lookup':parent_lookup(),'validation':'valid accepted; 3 invalid cases rejected','budget':'estimate .006; over-budget case rejected'}
    (Path(__file__).resolve().parent/'results'/'practical-checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
