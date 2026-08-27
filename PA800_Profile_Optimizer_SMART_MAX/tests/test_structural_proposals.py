import copy
import mido

from pa800_optimizer.structural_proposals import (
    build_sound_address_proposals,
    arbitrate_sound_address_proposals,
    commit_sound_address_proposals,
    build_articulation_insert_proposals,
    commit_articulation_insert_proposals,
)
from pa800_optimizer.verifier import verify


def voice_mid():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.extend([
        mido.Message('control_change',channel=0,control=0,value=121,time=0),
        mido.Message('control_change',channel=0,control=32,value=8,time=0),
        mido.Message('program_change',channel=0,program=24,time=0),
        mido.Message('note_on',channel=0,note=60,velocity=80,time=0),
        mido.Message('note_off',channel=0,note=60,velocity=0,time=96),
    ])
    return mid


def test_sound_address_transaction_is_atomic_and_does_not_invent_events():
    before=voice_mid(); sandbox=copy.deepcopy(before)
    sandbox.tracks[0][0]=sandbox.tracks[0][0].copy(value=121)
    sandbox.tracks[0][1]=sandbox.tracks[0][1].copy(value=15)
    sandbox.tracks[0][2]=sandbox.tracks[0][2].copy(program=24)
    proposals=build_sound_address_proposals(before,sandbox)
    assert len(proposals)==1 and proposals[0]['atomic'] is True
    assert proposals[0]['proposed_address']==[121,15,24]
    audit=arbitrate_sound_address_proposals(proposals,{(0,0):(121,15,24)})
    assert audit['pass'] is True and len(audit['accepted'])==1
    assert before.tracks[0][1].value==8  # sandbox planning never touched production MIDI
    committed=commit_sound_address_proposals(before,audit['accepted'])
    assert len(committed)==1 and before.tracks[0][1].value==15
    assert sum(m.type=='program_change' for m in before.tracks[0])==1


def test_sound_address_transaction_rejects_unauthorized_target():
    before=voice_mid(); sandbox=copy.deepcopy(before);sandbox.tracks[0][1]=sandbox.tracks[0][1].copy(value=15)
    proposals=build_sound_address_proposals(before,sandbox)
    audit=arbitrate_sound_address_proposals(proposals,{(0,0):(121,35,25)})
    assert audit['pass'] is False and audit['accepted']==[]
    assert before.tracks[0][1].value==8


def test_articulation_insert_requires_complete_pulse_pair_and_roundtrips_verifier():
    before=voice_mid(); original=copy.deepcopy(before)
    insertions=[(0,0,0,80,127,60,0),(0,0,0,80,0,60,0)]
    audit=build_articulation_insert_proposals(insertions)
    assert audit['pass'] is True and len(audit['accepted'])==1
    rows=commit_articulation_insert_proposals(before,audit['accepted'])
    assert rows==insertions
    pulses=[(m.control,m.value) for m in before.tracks[0] if m.type=='control_change' and m.control==80]
    assert pulses==[(80,127),(80,0)]
    assert verify(original,before,authorized_articulation_insertions=rows)['pass'] is True


def test_articulation_insert_rejects_incomplete_pair():
    audit=build_articulation_insert_proposals([(0,0,0,80,127,60,0)])
    assert audit['pass'] is False and audit['accepted']==[] and len(audit['rejected'])==1
