import copy

import mido

from pa800_optimizer.analysis.neural_forensics import audit_neural_application
from tools.run_neural_forensic_regression import run


def _midi():
    mid=mido.MidiFile(type=1,ticks_per_beat=96);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('program_change',channel=0,program=0,time=0),mido.Message('note_on',channel=0,note=60,velocity=80,time=0),mido.Message('note_on',channel=0,note=64,velocity=76,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=48),mido.Message('note_off',channel=0,note=64,velocity=0,time=0)])
    return mid


def test_forensic_audit_rejects_velocity_and_broken_chord():
    before=_midi();after=copy.deepcopy(before);after.tracks[0][2]=after.tracks[0][2].copy(velocity=99);after.tracks[0][3]=after.tracks[0][3].copy(time=2)
    audit=audit_neural_application(before,after)
    assert not audit['pass'] and any(row.startswith('velocity_changed') for row in audit['errors'])
    assert 'simultaneous_group_broken' in audit['errors']


def test_certified_corpus_passes_neural_forensic_regression(tmp_path):
    result=run(tmp_path/'result.json')
    assert result['pass'] and result['cases']>=12 and result['changed_cases']>0
    assert all(row['audit']['velocity_preserved'] and row['audit']['voice_events_preserved'] for row in result['rows'])