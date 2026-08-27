import unittest
from pa800_optimizer.analysis.factory_atomic import FactoryAtomicKnowledge
from pa800_optimizer.manual import DncManualRegistry

class FactoryAtomicMaxTests(unittest.TestCase):
    def test_corpus_is_complete(self):
        a=FactoryAtomicKnowledge(); self.assertTrue(a.available)
        c=a.corpus(); self.assertEqual(c['styles'],252); self.assertEqual(c['notes'],1430602); self.assertGreaterEqual(c['segments'],31000)
    def test_variation_orchestration_growth(self):
        a=FactoryAtomicKnowledge(); v1=a.element('Variation 1');v4=a.element('Variation 4')
        self.assertLess(v1['role_presence']['ACC5'],v4['role_presence']['ACC5'])
        self.assertLess(v1['active_roles']['p50'],v4['active_roles']['p50'])
    def test_cv_and_variation_knowledge_present(self):
        a=FactoryAtomicKnowledge(); p=a.variation_progression('V1->V2','DRUM')
        self.assertIsNotNone(p); self.assertGreaterEqual(p['rhythm_jaccard']['p50'],0.9)
    def test_controller_forensics(self):
        a=FactoryAtomicKnowledge(); self.assertEqual(a.controller_count(22),125493);self.assertEqual(a.pitchbend_count(),52542)
        self.assertEqual(a.controller_count(81),0)
    def test_manual_dnc_registry_is_separate(self):
        d=DncManualRegistry(); self.assertEqual(len(d.data['sounds']),23)
        self.assertIn(80,d.controller_ccs());self.assertIn(81,d.controller_ccs())

if __name__=='__main__':unittest.main()