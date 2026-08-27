import unittest
from pa800_optimizer.profiles.registry import ProfileRegistry
class T(unittest.TestCase):
    def test_required_json_is_cached_across_registry_instances(self):
        a=ProfileRegistry();b=ProfileRegistry();self.assertIs(a,b);self.assertIs(a.profiles,b.profiles)
    def test_load(self):
        r=ProfileRegistry(); self.assertGreater(len(r.profiles),500)
    def test_finger_bass_rx(self):
        r=ProfileRegistry(); p,s=r.resolve_identity(121,13,33,'BASS'); self.assertIsNotNone(p); self.assertIn('Finger Bass RX',p['identity']['sound'])
    def test_conflicts_guarded(self):
        r=ProfileRegistry(); p,s=r.resolve_identity(120,0,35,'DRUM'); self.assertIsNone(p); self.assertTrue(s.startswith('IDENTITY_CONFLICT'))
    def test_family_velocity_fallback_exists_for_gm_song_instruments(self):
        r=ProfileRegistry()
        for family in ('PIANO','BASS','GUITAR','STRINGS','BRASS'):
            p=r.velocity_family_profile(family,'SONG');self.assertIsNotNone(p);self.assertGreater(p['velocity']['ideal_center'],0)
    def test_positive_instrument_models_are_holdout_gated(self):
        r=ProfileRegistry()
        self.assertTrue(r.instrument_positive_model_allowed('PIANO',(121,3,0),'coherent_chord_timing'))
        self.assertTrue(r.instrument_positive_model_allowed('BASS',(121,7,33),'drum_anchor_timing'))
        self.assertTrue(r.instrument_positive_model_allowed('ENSEMBLE',(121,2,50),'coherent_phrase_velocity'))
        self.assertTrue(r.instrument_positive_model_allowed('ENSEMBLE',(121,5,48),'coherent_sustain_chord_timing'))
        self.assertTrue(r.instrument_positive_model_allowed('REED',(121,1,71),'breath_phrase_velocity'))
        self.assertFalse(r.instrument_positive_model_allowed('GUITAR',(121,8,24),'coherent_strum_timing'))
        self.assertFalse(r.instrument_positive_model_allowed('BRASS',(121,0,56),'breath_phrase_velocity'))
    def test_profile_completeness_overlay(self):
        r=ProfileRegistry();card=r.profile_completeness(r.profiles[0])
        self.assertEqual(card['completion_state'],'COMPLETE_WITH_EXPLICIT_UNKNOWNS')
        self.assertEqual(len(r.manual_only_profiles()),23)
if __name__=='__main__':unittest.main()