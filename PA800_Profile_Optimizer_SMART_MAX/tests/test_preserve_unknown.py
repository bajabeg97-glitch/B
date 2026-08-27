import unittest,tempfile,os,mido
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.config import OptimizeConfig
class T(unittest.TestCase):
    def test_unknown_exact_sound_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            a=os.path.join(d,'in.mid'); b=os.path.join(d,'out.mid')
            m=mido.MidiFile(type=1,ticks_per_beat=192); t=mido.MidiTrack();m.tracks.append(t)
            t.append(mido.Message('control_change',channel=0,control=0,value=99,time=0));t.append(mido.Message('control_change',channel=0,control=32,value=99,time=0));t.append(mido.Message('program_change',channel=0,program=99,time=0))
            for v in (30,50,70,90,110):t.append(mido.Message('note_on',channel=0,note=60,velocity=v,time=24));t.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=24))
            m.save(a); Optimizer(OptimizeConfig.for_mode('max')).optimize(a,b)
            x=mido.MidiFile(a);y=mido.MidiFile(b)
            xv=[z.velocity for tr in x.tracks for z in tr if z.type=='note_on' and z.velocity>0]; yv=[z.velocity for tr in y.tracks for z in tr if z.type=='note_on' and z.velocity>0]
            self.assertEqual(xv,yv)
if __name__=='__main__':unittest.main()