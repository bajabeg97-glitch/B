from types import SimpleNamespace

from pa800_optimizer.instruments.guards import expressive_controller_channels,organ_legato_note_ids,retain_group_spread,sustained_tail_note_ids,sustained_timing_guard_ids,timing_guard_ids
import mido


def note(track,channel,pitch,onset,velocity=80,occurrence=0):
    return SimpleNamespace(track_index=track,channel=channel,note=pitch,onset=onset,off=onset+48,velocity=velocity,occurrence=occurrence)


def context(family):return SimpleNamespace(family=family)


def test_piano_chord_spread_guard_restores_minimum_dynamic_shape():
    notes=[note(0,0,60,0,50),note(0,0,64,0,80),note(0,0,67,0,110)]
    proposed=retain_group_spread(notes,[78,80,82],minimum=.75)
    assert max(proposed)-min(proposed)>=45


def test_timing_guards_cover_guitar_strums_and_piano_chords():
    notes=[note(0,0,60,0),note(0,0,64,3),note(1,0,60,96),note(1,0,64,96)]
    guitar,piano=timing_guard_ids(notes,{(0,0):context('GUITAR'),(1,0):context('PIANO')},192)
    assert len(guitar)==2 and len(piano)==2


def test_separated_guitar_notes_remain_eligible_for_profile_timing():
    notes=[note(0,0,60,0),note(0,0,64,24)]
    guitar,piano=timing_guard_ids(notes,{(0,0):context('GUITAR')},192)
    assert not guitar and not piano


def test_sustained_chords_and_long_tails_are_guarded():
    notes=[note(0,0,60,0),note(0,0,64,0)];notes[0].off=192;notes[1].off=48
    contexts={(0,0):context('STRINGS')}
    assert len(sustained_timing_guard_ids(notes,contexts))==2
    assert sustained_tail_note_ids(notes,contexts,192)=={(0,0,60,0)}


def test_organ_legato_and_expressive_controller_channels_are_detected():
    organ=[note(0,0,60,0),note(0,0,64,48)];organ[0].off=48
    assert organ_legato_note_ids(organ,{(0,0):context('ORGAN')})=={(0,0,60,0),(0,0,64,0)}
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=1,control=1,value=90,time=0))
    assert expressive_controller_channels(mid,{(0,1):context('BRASS')})=={(0,1)}