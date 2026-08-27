import unittest
from pa800_optimizer.profiles.registry import ProfileRegistry
class T(unittest.TestCase):
    def test_standard_rx3_key36(self):
        r=ProfileRegistry(); p=r.resolve_drum_key(120,0,2,36)
        self.assertIsNotNone(p); self.assertGreater(p['support']['hits'],1000)
        self.assertEqual(p['key'],36)
if __name__=='__main__':unittest.main()