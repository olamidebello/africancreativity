import unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from domain_config import discover

class DomainDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('sites-enabled','sites-available','conf.d'):(self.root/name).mkdir()
    def tearDown(self):self.tmp.cleanup()
    def test_new_hostname_has_inactive_dedicated_destination(self):
        result=discover('olamideolatayobello.com',self.root)
        self.assertFalse(result['active']);self.assertEqual(Path(result['config']).name,'olamideolatayobello.com')
    def test_symlink_resolves_to_existing_dedicated_vhost(self):
        config=self.root/'sites-available/site';config.write_text('server { server_name olamideolatayobello.com www.olamideolatayobello.com; }')
        (self.root/'sites-enabled/site').symlink_to(config)
        result=discover('olamideolatayobello.com',self.root)
        self.assertTrue(result['active']);self.assertEqual(result['config'],str(config))
    def test_unrelated_domain_is_not_selected(self):
        (self.root/'conf.d/medical.conf').write_text('server { server_name olamidemedical.health; }')
        self.assertFalse(discover('olamideolatayobello.com',self.root)['active'])
    def test_shared_config_is_rejected(self):
        (self.root/'conf.d/shared.conf').write_text('server { server_name olamideolatayobello.com other.example; }')
        with self.assertRaises(ValueError):discover('olamideolatayobello.com',self.root)
    def test_duplicate_active_configs_are_rejected(self):
        for name in ('a','b'):(self.root/'sites-enabled'/name).write_text('server { server_name olamideolatayobello.com; }')
        with self.assertRaises(ValueError):discover('olamideolatayobello.com',self.root)
    def test_invalid_hostname_is_rejected(self):
        for name in ('https://olamideolatayobello.com','../example.com','test;nginx.example'):
            with self.assertRaises(ValueError):discover(name,self.root)

if __name__=='__main__':unittest.main()
