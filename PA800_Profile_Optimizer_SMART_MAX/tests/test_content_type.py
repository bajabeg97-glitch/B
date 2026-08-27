import os,tempfile,unittest,mido
from pa800_optimizer.analysis.context import build_contexts,detect_content_type,detect_content_type_details
from pa800_optimizer.profiles.registry import ProfileRegistry
from tests.helpers import make_mid

class ContentTypeTests(unittest.TestCase):
    def test_auto_style_from_cv(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mid(os.path.join(d,'style.mid'));mid=mido.MidiFile(p)
            self.assertEqual(detect_content_type(mid),'style')
            self.assertEqual(build_contexts(mid,ProfileRegistry(),'auto')[(0,8)].role,'BASS')
    def test_song_channel_is_not_arranger_role(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mid(os.path.join(d,'song.mid'),lsb=13,program=24,channel=8);mid=mido.MidiFile(p)
            mid.tracks[0][0]=mido.MetaMessage('track_name',name='Lead',time=0);mid.save(p)
            ctx=build_contexts(mido.MidiFile(p),ProfileRegistry(),'song')[(0,8)]
            self.assertEqual(ctx.role,'SONG');self.assertIsNone(ctx.cv)
    def test_explicit_selection_is_audited(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mid(os.path.join(d,'x.mid'));details=detect_content_type_details(mido.MidiFile(p),'song')
            self.assertEqual(details['confidence'],1.0);self.assertIn('explicit_user_selection',details['reasons'])

if __name__=='__main__':unittest.main()