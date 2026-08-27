import copy
import mido
from pa800_optimizer.midi_doctor import repair_midi_transaction, canonical_midi_digest
from pa800_optimizer.event_proposals import generate_controller_diff_proposals, arbitrate_controller_proposals, commit_controller_proposals


def _broken():
    mid=mido.MidiFile(type=1,ticks_per_beat=480);t=mido.MidiTrack();mid.tracks.append(t)
    t.append(mido.Message('note_on',channel=0,note=60,velocity=80,time=0))
    return mid


def test_doctor_transaction_does_not_mutate_source_before_commit():
    raw=_broken();digest=canonical_midi_digest(raw)
    candidate,audit=repair_midi_transaction(raw)
    assert canonical_midi_digest(raw)==digest
    assert audit['transaction']['production_midi_mutated_during_proposal'] is False
    assert audit['transaction']['commit_authorized'] is True
    assert canonical_midi_digest(candidate)!=digest


def test_controller_diff_proposal_is_non_mutating_until_commit():
    before=mido.MidiFile(type=1,ticks_per_beat=480);t=mido.MidiTrack();before.tracks.append(t)
    t.append(mido.Message('control_change',channel=0,control=91,value=20,time=0))
    after=copy.deepcopy(before);after.tracks[0][0]=after.tracks[0][0].copy(value=30)
    source_digest=canonical_midi_digest(before)
    props,audit=generate_controller_diff_proposals(before,after,(91,93),'TEST_LEGACY_FX')
    assert audit['production_midi_mutated'] is False and len(props)==1
    assert canonical_midi_digest(before)==source_digest
    arb=arbitrate_controller_proposals(props);commit=commit_controller_proposals(before,arb)
    assert commit['changes_committed']==1 and before.tracks[0][0].value==30
