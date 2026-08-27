import unittest,mido
from pa800_optimizer.models import Change
from pa800_optimizer.verifier import verify
class T(unittest.TestCase):
    def test_equal(self):
        a=mido.MidiFile(type=1); a.tracks.append(mido.MidiTrack()); b=mido.MidiFile(type=1); b.tracks.append(mido.MidiTrack()); self.assertTrue(verify(a,b)['pass'])
    def base(self):
        m=mido.MidiFile(type=1,ticks_per_beat=192);t=mido.MidiTrack();m.tracks.append(t)
        t.append(mido.Message('control_change',channel=0,control=0,value=121,time=0))
        t.append(mido.Message('control_change',channel=0,control=32,value=3,time=0))
        t.append(mido.Message('program_change',channel=0,program=0,time=0))
        t.append(mido.Message('control_change',channel=0,control=91,value=20,time=0))
        t.append(mido.Message('note_on',channel=0,note=60,velocity=90,time=0))
        t.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=96))
        return m
    def test_only_authorized_fx_can_change(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0][3]=b.tracks[0][3].copy(value=40)
        self.assertFalse(verify(a,b)['pass']);self.assertTrue(verify(a,b,authorized_fx_channels={(0,0)})['pass'])
    def test_sound_target_must_match_allowlist(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0][0]=b.tracks[0][0].copy(value=120);b.tracks[0][1]=b.tracks[0][1].copy(value=0);b.tracks[0][2]=b.tracks[0][2].copy(program=5)
        self.assertTrue(verify(a,b,authorized_sound_targets={(0,0):(120,0,5)})['pass'])
        self.assertFalse(verify(a,b,authorized_sound_targets={(0,0):(120,0,6)})['pass'])
    def test_missing_note_off_fails(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0].pop()
        self.assertFalse(verify(a,b)['pass'])
    def test_note_mutation_requires_exact_change_chain(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0][4]=b.tracks[0][4].copy(velocity=96)
        change=Change(0,4,'velocity',90,96,'test','',channel=0,note=60,occurrence=0)
        self.assertTrue(verify(a,b,authorized_note_changes=[change])['pass'])
        wrong=Change(0,4,'velocity',90,95,'test','',channel=0,note=60,occurrence=0)
        failed=verify(a,b,authorized_note_changes=[wrong]);self.assertFalse(failed['pass']);self.assertEqual(failed['note_diff_diagnostics']['reason'],'final_note_value_mismatch')
        self.assertFalse(verify(a,b,authorized_note_changes=[])['pass'])

    def test_baja_percussion_velocity_authorization(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0][4]=b.tracks[0][4].copy(velocity=36)
        change=Change(0,4,'baja_percussion_40pct',90,36,'explicit_user_stage_mix_percussion_40_percent','PERC',channel=0,note=60,occurrence=0)
        result=verify(a,b,authorized_note_changes=[change])
        self.assertTrue(result['pass'],result)

    def test_timing_and_gate_authorization_chain(self):
        import copy
        a=self.base();a.tracks[0].append(mido.MetaMessage('end_of_track',time=200));b=copy.deepcopy(a);b.tracks[0][4]=b.tracks[0][4].copy(time=2);b.tracks[0][5]=b.tracks[0][5].copy(time=110);b.tracks[0][6]=b.tracks[0][6].copy(time=184)
        changes=[Change(0,4,'timing',0,2,'test','',channel=0,note=60,occurrence=0),Change(0,5,'gate',98,112,'test','',channel=0,note=60,occurrence=0)]
        self.assertTrue(verify(a,b,authorized_note_changes=changes)['pass'])
    def test_fx_event_requires_exact_value_authorization(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.tracks[0][3]=b.tracks[0][3].copy(value=24)
        auth=[{'track':0,'channel':0,'control':91,'occurrence':0,'tick':0,'old':20,'new':24,'source':'test'}]
        self.assertTrue(verify(a,b,authorized_fx_channels={(0,0)},authorized_fx_events=auth)['pass'])
        auth[0]['new']=25
        self.assertFalse(verify(a,b,authorized_fx_channels={(0,0)},authorized_fx_events=auth)['pass'])
    def test_articulation_pulse_must_bracket_note_on_at_same_tick(self):
        import copy
        a=self.base();good=copy.deepcopy(a)
        good.tracks[0].insert(4,mido.Message('control_change',channel=0,control=80,value=127,time=0))
        good.tracks[0].insert(6,mido.Message('control_change',channel=0,control=80,value=0,time=0))
        auth=[(0,0,0,80,127,60,0),(0,0,0,80,0,60,0)]
        self.assertTrue(verify(a,good,authorized_articulation_insertions=auth)['pass'])
        bad=copy.deepcopy(a)
        bad.tracks[0].insert(4,mido.Message('control_change',channel=0,control=80,value=127,time=0))
        bad.tracks[0].insert(5,mido.Message('control_change',channel=0,control=80,value=0,time=0))
        self.assertFalse(verify(a,bad,authorized_articulation_insertions=auth)['pass'])
    def test_smf_type_change_fails(self):
        import copy
        a=self.base();b=copy.deepcopy(a);b.type=0
        result=verify(a,b)
        self.assertFalse(result['pass']);self.assertFalse(result['smf_type'])
    def test_program_note_same_tick_reordering_fails(self):
        import copy
        a=self.base();b=copy.deepcopy(a)
        b.tracks[0][2],b.tracks[0][4]=b.tracks[0][4],b.tracks[0][2]
        result=verify(a,b)
        self.assertFalse(result['pass']);self.assertFalse(result['semantic_event_order'])
if __name__=='__main__':unittest.main()