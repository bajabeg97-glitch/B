import unittest,tempfile,os,mido
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.config import OptimizeConfig
class T(unittest.TestCase):
    def test_low_rx_velocity_survives(self):
        with tempfile.TemporaryDirectory() as d:
            a=os.path.join(d,'in.mid'); b=os.path.join(d,'out.mid'); m=mido.MidiFile(type=1,ticks_per_beat=192); t=mido.MidiTrack(); m.tracks.append(t)
            t.append(mido.MetaMessage('track_name',name='ACC1 CV1',time=0)); t.append(mido.Message('control_change',channel=11,control=0,value=121,time=0)); t.append(mido.Message('control_change',channel=11,control=32,value=14,time=0)); t.append(mido.Message('program_change',channel=11,program=28,time=0)); t.append(mido.Message('note_on',channel=11,note=60,velocity=15,time=0)); t.append(mido.Message('note_off',channel=11,note=60,velocity=0,time=96)); m.save(a)
            Optimizer(OptimizeConfig.for_mode('max')).optimize(a,b); mm=mido.MidiFile(b); vals=[x.velocity for tr in mm.tracks for x in tr if x.type=='note_on' and x.velocity>0]; self.assertEqual(vals,[15])
if __name__=='__main__':unittest.main()