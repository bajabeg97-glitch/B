from core.instrument_profiles import INSTRUMENT_DB, InstrumentFamily
from core.models import MidiDocument, MidiTrack, NoteEvent, ProgramEvent, create_note_on
from engine.analyzer import ChordAnalyzer, RoleDetector
from engine.instrument_validator import InstrumentValidator, ViolationSeverity


def test_chord_analyzer_detects_c_major():
    track = MidiTrack(name="Piano")
    for pitch in (60, 64, 67):
        note = create_note_on(pitch, 80, 0)
        note.duration = 480
        note.duration_ticks = 480
        track.add_event(note)
    chords = ChordAnalyzer().extract_chords_from_tracks([track])
    assert chords
    assert chords[0]["root"] == "C"
    assert chords[0]["quality"] in {"major", "maj7"}


def test_role_detector_bass_and_empty():
    empty = MidiTrack()
    assert RoleDetector().detect_role(empty)["primary_role"] == "empty"

    bass = MidiTrack(name="Bass", channel=1)
    for i, pitch in enumerate((36, 38, 40, 43)):
        bass.add_event(create_note_on(pitch, 90, i * 480))
        bass.events[-1].duration = 240
        bass.events[-1].duration_ticks = 240
    role = RoleDetector().detect_role(bass)
    assert role["primary_role"] in {"bass", "unknown", "drums"}


def test_instrument_validator_out_of_range_and_repair():
    doc = MidiDocument()
    track = doc.add_track(name="Alto Sax")
    track.add_event(ProgramEvent(program=65, absolute_tick=0))
    too_low = NoteEvent(pitch=10, velocity=80, absolute_tick=0, duration_ticks=240)
    track.add_event(too_low)
    validator = InstrumentValidator(doc)
    violations = validator.validate_track(track)
    assert any(v.violation_type == "OUT_OF_RANGE" for v in violations)
    repaired = validator.auto_repair(violations)
    assert repaired >= 1
    assert 58 <= too_low.pitch <= 93


def test_instrument_db_profiles():
    piano = INSTRUMENT_DB.get_profile("Grand Piano")
    assert piano.family == InstrumentFamily.KEYBOARD
    assert INSTRUMENT_DB.get_profile_by_program(32).name == "Finger Bass"
    assert INSTRUMENT_DB.get_profile("missing") is None
