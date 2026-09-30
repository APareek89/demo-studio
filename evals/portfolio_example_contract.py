"""Free example contract: real factory/routes, isolated disk, poisoned paid adapters."""
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM='1', PORTFOLIO_AUTH_ENABLED='0', PYTHON_DOTENV_DISABLED='1', CLOUD_SYNC='0', STORAGE_BACKEND='local')
for key in ('ANTHROPIC_API_KEY','OPENAI_API_KEY','GEMINI_API_KEY','RUNWARE_API_KEY','SARVAM_API_KEY','GCLOUD_TTS_API_KEY','PIXELBIN_API_TOKEN'):
    os.environ[key] = ''
scratch = tempfile.TemporaryDirectory(prefix='demo-example-contract-')
os.environ.update(DEMO_STUDIO_DATA=scratch.name+'/demos', DEMO_STUDIO_GRAPH_DB=scratch.name+'/graph.sqlite')
from fastapi.testclient import TestClient
from server import app as server, config, portfolio_example as examples, store


class FreeExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('No provider network allowed'))
        cls.network.start()
        cls.client = TestClient(server.app)
        cls.demo = examples.create_example(None, synthetic=True)
        cls.did = cls.demo['id']
        cls.base = '/api/demos/'+cls.did
        cls.initial_records = {name:list(store.path(cls.did,name).glob('*')) for name in ('sessions','leads','logs')}
        # Disable the provider mock switch as well: the cached policy itself,
        # not global mock behavior, must keep every visitor action free.
        cls.live = patch.object(config, 'MOCK_LLM', False)
        cls.live.start()

    @classmethod
    def tearDownClass(cls):
        cls.live.stop(); cls.network.stop(); scratch.cleanup()

    def test_private_copy_and_normal_publication(self):
        self.assertEqual(self.demo['status'], 'ready')
        published = self.client.get(self.base+'/bundle').json()
        self.assertTrue(published['example']['cached_only'])
        self.assertTrue(published['example']['silent'])
        self.assertGreaterEqual(published['runtime']['narration_minimum']['measured_seconds'], 180)
        self.assertFalse(published['runtime']['continuous_voice'])
        self.assertEqual(published['runtime']['tools'], [])
        self.assertEqual(published['ctas'], [])
        self.assertNotIn('(mock)', str(published))
        for directory in ('sessions','leads','logs'):
            self.assertEqual(self.initial_records[directory], [])
        self.assertNotIn('source_demo_id', self.demo)

    def test_runtime_actions_cannot_invoke_paid_paths(self):
        from server import runtime_graph
        with patch.object(runtime_graph,'run_turn',side_effect=AssertionError('Paid graph')), \
             patch.object(server.qa,'answer',side_effect=AssertionError('Paid answer')), \
             patch.object(server.pitch,'plan_pitch',side_effect=AssertionError('Paid pitch')), \
             patch.object(server.voice,'render_line',side_effect=AssertionError('Paid TTS')), \
             patch.object(server.sarvam,'stt',side_effect=AssertionError('Paid STT')):
            body={'session_id':'s_fixture','question':'Where are the driver seat controls?', 'voice_it':True, 'skip_bank':True,
                  'cached_only':False, 'example_kind':None, 'runtime_version':1}
            response=self.client.post(self.base+'/run/qa',json=body)
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.json()['cached_only'])
            self.assertTrue(response.json()['fact_ids'])
            body['question']='Predict next year’s stock market returns'
            self.assertFalse(self.client.post(self.base+'/run/qa',json=body).json()['answered'])
            self.assertTrue(self.client.post(self.base+'/run/pitch',json=body).json()['cached_only'])
            response=self.client.post(self.base+'/run/tts',json={**body,'text':'Unprepared arbitrary speech'})
            self.assertEqual(response.status_code,200)
            self.assertIsNone(response.json()['url'])
            response=self.client.post(self.base+'/run/stt',data={'session_id':'s_fixture'},files={'file':('audio.wav',b'x'*2048,'audio/wav')})
            self.assertEqual(response.status_code,409)
            response=self.client.post(self.base+'/run/lead',json={**body,'phone':'9876543210','consent':True})
            self.assertEqual(response.status_code,409)

    def test_bmw_literal_engine_answer_and_prepared_limit(self):
        demo=examples.create_example(None)
        base='/api/demos/'+demo['id']
        from server import runtime_graph
        with patch.object(runtime_graph,'run_turn',side_effect=AssertionError('Paid graph')):
            response=self.client.post(base+'/run/qa',json={'question':'What engine does the BMW X7 use?','session_id':'s_bmw'})
            self.assertEqual(response.status_code,200)
            answer=response.json()
            self.assertTrue(answer['answered'])
            self.assertIn('F077',answer['fact_ids'])
            self.assertIn('xDrive40i',answer['answer'])
            self.assertIn('6-cylinder',answer['answer'])
            response=self.client.post(base+'/run/qa',json={'question':'Explain quantum teleportation','session_id':'s_bmw'})
            self.assertFalse(response.json()['answered'])
            self.assertIn('prepared content',response.json()['answer'])
            self.assertFalse(response.json()['offer_callback'])

    def test_exact_authored_audio_and_generic_recap(self):
        published=store.read_json(self.did,'bundle.json')
        overview=published['runtime']['overview']
        self.assertEqual(examples.cached_audio(self.did,overview['text']),overview['audio'])
        self.assertIsNone(examples.cached_audio(self.did,overview['text']+' changed'))
        with patch.object(server._summary,'summarize',side_effect=AssertionError('Paid summary')) as paid:
            response=self.client.post(self.base+'/run/session',json={'id':'s_free','ended':True,'save_seq':1,'questions':['seating controls'],'transcript':[]})
            self.assertEqual(response.status_code,200)
            for _ in range(50):
                saved=server.storage.backend().get_session(self.did,'s_free')
                if saved.get('summary'): break
                time.sleep(.01)
            self.assertEqual(saved['summary']['model'],'none-cached-example')
            paid.assert_not_called()

    def test_caller_cannot_remove_server_policy(self):
        response=self.client.patch(self.base,json={'example_kind':None,'cached_only':False,'settings':{'example_kind':None}})
        self.assertEqual(response.status_code,200)
        self.assertTrue(examples.is_cached_only(self.did))


if __name__=='__main__':
    unittest.main()
