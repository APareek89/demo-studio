"""Feedback attachments remain reusable after partial upload/provider failures."""
from __future__ import annotations
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

TMP=tempfile.TemporaryDirectory(prefix='feedback-upload-retry-')
os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=TMP.name,DEMO_STUDIO_GRAPH_DB=str(Path(TMP.name)/'graph.sqlite'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
OUTBOUND=[]
def blocked(*args,**kwargs):
    OUTBOUND.append(True);raise AssertionError('No outbound service calls')
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=blocked
from fastapi.testclient import TestClient
from server import graph,orchestrator,store
from server.app import app

class UploadRetryContract(unittest.TestCase):
    def setUp(self):
        self.did=store.new_demo('Retry-safe feedback upload')['id']
        self.api=TestClient(app)
        self.url=f'/api/demos/{self.did}/align'
    def tearDown(self): self.assertEqual(OUTBOUND,[])
    def send(self,files,context='rehearse'):
        return self.api.post(self.url,data={'message':'Use this source','context':context},files=[('files',(name,data,'text/plain')) for name,data in files])
    def sources(self):return store.load(self.did)['sources']
    def test_busy_worker_rejects_before_any_upload(self):
        with patch.object(graph,'is_running',return_value=True),patch.object(graph,'handle_message') as handle:
            self.assertEqual(self.send([('evidence.txt',b'Approved details')]).status_code,409)
        self.assertEqual(self.sources(),[]);self.assertEqual(list(store.path(self.did,'sources').iterdir()),[]);handle.assert_not_called()
    def test_persisted_busy_stage_rejects_before_any_upload(self):
        store.update(self.did,lambda d:d.update(running='understand'))
        self.assertEqual(self.send([('evidence.txt',b'Approved details')]).status_code,409)
        self.assertEqual(self.sources(),[])
    def test_partial_multifile_failure_retry_reuses_first_source(self):
        with patch.object(graph,'handle_message',return_value={'reply':'Review in Align'}) as handle:
            self.assertEqual(self.send([('first.txt',b'First source'),('second.txt',b'')]).status_code,400)
            first=self.sources()[0]
            self.assertEqual(handle.call_count,0)
            self.assertEqual(self.send([('first.txt',b'First source'),('second.txt',b'Second source')]).status_code,200)
            self.assertEqual(len(self.sources()),2)
            self.assertEqual(self.sources()[0],first)
            self.assertEqual([x['id'] for x in handle.call_args.args[2]],[x['id'] for x in self.sources()])
            self.assertEqual(len(list(store.path(self.did,'sources').iterdir())),2)
    def test_provider_failure_retry_keeps_existing_identity_and_bytes(self):
        with patch.object(graph,'handle_message',side_effect=RuntimeError('Provider did not answer')):
            self.assertEqual(self.send([('proof.txt',b'Grounded proof')]).status_code,409)
            first=self.sources()[0]
            self.assertEqual(self.send([('proof.txt',b'Grounded proof')]).status_code,409)
        self.assertEqual(self.sources(),[first])
        self.assertEqual(store.path(self.did,first['path']).read_bytes(),b'Grounded proof')
    def test_timeout_never_rolls_back_source_a_worker_may_use(self):
        captured=[]
        def timeout(did,message,attachments,context):
            captured.extend(attachments);raise RuntimeError('The agent did not answer in time')
        with patch.object(graph,'handle_message',side_effect=timeout):self.send([('source.txt',b'Read in progress')])
        self.assertEqual(self.sources(),captured)
        self.assertTrue(store.path(self.did,captured[0]['path']).is_file())
    def test_same_name_and_size_different_content_never_reused(self):
        with patch.object(graph,'handle_message',return_value={'reply':'Review'}):
            self.send([('proof.txt',b'First')]);self.send([('proof.txt',b'Other')])
        self.assertEqual(len(self.sources()),2)
        self.assertEqual({store.path(self.did,s['path']).read_bytes() for s in self.sources()},{b'First',b'Other'})
    def test_different_name_or_role_never_reused(self):
        a=store.add_stream_source(self.did,'a.txt',io.BytesIO(b'Same'),reuse_identical=True)
        b=store.add_stream_source(self.did,'b.txt',io.BytesIO(b'Same'),reuse_identical=True)
        c=store.add_stream_source(self.did,'a.txt',io.BytesIO(b'Same'),'brand',reuse_identical=True)
        self.assertEqual(len({a['id'],b['id'],c['id']}),3)
    def test_old_source_without_hash_can_be_reused(self):
        old=store.add_file_source(self.did,'old.txt',b'Existing source')
        with patch.object(graph,'handle_message',return_value={'reply':'Review'}):self.send([('old.txt',b'Existing source')])
        self.assertEqual(self.sources(),[old])
    def test_sources_endpoint_retains_explicit_add_semantics(self):
        for _ in range(2):
            result=self.api.post(f'/api/demos/{self.did}/sources',data={'role':'product'},files=[('files',('same.txt',b'Explicit source','text/plain'))])
            self.assertEqual(result.status_code,200)
        self.assertEqual(len(self.sources()),2)
    def test_concurrent_feedback_uploads_reuse_under_demo_lock(self):
        def upload(_):return store.add_stream_source(self.did,'race.txt',io.BytesIO(b'Complete bytes'*10000),reuse_identical=True)
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(upload,range(4)))
        self.assertEqual(len({r['id'] for r in rows}),1)
        self.assertEqual(len(self.sources()),1)
        self.assertEqual(len(list(store.path(self.did,'sources').iterdir())),1)
    def test_rehearse_attachments_without_model_actions_schedule_understand(self):
        attached=store.add_file_source(self.did,'support.txt',b'New approved-source candidate')
        requests={}
        notes=orchestrator.apply_actions(self.did,[],[attached],'rehearse',requests)
        self.assertEqual(requests['revise'][0],'understand')
        self.assertIn('support.txt',requests['revise'][1])
        self.assertNotIn('build',requests)
        self.assertFalse(any(store.load(self.did)['approvals'].values()))
        self.assertIsNone(store.read_json(self.did,'bundle.json'))
    def test_attachment_graph_route_requires_review_without_publishing(self):
        attached=store.add_file_source(self.did,'support.txt',b'New candidate')
        requests={};orchestrator.apply_actions(self.did,[],[attached],'rehearse',requests)
        with patch.object(orchestrator,'respond',return_value=('Review new material',[],[],requests)):
            result=graph.align_wait({'demo_id':self.did,'pending':{'type':'message','message':'Read it','attachments':[attached],'context':'rehearse'}})
        self.assertEqual(result.goto,'understand')
        self.assertEqual(result.update['entry'],'revise')
        self.assertEqual(graph.after_author({'demo_id':self.did,'entry':'revise'}),'faq')
        self.assertEqual(graph.after_faq({'demo_id':self.did,'entry':'revise','rebuild':True}),'align_enter')
        self.assertIsNone(store.read_json(self.did,'bundle.json'))

if __name__=='__main__':unittest.main()
