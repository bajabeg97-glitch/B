"""Exercise the unused models_v2 public surface so complete-stress can account it."""
from pa800_optimizer.core.models_v2 import (
    ControllerEvent,
    EventType,
    KeySignatureEvent,
    MidiEvent,
    NoteEvent,
    NrpnEvent,
    PitchBendEvent,
    ProgramChangeEvent,
    RpnEvent,
    SysExEvent,
    TempoEvent,
    TimeSignatureEvent,
)


def _base(**kwargs):
    values=dict(event_id='e',original_event_id=None,track_index=0,channel=0,absolute_tick=0,delta_tick=0)
    values.update(kwargs)
    return values


def test_models_v2_public_methods_serialize():
    rpn=RpnEvent(rpn_msb=0,rpn_lsb=0,data_msb=2)
    assert rpn.rpn_number==0 and 'Pitch' in rpn.parameter_name and rpn.to_dict()['type']=='RPN'
    nrpn=NrpnEvent(nrpn_msb=1,nrpn_lsb=2)
    assert nrpn.nrpn_number==(1<<7)|2 and nrpn.to_dict()['type']=='NRPN'
    sysex=SysExEvent(raw_bytes=bytes((0xF0,0x42,0xF7)),manufacturer_id=0x42)
    assert sysex.manufacturer_name=='Korg' and not sysex.is_universal and 'F0' in sysex.hex_dump
    assert sysex.to_dict()['type']=='SYSEX'
    event_id=MidiEvent.generate_id(0,0,0,'note_on')
    base=MidiEvent(**_base(event_id=event_id,event_type=EventType.NOTE_ON))
    cloned=base.clone();assert cloned.original_event_id==event_id and cloned.to_dict()['event_type']=='note_on'
    note=NoteEvent(**_base(event_type=EventType.NOTE_ON),note=69,velocity=100,duration_ticks=192)
    assert note.midi_note_to_name(69)==('A',4) and note.frequency>400 and note.gate_ratio==1.0
    assert note.to_dict()['note']==69
    cc=ControllerEvent(**_base(event_type=EventType.CONTROL_CHANGE),controller=7,value=100)
    assert cc.to_dict()['controller']==7
    pc=ProgramChangeEvent(**_base(event_type=EventType.PROGRAM_CHANGE),program=33)
    assert pc.to_dict()['program']==33
    bend=PitchBendEvent(**_base(event_type=EventType.PITCH_BEND),bend_value=8192)
    assert bend.normalized_value==0 and bend.cents==0 and bend.to_dict()['bend_value']==8192
    tempo=TempoEvent(**_base(event_type=EventType.TEMPO),tempo_usq=500000)
    assert abs(tempo.bpm-120)<0.01 and tempo.to_dict()['tempo_usq']==500000
    meter=TimeSignatureEvent(**_base(event_type=EventType.TIME_SIGNATURE),numerator=4,denominator=2)
    assert meter.beats_per_measure==4 and meter.beat_unit==4 and meter.to_dict()['numerator']==4
    key=KeySignatureEvent(**_base(event_type=EventType.KEY_SIGNATURE),fifths=0,is_minor=True)
    assert key.key_name=='Am' and key.to_dict()['is_minor'] is True
