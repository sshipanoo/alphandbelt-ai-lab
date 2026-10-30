import asyncio
import unittest
import numpy as np
from ai_lab import attention, online_attention, softmax, rrf, rag_retrieval, sample_speculative, advantages, IdempotentTasks, bounded_jobs, validate_shots


class LabTests(unittest.TestCase):
    def test_attention_hand_example(self):
        out=attention(np.array([[1.,0.]]),np.eye(2),np.diag([10.,20.]))
        np.testing.assert_allclose(out,[[6.697615493266568,6.604769013466863]],rtol=1e-12)

    def test_online_matches_dense_across_shapes_blocks(self):
        rng=np.random.default_rng(77)
        for nq,nk,d,dv in [(1,1,2,3),(3,7,4,6),(17,17,8,8),(4,11,2,1)]:
            q,k,v=rng.normal(size=(nq,d)),rng.normal(size=(nk,d)),rng.normal(size=(nk,dv))
            for block in [1,3,8,50]:
                np.testing.assert_allclose(online_attention(q,k,v,block),attention(q,k,v),atol=1e-12)

    def test_softmax_extreme_logits(self):
        np.testing.assert_allclose(softmax([10000,10000]),[.5,.5])

    def test_speculative_preserves_target_distribution_empirically(self):
        for p,q in [([.6,.3,.1],[.2,.5,.3]),([1.,0.],[0.,1.]),([.2,.8],[.2,.8])]:
            r=sample_speculative(p,q,100000,42)
            np.testing.assert_allclose(r['frequency'],p,atol=.008)

    def test_lora_merge(self):
        rng=np.random.default_rng(1)
        w,a,b,x=rng.normal(size=(8,5)),rng.normal(size=(2,5)),rng.normal(size=(8,2)),rng.normal(size=5)
        np.testing.assert_allclose((w+b@a)@x,w@x+b@(a@x),atol=1e-12)

    def test_group_normalization(self):
        np.testing.assert_array_equal(advantages([0,0,1,1]),[-1,-1,1,1])
        np.testing.assert_array_equal(advantages([1,1,1]),[0,0,0])

    def test_rrf_ranking(self):
        self.assertEqual(rrf([['A','B','C'],['B','D','A']])[0][0],'B')

    def test_retrieval_returns_supporting_document(self):
        self.assertEqual(rag_retrieval()[0]['title'],'Device token')

    def test_idempotency_retry_and_payload_conflict(self):
        db=IdempotentTasks()
        self.assertEqual(db.create('a','key','title'),db.create('a','key','title'))
        with self.assertRaises(ValueError):db.create('a','key','other')
        self.assertEqual(db.db.execute('SELECT count(*) FROM tasks').fetchone()[0],1)
        self.assertNotEqual(db.create('a','key','title'),db.create('b','key','title'))

    def test_bounded_concurrency(self):
        r=asyncio.run(bounded_jobs(9,3))
        self.assertEqual(r['peak'],3)
        self.assertEqual(r['values'],[i*i for i in range(9)])

    def test_storyboard_validation(self):
        shots=[{'id':str(i),'duration':6,'caption':'A scene'} for i in range(3)]
        self.assertTrue(validate_shots(shots))
        shots[1]['id']='0'
        with self.assertRaises(ValueError):validate_shots(shots)

    def test_kv_memory_formula(self):
        self.assertEqual(2*32*32768*8*128*2/2**30,4)


if __name__=='__main__':unittest.main(verbosity=2)
