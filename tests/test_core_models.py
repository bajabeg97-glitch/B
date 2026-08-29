"""Unit tests for lossless MIDI models."""

from core.models import (
    ChangeType,
    MidiDocument,
    MidiProject,
    MidiTrack,
    NoteEvent,
    ProcessingMode,
    create_cc,
    create_note_off,
    create_note_on,
    create_program_change,
)


def test_note_event_aliases_and_name():
    note = create_note_on(60, 100, tick=0, channel=1)
    assert note.pitch == 60
    assert note.note == 60
    assert note.is_note_on
    assert note.note_name == "C4"
    note.note = 64
    assert note.pitch == 64
    assert note.note_name == "E4"


def test_track_statistics_and_lookup():
    track = MidiTrack(name="Piano", channel=0)
    on = create_note_on(60, 100, 0)
    track.add_event(on)
    track.add_event(create_note_on(72, 80, 480))
    assert track.note_count == 2
    assert track.pitch_range == (60, 72)
    assert track.get_event_by_id(on.event_id) is on
    assert track.get_event_by_id("missing") is None
    assert not track.is_empty()
    assert track.get_duration_bars() >= 1


def test_add_note_keyword_and_positional():
    track = MidiTrack(channel=2)
    track.add_note(tick=0, duration=480, pitch=60, velocity=90)
    track.add_note(480, 240, 64, 70)  # tick, duration, pitch, vel
    ons = [e for e in track.events if isinstance(e, NoteEvent) and e.note_on]
    offs = [e for e in track.events if isinstance(e, NoteEvent) and not e.note_on]
    assert len(ons) == 2
    assert len(offs) == 2
    assert ons[0].pitch == 60
    assert ons[1].pitch == 64


def test_suno_style_add_note():
    track = MidiTrack(channel=9)
    track.add_note(36, 0, 120, 480)  # pitch, tick, vel, duration
    on = next(e for e in track.events if isinstance(e, NoteEvent) and e.note_on)
    assert on.pitch == 36
    assert on.velocity == 120
    assert on.duration_ticks == 480


def test_document_and_project_summary():
    project = MidiProject(name="Demo")
    track = project.document.add_track(name="Bass")
    track.program_change(1, 33)
    track.add_note(tick=0, duration=960, pitch=36, velocity=100)
    project.document.set_tempo(0, 500000)
    analysis = project.analyze()
    assert analysis["total_tracks"] == 1
    assert analysis["total_notes"] == 1
    assert "Demo" in project.get_summary()
    assert project.ppqn == 480
    assert project.active_document is project.document


def test_undo_stacks_and_audit():
    project = MidiProject()
    project.push_undo({"action": "add"})
    assert project.undo()["action"] == "add"
    assert project.redo()["action"] == "add"
    note = create_note_on(60, 64, 0)
    note.add_audit_entry(ChangeType.OPTIMIZATION, 64, 80, reason="boost")
    assert note.changed
    assert note.audit_trail[0].reason == "boost"


def test_helpers_create_events():
    off = create_note_off(60, 480)
    assert not off.is_note_on
    cc = create_cc(7, 100, 0)
    assert cc.cc_number == 7
    assert cc.cc_name == "Volume"
    pc = create_program_change(5, 0, bank_msb=121)
    assert pc.program == 5
    payload = note_roundtrip_dict()
    assert payload["event_type"] == "note_on"


def note_roundtrip_dict():
    note = create_note_on(67, 90, 240)
    data = note.to_dict()
    restored = NoteEvent.from_dict(data)
    assert restored.event_type.value == "note_on"
    return data


def test_empty_track_defaults():
    track = MidiTrack()
    assert track.is_empty()
    assert track.get_absolute_tick_max() == 0
    assert MidiDocument().get_tempo() == 120.0
    assert ProcessingMode.PRESERVE.value == "preserve"
