import mido
from types import SimpleNamespace
from pa800_optimizer.models import OptimizationReport
from pa800_optimizer.user_stage_profile import apply_stage_sound_defaults, apply_percussion_40_percent
from pa800_optimizer.core.midi_io import extract_notes


def _track(channel, msb=0, lsb=0, program=0, note=60, velocity=100):
    t=mido.MidiTrack();t.extend([
        mido.Message('control_change',channel=channel,control=0,value=msb,time=0),
        mido.Message('control_change',channel=channel,control=32,value=lsb,time=0),
        mido.Message('program_change',channel=channel,program=program,time=0),
        mido.Message('note_on',channel=channel,note=note,velocity=velocity,time=0),
        mido.Message('note_off',channel=channel,note=note,velocity=0,time=96),
        mido.MetaMessage('end_of_track',time=0)])
    return t


def _ctx(ti,ch,role):
    return SimpleNamespace(track_index=ti,channel=ch,role=role,identity=SimpleNamespace(name=role))


def test_explicit_stage_defaults_and_percussion_mix():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(mido.MidiTrack())
    mid.tracks.extend([_track(8,note=36),_track(9,note=36),_track(10,note=64),_track(11,note=52)])
    contexts={(1,8):_ctx(1,8,'BASS'),(2,9):_ctx(2,9,'DRUM'),(3,10):_ctx(3,10,'PERC'),(4,11):_ctx(4,11,'ACC1')}
    targets,rows=apply_stage_sound_defaults(mid,contexts)
    assert targets[(1,8)]==(121,16,33)
    assert targets[(2,9)]==(120,0,4)
    assert targets[(4,11)]==(121,35,25)
    assert all(r['status'] in ('applied','already_target') for r in rows)
    notes=extract_notes(mid)
    for n in notes:n.protected=False
    rep=OptimizationReport('in.mid','out.mid')
    changed=apply_percussion_40_percent(mid,notes,contexts,rep)
    assert changed==1
    p=[n for n in extract_notes(mid) if n.channel==10][0]
    assert p.velocity==40
    assert [n.velocity for n in extract_notes(mid) if n.channel in (8,9,11)]==[100,100,100]
