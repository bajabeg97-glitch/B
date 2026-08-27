import mido

from pa800_optimizer.core.midi_io import collect_channel_state


def test_bank_select_without_following_program_does_not_relabel_active_sound():
    midi=mido.MidiFile(type=1)
    track=mido.MidiTrack();midi.tracks.append(track)
    track.extend([
        mido.Message('control_change',channel=0,control=0,value=0,time=0),
        mido.Message('control_change',channel=0,control=32,value=0,time=0),
        mido.Message('program_change',channel=0,program=1,time=0),
        mido.Message('control_change',channel=0,control=0,value=121,time=10),
    ])
    state=collect_channel_state(midi)[(0,0)]
    assert (state['msb'],state['lsb'],state['program'])==(0,0,1)
    assert state['multi_program'] is False


def test_channel_state_is_shared_across_format_one_tracks():
    midi=mido.MidiFile(type=1)
    conductor=mido.MidiTrack();notes=mido.MidiTrack();midi.tracks.extend([conductor,notes])
    conductor.extend([
        mido.Message('control_change',channel=2,control=0,value=121,time=0),
        mido.Message('control_change',channel=2,control=32,value=1,time=0),
        mido.Message('program_change',channel=2,program=7,time=0),
    ])
    notes.append(mido.Message('note_on',channel=2,note=60,velocity=90,time=0))
    states=collect_channel_state(midi)
    assert (states[(1,2)]['msb'],states[(1,2)]['lsb'],states[(1,2)]['program'])==(121,1,7)