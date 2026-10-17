import unittest,base64,json
from unittest.mock import patch
import providers
from database import Problem
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1EAAAAASUVORK5CYII=')
class ProviderContracts(unittest.TestCase):
 def test_text_extracts_response_output(self):
  with patch.object(providers,'openai',return_value={'output':[{'content':[{'type':'output_text','text':'Original line'}]}]}) as call:
   self.assertEqual(providers.assist('lyrics','A hopeful song'),'Original line');self.assertFalse(call.call_args.args[1]['store'])
 def test_storyboard_rejects_malformed_provider_output(self):
  with patch.object(providers,'openai',return_value={'output':[{'content':[{'type':'output_text','text':'{"scenes": []}'}]}]}):
   with self.assertRaises(Problem):providers.assist('storyboard','A story')
 def test_image_uses_base64_not_arbitrary_remote_url(self):
  with patch.object(providers,'openai',return_value={'data':[{'b64_json':base64.b64encode(PNG).decode()}]}):self.assertEqual(providers.image({'prompt':'An original landscape'}),PNG)
  with patch.object(providers,'openai',return_value={'data':[{'url':'https://untrusted.example/image'}]}):
   with self.assertRaises(Problem):providers.image({'prompt':'An original landscape'})
 def test_motion_tracks_provider_job_then_downloads_content(self):
  with patch.object(providers,'capabilities',return_value={'ai_motion_video':True}),patch.object(providers,'openai',side_effect=[{'id':'video_test','status':'completed'},b'test mp4']) as call:
   ids=[];self.assertEqual(providers.motion({'prompt':'A fictional landscape','aspect':'9:16'},ids.append),b'test mp4');self.assertEqual(ids,['video_test']);self.assertEqual(call.call_args_list[0].args[1]['size'],'720x1280');self.assertEqual(call.call_args_list[1].args[0],'videos/video_test/content')
 def test_motion_disabled_does_not_call_provider(self):
  with patch.object(providers,'capabilities',return_value={'ai_motion_video':False}),patch.object(providers,'openai') as call:
   with self.assertRaises(Problem):providers.motion({'prompt':'test'},lambda x:None)
   call.assert_not_called()
