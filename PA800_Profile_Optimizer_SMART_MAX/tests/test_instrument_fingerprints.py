from types import SimpleNamespace
import mido

from pa800_optimizer.analysis.instrument_fingerprints import snapshot_instrument_state,audit_instrument_fingerprints


def note(track,channel,pitch,onset,velocity,occurrence=0):
    return SimpleNamespace(track_index=track,channel=channel,note=pitch,onset=onset,off=onset+48,velocity=velocity,occurrence=occurrence)


def midi():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=0,control=64,value=127,time=0));track.append(mido.Message('control_change',channel=0,control=64,value=0,time=96));return mid


def test_fingerprint_audit_passes_unchanged_bass_guitar_and_piano_shapes():
    notes=[note(0,9,36,0,100),note(0,8,40,0,80),note(0,0,60,96,50),note(0,0,64,99,80),note(0,1,60,192,50),note(0,1,64,192,80),note(0,1,67,192,110)]
    contexts={(0,9):SimpleNamespace(family='DRUM_KIT'),(0,8):SimpleNamespace(family='BASS'),(0,0):SimpleNamespace(family='GUITAR'),(0,1):SimpleNamespace(family='PIANO')}
    mid=midi();before=snapshot_instrument_state(mid,notes,contexts);result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert result['pass'];assert result['bass']['locked_notes_evaluated']==1;assert result['guitar']['strum_groups_evaluated']==1;assert result['piano']['chord_groups_evaluated']==1


def test_fingerprint_audit_detects_piano_chord_flattening():
    notes=[note(0,1,60,0,50),note(0,1,64,0,80),note(0,1,67,0,110)];contexts={(0,1):SimpleNamespace(family='PIANO')};mid=midi();before=snapshot_instrument_state(mid,notes,contexts)
    for item in notes:item.velocity=80
    result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert not result['pass'];assert result['piano']['spread_failure_count']==1


def test_fingerprint_audit_detects_shortened_string_tail_and_controller_change():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=0,control=1,value=80,time=0))
    notes=[note(0,0,60,0,80),note(0,0,64,0,90)];notes[0].off=192;notes[1].off=192;contexts={(0,0):SimpleNamespace(family='STRINGS')};before=snapshot_instrument_state(mid,notes,contexts)
    notes[0].off=96;mid.tracks[0][0]=mid.tracks[0][0].copy(value=70)
    result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert not result['pass'];assert result['sustain']['shortened_tail_count']==1;assert not result['expressive_controllers']['preserved']


def test_fingerprint_audit_detects_organ_velocity_pump_and_lost_legato():
    mid=midi();notes=[note(0,0,60,0,70),note(0,0,64,48,80)];notes[0].off=48;contexts={(0,0):SimpleNamespace(family='ORGAN')};before=snapshot_instrument_state(mid,notes,contexts)
    notes[0].velocity=90;notes[0].off=40
    result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert not result['pass'];assert result['organ']['velocity_excess_count']==1;assert result['organ']['legato_lost_count']==1


def test_fingerprint_audit_blocks_cumulative_velocity_budget_overrun():
    mid=midi();notes=[note(0,0,60,0,70)];contexts={(0,0):SimpleNamespace(family='BRASS')};before=snapshot_instrument_state(mid,notes,contexts)
    notes[0].velocity=95
    result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert not result['pass']
    assert not result['checks']['cumulative_velocity_delta_bounded']
    assert result['velocity_budget']['violation_count']==1
    assert result['velocity_budget']['samples'][0]['cap']==18