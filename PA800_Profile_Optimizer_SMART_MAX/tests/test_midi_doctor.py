import copy,mido

from pa800_optimizer.core.smf_preflight import preflight_smf
from pa800_optimizer.midi_doctor import canonical_midi_digest,repair_midi,scan_midi_health,verify_repair_replay


def broken_midi():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('note_off',channel=0,note=40,velocity=0,time=0))
    track.append(mido.Message('note_on',channel=0,note=60,velocity=90,time=0))
    track.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=0))
    track.append(mido.Message('control_change',channel=0,control=64,value=127,time=20))
    track.append(mido.Message('note_on',channel=0,note=62,velocity=80,time=10))
    track.append(mido.MetaMessage('end_of_track',time=10))
    track.append(mido.MetaMessage('end_of_track',time=0))
    return mid


def test_doctor_repairs_structural_note_and_track_errors():
    mid=broken_midi();before=scan_midi_health(mid)
    assert before['pass'] is False
    audit=repair_midi(mid)
    assert audit['pass'] is True
    assert audit['after']['pass'] is True
    kinds={row['kind'] for row in audit['repairs']}
    assert 'REMOVE_ORPHAN_NOTE_OFF' in kinds
    assert audit['after']['zero_duration_note']==1
    assert 'ADD_MISSING_NOTE_OFF' in kinds
    assert 'RELEASE_STUCK_SUSTAIN' in kinds
    assert 'COLLAPSE_DUPLICATE_END_OF_TRACK' in kinds


def test_doctor_is_idempotent_after_first_repair():
    mid=broken_midi();repair_midi(mid);second=repair_midi(mid)
    assert second['repair_count']==0
    assert second['pass'] is True


def test_zero_duration_drum_style_event_is_preserved():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('note_on',channel=9,note=36,velocity=110,time=0));track.append(mido.Message('note_off',channel=9,note=36,velocity=0,time=0));track.append(mido.MetaMessage('end_of_track',time=0))
    audit=repair_midi(mid)
    assert audit['pass'] is True and audit['repair_count']==0
    assert audit['after']['zero_duration_note']==1
    assert [msg.time for msg in mid.tracks[0] if msg.type in ('note_on','note_off')]==[0,0]


def test_doctor_repairs_invalid_tempo_and_resolution():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo',tempo=0,time=0));track.append(mido.MetaMessage('end_of_track',time=0))
    mid.ticks_per_beat=0
    audit=repair_midi(mid)
    assert audit['pass'] is True
    assert mid.ticks_per_beat==480
    assert next(msg for msg in mid.tracks[0] if msg.type=='set_tempo').tempo==500000


def test_zero_ppqn_preflight_is_recoverable_only_when_doctor_is_enabled(tmp_path):
    path=tmp_path/'zero.mid';path.write_bytes(b'MThd'+(6).to_bytes(4,'big')+(0).to_bytes(2,'big')+(1).to_bytes(2,'big')+(0).to_bytes(2,'big')+b'MTrk'+(4).to_bytes(4,'big')+b'\x00\xff\x2f\x00')
    strict=preflight_smf(path);repair=preflight_smf(path,allow_zero_division_repair=True)
    assert not strict['pass'] and 'zero_division' in strict['errors']
    assert repair['pass'] and 'zero_division_repair_required' in repair['warnings']
    mid=mido.MidiFile(path);audit=repair_midi(mid)
    assert audit['pass'] and mid.ticks_per_beat==480


def test_channel_mode_all_notes_off_materializes_pairing():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('note_on',channel=2,note=64,velocity=90,time=0));track.append(mido.Message('control_change',channel=2,control=123,value=0,time=96));track.append(mido.MetaMessage('end_of_track',time=0))
    audit=repair_midi(mid)
    assert audit['pass'] and any(x['kind']=='MATERIALIZE_CHANNEL_MODE_NOTE_OFF' for x in audit['repairs'])
    assert any(x['kind']=='MATERIALIZE_CHANNEL_MODE_NOTE_OFFS' for x in audit['repair_plan'])
    assert any(msg.type=='note_off' and msg.note==64 for msg in track) or any(msg.type=='note_off' and msg.note==64 for msg in mid.tracks[0])


def test_invalid_tempo_uses_previous_valid_value_not_arbitrary_new_tempo():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo',tempo=600000,time=0));track.append(mido.MetaMessage('set_tempo',tempo=0,time=192));track.append(mido.MetaMessage('end_of_track',time=0))
    audit=repair_midi(mid);tempos=[msg.tempo for msg in mid.tracks[0] if msg.type=='set_tempo']
    assert audit['pass'] and tempos==[600000,600000]
    assert next(row for row in audit['repairs'] if row['kind']=='REPLACE_INVALID_TEMPO')['basis']=='previous_valid_or_smf_default'


def test_conflicting_same_tick_tempo_is_unrecoverable_not_guessed():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    for tempo in (500000,600000):
        track=mido.MidiTrack();track.append(mido.MetaMessage('set_tempo',tempo=tempo,time=0));track.append(mido.MetaMessage('end_of_track',time=0));mid.tracks.append(track)
    audit=repair_midi(mid)
    assert not audit['pass'] and audit['after']['tempo_map_conflicts']==1
    assert 'conflicting_tempo_events_at_same_tick' in audit['unrecoverable']


def test_same_track_same_tick_meter_keeps_last_effective_event():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.MetaMessage('time_signature',numerator=1,denominator=4,time=0))
    track.append(mido.MetaMessage('track_name',name='Conductor',time=0))
    track.append(mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0))
    track.append(mido.MetaMessage('end_of_track',time=0))
    audit=repair_midi(mid)
    meters=[(msg.numerator,msg.denominator) for msg in mid.tracks[0] if msg.type=='time_signature']
    assert audit['pass'] and meters==[(4,4)]
    assert audit['before']['meter_map_conflicts']==1 and audit['after']['meter_map_conflicts']==0
    assert any(row['kind']=='REMOVE_SHADOWED_TIME_SIGNATURE' and row['old_meter'][:2]==[1,4] for row in audit['repairs'])
    assert repair_midi(mid)['repair_count']==0


def test_cross_track_same_tick_meter_conflict_remains_unrecoverable():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    for numerator in (3,4):
        track=mido.MidiTrack();track.append(mido.MetaMessage('time_signature',numerator=numerator,denominator=4,time=0));track.append(mido.MetaMessage('end_of_track',time=0));mid.tracks.append(track)
    audit=repair_midi(mid)
    assert not audit['pass'] and audit['after']['meter_map_conflicts']==1
    assert 'conflicting_meter_events_at_same_tick' in audit['unrecoverable']


def test_doctor_canonical_replay_reproduces_exact_repair_stream():
    raw=broken_midi();repaired=copy.deepcopy(raw);audit=repair_midi(repaired)
    replay=verify_repair_replay(raw,repaired,audit['repairs'])
    assert replay['pass'] and replay['repair_list_match']
    assert replay['expected_digest']==replay['replay_digest']==canonical_midi_digest(repaired)