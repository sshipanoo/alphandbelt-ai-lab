"""Explicit local-model smoke checks; requires a downloaded qwen3:0.6b.

python ollama_check.py --base-url http://127.0.0.1:11434
No cloud endpoint, credentials, or automatic model download.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
import argparse,json

def run(base):
    if urlsplit(base).hostname not in ['localhost','127.0.0.1','::1']:
        raise ValueError('This teaching script only calls loopback addresses')
    def call(path,body=None):
        req=Request(base.rstrip('/')+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=180) as response:return json.load(response)
    model='qwen3:0.6b'
    common={'model':model,'stream':False,'think':False,'options':{'temperature':0,'num_predict':128,'num_ctx':2048}}
    basic=call('/api/generate',dict(common,prompt='用一句话解释HTTP。'))
    assert basic['done'] and basic['response'].strip()
    schema={'type':'object','properties':{'title':{'type':'string'},'priority':{'type':'string','enum':['low','normal','high']}},'required':['title','priority'],'additionalProperties':False}
    structured=call('/api/generate',dict(common,prompt='提取任务：尽快整理发票。title写任务名称，priority用high。只输出JSON。',format=schema))
    obj=json.loads(structured['response'])
    assert isinstance(obj.get('title'),str) and obj['title'].strip()
    assert obj.get('priority') in ['low','normal','high']
    messages=[{'role':'user','content':'必须调用add工具计算17+25，然后告诉我结果。'}]
    tools=[{'type':'function','function':{'name':'add','description':'Add two integers. Use this for all addition calculations.','parameters':{'type':'object','properties':{'a':{'type':'integer'},'b':{'type':'integer'}},'required':['a','b']}}}]
    proposal=call('/api/chat',dict(common,messages=messages,tools=tools))
    messages.append(proposal['message'])
    calls=proposal['message'].get('tool_calls',[])
    executed=[]
    for item in calls:
        fn=item['function']
        if fn['name']!='add':raise ValueError('unapproved tool')
        args=fn['arguments']
        if set(args)!={'a','b'} or any(type(args[k]) is not int for k in ['a','b']):raise ValueError('invalid add arguments')
        result=args['a']+args['b']
        executed.append({'name':'add','arguments':args,'result':result})
        messages.append({'role':'tool','tool_name':'add','content':json.dumps({'result':result})})
    if calls:
        final=call('/api/chat',dict(common,messages=messages))
        messages.append(final['message'])
    else:
        final={'message':{'content':'Model did not call a tool; this run is not a successful tool-calling check.'}}
    return {'scope':'Local smoke checks, not an evaluation benchmark','version':call('/api/version'),
        'model':model,'models':[{'name':x['name'],'digest':x['digest']} for x in call('/api/tags')['models']],
        'basic':{'request_prompt':'用一句话解释HTTP。','response':basic['response'],'done':basic['done']},
        'structured':{'schema':schema,'response':obj,'shape_check':'passed'},
        'tool_call':{'passed':bool(executed) and executed[0]['result']==42,'executed':executed,'messages':messages,'final':final['message']['content']}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:11434');args=p.parse_args()
    data=run(args.base_url)
    out=Path(__file__).resolve().parent/'results'/'ollama-check.json'
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps(data,ensure_ascii=False,indent=2))
