import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.engines.gate import optimize_gate
from pa800_optimizer.models import NoteEvent,OptimizationReport,SoundIdentity,TrackContext


def test_null_gate_profile_is_preserved_without_crash():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('note_on',channel=0,note=60,velocity=90,time=0));track.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=96));track.append(mido.Message('note_on',channel=0,note=62,velocity=90,time=96));track.append(mido.Message('note_off',channel=0,note=62,velocity=0,time=96))
    notes=[NoteEvent(0,0,60,90,0,96,0,1),NoteEvent(0,0,62,90,192,288,2,3)]
    ctx=TrackContext(0,0,'SONG',SoundIdentity(121,0,0,'Partial Piano','PIANO'),family='PIANO')
    report=OptimizationReport('in','out');optimize_gate(mid,notes,{(0,0):ctx},{(0,0):{'gate_to_next_onset':None}},OptimizeConfig.for_mode('max'),report)
    assert report.changes==[]