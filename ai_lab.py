"""Small, deterministic teaching experiments. No model/API downloads or secrets."""
from collections import defaultdict
from pathlib import Path
import argparse
import asyncio
import hashlib
import json
import math
import platform
import sqlite3
import sys
import numpy as np


def softmax(x):
    x = np.asarray(x, dtype=np.float64)
    e = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def attention(q, k, v):
    return softmax(q @ k.T / math.sqrt(k.shape[-1])) @ v


def online_attention(q, k, v, block=3):
    """CPU demonstration of tiled forward attention with online normalization.

    Not a FlashAttention CUDA kernel, backward implementation, or speed benchmark.
    Scores use all queries against one key block at a time: O(n_query * block).
    """
    if block < 1 or len(k) == 0:
        raise ValueError('positive block and nonempty keys required')
    m = np.full((len(q), 1), -np.inf)
    den = np.zeros((len(q), 1))
    num = np.zeros((len(q), v.shape[-1]))
    for start in range(0, len(k), block):
        kb, vb = k[start:start+block], v[start:start+block]
        s = q @ kb.T / math.sqrt(k.shape[-1])
        new_m = np.maximum(m, s.max(axis=1, keepdims=True))
        rescale = np.exp(m-new_m)
        p = np.exp(s-new_m)
        den = den * rescale + p.sum(axis=1, keepdims=True)
        num = num * rescale + p @ vb
        m = new_m
    return num / den


def rrf(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        if len(ranking) != len(set(ranking)):
            raise ValueError('each ranking must contain unique document IDs')
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] += 1.0/(k+rank)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def rag_retrieval():
    """Lexical retrieval only. English corpus avoids implying Chinese segmentation."""
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE VIRTUAL TABLE docs USING fts5(title, body)')
        db.executemany('INSERT INTO docs VALUES (?, ?)', [
            ('Device token', 'The device token authenticates each device request.'),
            ('Audio format', 'Streaming speech returns PCM audio samples.'),
            ('Cache', 'A KV cache stores attention keys and values.'),
        ])
        rows = db.execute('SELECT rowid, title, body FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT 2',
                          ('device AND token',)).fetchall()
    return [{'id': row[0], 'title': row[1], 'text': row[2]} for row in rows]


def sample_speculative(p, q, count=100000, seed=42):
    """One-position speculative sampling. Exact correction, no LLM speed claims."""
    p, q = np.asarray(p, dtype=float), np.asarray(q, dtype=float)
    if p.shape != q.shape or np.any(p < 0) or np.any(q < 0):
        raise ValueError('matching, nonnegative distributions required')
    if not np.isclose(p.sum(), 1) or not np.isclose(q.sum(), 1):
        raise ValueError('distributions must sum to one')
    rng = np.random.default_rng(seed)
    draft = rng.choice(len(q), size=count, p=q)
    accepted = rng.random(count) < np.minimum(1, p[draft]/q[draft])
    out = draft.copy()
    residual = np.maximum(p-q, 0)
    rejected = int((~accepted).sum())
    if rejected:
        out[~accepted] = rng.choice(len(p), size=rejected, p=residual/residual.sum())
    return {'frequency': (np.bincount(out, minlength=len(p))/count).tolist(),
            'acceptance': float(accepted.mean()), 'samples': count, 'seed': seed}


def advantages(rewards):
    """Outcome-reward group normalization; population std, zero-variance guard."""
    x = np.asarray(rewards, dtype=float)
    sd = x.std(ddof=0)
    return np.zeros_like(x) if sd == 0 else (x-x.mean())/sd


class IdempotentTasks:
    """A local transactional example, not exactly-once for external services."""
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, tenant TEXT, key TEXT, digest TEXT, title TEXT, UNIQUE(tenant,key))')

    def create(self, tenant, key, title):
        digest = hashlib.sha256(json.dumps({'title': title}, sort_keys=True).encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO tasks(tenant,key,digest,title) VALUES(?,?,?,?)',
                            (tenant, key, digest, title))
            row = self.db.execute('SELECT id,digest FROM tasks WHERE tenant=? AND key=?', (tenant,key)).fetchone()
            if row[1] != digest:
                raise ValueError('idempotency key reused with different payload')
        return row[0]


