import unittest,tempfile,os
from tests.helpers import make_mid
from pa800_optimizer.core.midi_io import load_midi,extract_notes
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.intent import classify_intents
class T(unittest.TestCase):
    def test_bass_intents(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mid(os.path.join(d,'x.mid')); m=load_midi(p); c=build_contexts(m,ProfileRegistry()); n=extract_notes(m); classify_intents(n,c,m.ticks_per_beat); self.assertTrue(all(x.intent!='NORMAL' for x in n))
if __name__=='__main__':unittest.main()