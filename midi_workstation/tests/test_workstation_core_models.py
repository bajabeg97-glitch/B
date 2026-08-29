"""Pytest port of workstation core model checks."""

from midi_workstation.core.models import (
    ArticulationMap,
    ChangeIntent,
    EventType,
    MicrotonalPitch,
    MidiDocument,
    MidiEvent,
    MidiTrack,
    PerformanceIntent,
    ProcessingMode,
    TrackRole,
)


def create_note_on(track: int, channel: int, tick: int, note: int, velocity: int) -> MidiEvent:
    return MidiEvent(
        event_type=EventType.NOTE_ON,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        note=note,
        velocity=velocity,
    )


def create_note_off(track: int, channel: int, tick: int, note: int, velocity: int = 0) -> MidiEvent:
    return MidiEvent(
        event_type=EventType.NOTE_OFF,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        note=note,
        velocity=velocity,
    )


def create_cc(track: int, channel: int, tick: int, cc_number: int, value: int) -> MidiEvent:
    return MidiEvent(
        event_type=EventType.CONTROL_CHANGE,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        cc_number=cc_number,
        cc_value=value,
    )


def test_basic_event_creation():
    note_on = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    assert note_on.event_type == EventType.NOTE_ON
    assert note_on.note == 60
    assert note_on.velocity == 100
    assert note_on.note_name == "C4"

    note_off = create_note_off(track=0, channel=1, tick=480, note=60)
    assert note_off.event_type == EventType.NOTE_OFF

    cc_event = create_cc(track=0, channel=1, tick=240, cc_number=1, value=64)
    assert cc_event.cc_number == 1
    assert cc_event.cc_value == 64


def test_track_structure():
    track = MidiTrack(track_index=0, name="Piano", channel=1)
    assert track.role == TrackRole.UNDEFINED
    track.add_event(create_note_on(0, 1, 0, 60, 100))
    track.add_event(create_note_on(0, 1, 480, 64, 90))
    track.add_event(create_note_on(0, 1, 960, 67, 95))
    track.calculate_statistics()
    assert track.total_notes == 3
    assert track.note_range_min == 60
    assert track.note_range_max == 67
    assert len(track.get_notes()) == 3


def test_document_structure():
    doc = MidiDocument(format_type=1, ppqn=480)
    doc.add_track(MidiTrack(name="Piano", channel=1))
    doc.add_track(MidiTrack(name="Bass", channel=2))
    drums = MidiTrack(name="Drums", channel=10, is_drum_track=True)
    doc.add_track(drums)
    assert len(doc.tracks) == 3


def test_processing_modes_and_clone():
    event = create_note_on(0, 1, 0, 60, 100)
    assert event.processing_mode == ProcessingMode.PRESERVE
    event.mark_changed(ChangeIntent.OPTIMIZATION, "Velocity adjustment", "optimizer_v1")
    assert event.changed
    generated = create_note_on(0, 1, 1000, 72, 110)
    generated.mark_generated(0.95, "generator_v1")
    assert generated.generated
    assert generated.source == "generator"
    cloned = event.clone()
    cloned.velocity = 120
    assert event.velocity == 100
    assert cloned.original_event_id == event.event_id


def test_microtonal_and_articulation():
    note = create_note_on(0, 1, 0, 60, 100)
    note.microtonal = MicrotonalPitch(semitone=60, cents_offset=25.5, tuning_system="12TET")
    assert note.microtonal.cents_offset == 25.5
    note.performance_intent = PerformanceIntent(role="accent", tension_level=0.8)
    assert note.performance_intent.role == "accent"
    art_map = ArticulationMap()
    art_map.accent = [60, 64, 67]
    assert 60 in art_map.accent


def test_serialization():
    event = create_note_on(0, 1, 0, 60, 100)
    payload = event.to_dict()
    assert payload["event_type"] == "note_on"
    assert payload["note"] == 60
