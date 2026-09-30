"""Free transport-mocked image-provider and asset-provenance checks."""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", PORTFOLIO_AUTH_ENABLED="0")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from PIL import Image
from server import config, media, store
from server.llm import image_media as m

REAL_CLIENT=httpx.Client
buffer=io.BytesIO();Image.new("RGB",(4,4),"white").save(buffer,format="PNG");PNG=buffer.getvalue()


class MediaProviderTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.tmp=self.stack.enter_context(tempfile.TemporaryDirectory(prefix="media-provider-contract-"))
        for name,value in [('DATA_DIR',Path(self.tmp)),('MOCK_LLM',False),('RUNWARE_API_KEY','fixture-runware-value'),('PIXELBIN_API_TOKEN','fixture-pixelbin-value'),('MEDIA_PROVIDER_ORDER',['runware','pixelbin'])]:
            self.stack.enter_context(patch.object(config,name,value))
        for name in ['socket.create_connection','socket.socket.connect','socket.socket.connect_ex']:
            self.stack.enter_context(patch(name,side_effect=AssertionError('Outbound blocked by free test')))
        self.stack.enter_context(patch.object(m.time,'sleep',return_value=None))
        self.calls=[]

    def client(self,handler):
        def handle(request):self.calls.append(request);return handler(request)
        self.stack.enter_context(patch.object(m.httpx,'Client',side_effect=lambda **kw:REAL_CLIENT(transport=httpx.MockTransport(handle),**kw)))

    def success(self,request,**extra):
        task=json.loads(request.content)[0]
        return httpx.Response(200,json={'data':[{'taskUUID':task['taskUUID'],'imageBase64Data':base64.b64encode(PNG).decode(),**extra}]})

    def test_mock_opens_no_http_client(self):
        with patch.object(config,'MOCK_LLM',True),patch.object(m.httpx,'Client',side_effect=AssertionError('No HTTP in mock')):
            result=m.generate('Guide mascot')
        self.assertTrue(result.mocked);self.assertEqual(result.provider,'mock')

    def test_runware_primary_returns_validated_png_and_actual_cost(self):
        def handle(request):
            task=json.loads(request.content)[0]
            self.assertEqual(task['outputType'],'base64Data')
            self.assertEqual(task['numberResults'],1)
            self.assertEqual(task['model'],'google:4@3')
            self.assertTrue(task['safety']['checkContent'])
            return self.success(request,cost=.0689)
        self.client(handle);result=m.generate('Guide mascot')
        self.assertEqual(result.provider,'runware');self.assertEqual(result.usd,.0689)
        self.assertEqual(len(self.calls),1);self.assertEqual(Image.open(io.BytesIO(result.png)).format,'PNG')

    def test_primary_failure_uses_pixelbin_binary_reference_and_fixed_poll_origin(self):
        reference=Path(self.tmp)/'input.png';reference.write_bytes(PNG)
        def handle(request):
            if request.url.host=='api.runware.ai':return httpx.Response(503,json={'private':'body must not be logged'})
            if request.method=='POST':
                self.assertEqual(request.headers['authorization'],'Bearer '+base64.b64encode(b'fixture-pixelbin-value').decode())
                self.assertIn(b'name="input.images"; filename="reference.png"',request.content)
                return httpx.Response(200,json={'_id':'fixture_prediction','status':'PENDING','urls':{'get':'http://169.254.169.254/private'}})
            if request.url.host=='api.pixelbin.io':
                self.assertEqual(str(request.url),m.PIXELBIN_URL+'/fixture_prediction')
                return httpx.Response(200,json={'_id':'fixture_prediction','status':'SUCCESS','output':['https://delivery.pixelbin.io/predictions/outputs/test.png'],'consumedCredits':3})
            self.assertNotIn('authorization',request.headers)
            return httpx.Response(200,content=PNG)
        self.client(handle)
        with self.assertLogs('uvicorn.error',level='INFO') as logs:result=m.generate('Clean product background',reference=reference,aspect='4:3')
        self.assertEqual(result.provider,'pixelbin');self.assertEqual(result.credits,3);self.assertIsNone(result.usd)
        self.assertEqual(len(self.calls),4)
        text='\n'.join(logs.output)
        self.assertIn('"status": "fallback"',text);self.assertIn('"provider": "pixelbin"',text)
        self.assertNotIn('fixture-pixelbin-value',text);self.assertNotIn('body must not be logged',text)

    def test_safety_refusal_does_not_try_another_provider(self):
        self.client(lambda req:self.success(req,NSFWContent=True))
        with self.assertRaises(m.SafetyRefusal):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)

    def test_http_safety_refusal_is_terminal_and_redacted(self):
        self.client(lambda req:httpx.Response(422,json={'errors':[{'code':'content_policy_violation','message':'private rejected prompt'}]}))
        with self.assertLogs('uvicorn.error',level='INFO') as logs,self.assertRaises(m.SafetyRefusal):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)
        self.assertNotIn('private rejected prompt','\n'.join(logs.output))

    def test_unclassified_bad_request_cannot_bypass_refusal(self):
        self.client(lambda req:httpx.Response(400,json={'errors':[{'code':'newUnknownCode'}]}))
        with self.assertRaises(m.RequestRejected):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)

    def test_authenticated_redirect_is_not_followed(self):
        config.MEDIA_PROVIDER_ORDER=['pixelbin']
        self.client(lambda req:httpx.Response(302,headers={'Location':'https://attacker.invalid/collect'}))
        with self.assertRaises(m.MediaError):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)

    def test_external_prediction_output_is_rejected_before_download(self):
        config.MEDIA_PROVIDER_ORDER=['pixelbin']
        self.client(lambda req:httpx.Response(200,json={'_id':'fixture_prediction','status':'SUCCESS','output':['http://169.254.169.254/latest/meta-data']}))
        with self.assertRaises(m.MediaError):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)

    def test_unknown_poll_status_stops_without_retrying_generation(self):
        config.MEDIA_PROVIDER_ORDER=['pixelbin']
        self.client(lambda req:httpx.Response(200,json={'_id':'fixture_prediction','status':'unexpected'}))
        with self.assertRaises(m.MediaError):m.generate('Guide mascot')
        self.assertEqual(len(self.calls),1)

    def test_oversized_response_is_bounded(self):
        config.MEDIA_PROVIDER_ORDER=['runware']
        self.client(lambda req:httpx.Response(200,content=b'x'*100))
        with patch.object(m,'MAX_JSON_BYTES',32),self.assertRaises(m.MediaError):m.generate('Guide mascot')

    def test_mismatched_task_output_is_rejected(self):
        config.MEDIA_PROVIDER_ORDER=['runware']
        self.client(lambda req:httpx.Response(200,json={'data':[{'taskUUID':'another-task','imageBase64Data':base64.b64encode(PNG).decode()}]}))
        with self.assertRaises(m.MediaError):m.generate('Guide mascot')

    def test_invalid_image_bytes_are_not_written(self):
        with self.assertRaises(m.MediaError):m._png(b'not an image')

    def test_cached_product_cleanup_retains_provider_badge_without_second_call(self):
        did=store.new_demo('Synthetic product')['id'];source={'id':'src1','kind':'image','name':'fixture.png','path':'sources/fixture.png','use_in_demo':True}
        store.path(did,source['path']).write_bytes(PNG)
        store.update(did,lambda d:d.update(sources=[source],settings={**d['settings'],'enhance_images':'ai'}))
        result=m.ImageResult(m._png(PNG),'pixelbin','nanoBanana_generate',credits=3)
        with patch.object(media,'needs_cleanup',return_value=(True,'Synthetic fixture')),patch.object(m,'generate',return_value=result) as generation:
            media.enhance_images(did)
            media.enhance_images(did)
        self.assertEqual(generation.call_count,1)
        enhanced=store.load(did)['sources'][0]['enhanced']
        self.assertEqual(enhanced['provider'],'pixelbin');self.assertEqual(enhanced['credits'],3)
        self.assertEqual(store.path(did,source['path']).read_bytes(),PNG)

    def test_generated_mascot_records_provider_on_demo(self):
        did=store.new_demo('Synthetic guide')['id']
        with patch.object(m,'generate',return_value=m.ImageResult(m._png(PNG),'runware','google:4@3',usd=.0689)) as generation:
            self.assertEqual(media.generate_mascot(did,{}),'media/mascot.png')
            self.assertEqual(media.generate_mascot(did,{}),'media/mascot.png')
        self.assertEqual(generation.call_count,1)
        self.assertEqual(store.load(did)['mascot_provider'],'runware')

if __name__=='__main__':unittest.main()