async def bounded_jobs(count=9, limit=3):
    """Simulated I/O only; count concurrency, not model/API throughput."""
    sem = asyncio.Semaphore(limit)
    state = {'active': 0, 'peak': 0}
    async def one(i):
        async with sem:
            state['active'] += 1
            state['peak'] = max(state['peak'],state['active'])
            try:
                await asyncio.sleep(0.005)
                return i*i
            finally:
                state['active'] -= 1
    values = await asyncio.gather(*(one(i) for i in range(count)))
    return {'jobs': count, 'limit': limit, 'peak': state['peak'], 'values': values}


def validate_shots(shots, target_duration=18):
    if not shots:
        raise ValueError('empty storyboard')
    seen = set()
    for s in shots:
        if not isinstance(s['id'], str) or s['id'] in seen:
            raise ValueError('unique string shot IDs required')
        seen.add(s['id'])
        if not 0 < s['duration'] <= 10 or not s['caption'].strip():
            raise ValueError('invalid shot duration/caption')
        if len(s['caption']) > 24:
            raise ValueError('caption too long for this template')
    if not math.isclose(sum(s['duration'] for s in shots), target_duration):
        raise ValueError('storyboard duration mismatch')
    return True


def run_all():
    q = np.array([[1.,0.]])
    k = np.array([[1.,0.],[0.,1.]])
    v = np.array([[10.,0.],[0.,20.]])
    rng = np.random.default_rng(7)
    rq,rk,rv = rng.normal(size=(3,17,8))
    err = float(np.max(np.abs(attention(rq,rk,rv)-online_attention(rq,rk,rv))))
    w = rng.normal(size=(4,4))
    a,b,x = rng.normal(size=(1,4)),rng.normal(size=(4,1)),rng.normal(size=4)
    merge_error = float(np.max(np.abs((w+b@a)@x-(w@x+b@(a@x)))))
    spec = sample_speculative([.6,.3,.1],[.2,.5,.3])
    tasks = IdempotentTasks()
    first = tasks.create('demo','request-1','Write a tutorial')
    second = tasks.create('demo','request-1','Write a tutorial')
    return {
      'environment': {'python':sys.version.split()[0], 'numpy':np.__version__, 'platform':platform.system()},
      'attention': {'q':q.tolist(),'k':k.tolist(),'v':v.tolist(),'weights':softmax(q@k.T/math.sqrt(2)).tolist(),'output':attention(q,k,v).tolist()},
      'online_attention': {'shape':[17,8],'block':3,'max_abs_error':err,'scope':'CPU forward math only, not a CUDA implementation or speed benchmark'},
      'lora': {'shape':[4,4],'rank':1,'merge_max_abs_error':merge_error,'large_matrix_params':4096**2,'rank8_params':2*4096*8,'scope':'Matrix update and merge equivalence, not fine-tuning a language model'},
      'speculative': dict(spec, target=[.6,.3,.1],draft=[.2,.5,.3],scope='Single-position probability correction, not an LLM decoding benchmark'),
      'grpo': {'rewards':[0,0,1,1], 'advantages':advantages([0,0,1,1]).tolist(),'scope':'Group normalization only, not complete policy training'},
      'memory': {'kv_gib':2*32*1*32768*8*128*2/2**30,'weight_7b_fp16_gb':7e9*2/1e9,'weight_7b_q4_raw_gb':7e9*4/8/1e9},
      'rrf': rrf([['A','B','C'],['B','D','A']]),
      'retrieval':rag_retrieval(),
      'idempotency':{'first_id':first,'retry_id':second,'rows':tasks.db.execute('SELECT count(*) FROM tasks').fetchone()[0]},
      'concurrency':asyncio.run(bounded_jobs()),
      'cost_example':{'requests':1000,'input_tokens_each':4000,'output_tokens_each':500,'hypothetical_input_per_million':1,'hypothetical_output_per_million':4,'total':1000*(4000*1+500*4)/1e6},
    }


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='results/results.json')
    args=parser.parse_args()
    result=run_all()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
