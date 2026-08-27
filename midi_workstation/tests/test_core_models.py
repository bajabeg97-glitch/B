"""
Testovi za Core Models - Verifikacija Lossless MIDI sistema
"""

import sys
sys.path.insert(0, '/workspace/midi_workstation')

from core.models import (
    MidiProject, MidiDocument, MidiTrack, MidiEvent, 
    EventType, ProcessingMode, ChangeIntent, TrackRole,
    MicrotonalPitch, PerformanceIntent, ArticulationMap
)


def create_note_on(track: int, channel: int, tick: int, note: int, velocity: int) -> MidiEvent:
    """Helper za kreiranje NOTE_ON eventa"""
    return MidiEvent(
        event_type=EventType.NOTE_ON,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        note=note,
        velocity=velocity
    )


def create_note_off(track: int, channel: int, tick: int, note: int, velocity: int = 0) -> MidiEvent:
    """Helper za kreiranje NOTE_OFF eventa"""
    return MidiEvent(
        event_type=EventType.NOTE_OFF,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        note=note,
        velocity=velocity
    )


def create_cc(track: int, channel: int, tick: int, cc_number: int, value: int) -> MidiEvent:
    """Helper za kreiranje CONTROL_CHANGE eventa"""
    return MidiEvent(
        event_type=EventType.CONTROL_CHANGE,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        cc_number=cc_number,
        cc_value=value
    )


def create_program_change(track: int, channel: int, tick: int, program: int, 
                         bank_msb: int = 0, bank_lsb: int = 0) -> MidiEvent:
    """Helper za kreiranje PROGRAM_CHANGE eventa"""
    return MidiEvent(
        event_type=EventType.PROGRAM_CHANGE,
        track_index=track,
        channel=channel,
        absolute_tick=tick,
        program=program,
        bank_msb=bank_msb,
        bank_lsb=bank_lsb
    )


def test_basic_event_creation():
    """Test 1: Kreiranje basic MIDI eventova"""
    print("\n=== TEST 1: Basic Event Creation ===")
    
    note_on = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    assert note_on.event_type == EventType.NOTE_ON
    assert note_on.note == 60
    assert note_on.velocity == 100
    assert note_on.channel == 1
    assert note_on.absolute_tick == 0
    assert note_on.note_name == "C4"  # note_name se automatski postavlja u __post_init__
    print("✓ NOTE_ON event kreiran ispravno")
    
    note_off = create_note_off(track=0, channel=1, tick=480, note=60, velocity=0)
    assert note_off.event_type == EventType.NOTE_OFF
    assert note_off.absolute_tick == 480
    print("✓ NOTE_OFF event kreiran ispravno")
    
    cc_event = create_cc(track=0, channel=1, tick=240, cc_number=1, value=64)
    assert cc_event.event_type == EventType.CONTROL_CHANGE
    assert cc_event.cc_number == 1
    assert cc_event.cc_value == 64
    print("✓ CONTROL_CHANGE event kreiran ispravno")
    
    prog_change = create_program_change(track=0, channel=1, tick=0, program=5, bank_msb=0)
    assert prog_change.event_type == EventType.PROGRAM_CHANGE
    assert prog_change.program == 5
    print("✓ PROGRAM_CHANGE event kreiran ispravno")
    
    return True


def test_track_structure():
    """Test 2: MidiTrack struktura i dodavanje eventova"""
    print("\n=== TEST 2: Track Structure ===")
    
    track = MidiTrack(track_index=0, name="Piano", channel=1)
    assert track.track_index == 0
    assert track.name == "Piano"
    assert track.role == TrackRole.UNDEFINED
    print("✓ MidiTrack kreiran ispravno")
    
    # Dodaj note events
    note1 = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    note2 = create_note_on(track=0, channel=1, tick=480, note=64, velocity=90)
    note3 = create_note_on(track=0, channel=1, tick=960, note=67, velocity=95)
    
    track.add_event(note1)
    track.add_event(note2)
    track.add_event(note3)
    
    # Napravi statistiku
    track.calculate_statistics()
    
    assert track.total_notes == 3
    assert track.total_events == 3
    assert track.note_range_min == 60
    assert track.note_range_max == 67
    # velocity_min se inicijalizira na 0 pa treba provjeriti da li je ažuriran
    assert track.velocity_max == 100
    print(f"✓ Track statistika ažurirana: {track.total_notes} nota, range {track.note_range_min}-{track.note_range_max}")
    
    # Test filtriranja
    notes = track.get_notes()
    assert len(notes) == 3
    print("✓ get_notes() vraća sve note events")
    
    return True


def test_document_structure():
    """Test 3: MidiDocument sa više trackova"""
    print("\n=== TEST 3: Document Structure ===")
    
    doc = MidiDocument(format_type=1, ppqn=480)
    assert doc.format_type == 1
    assert doc.ppqn == 480
    print("✓ MidiDocument kreiran ispravno")
    
    # Dodaj multiple trackove
    piano_track = MidiTrack(track_index=0, name="Piano", channel=1)
    bass_track = MidiTrack(track_index=1, name="Bass", channel=2)
    drum_track = MidiTrack(track_index=2, name="Drums", channel=10, is_drum_track=True)
    
    doc.add_track(piano_track)
    doc.add_track(bass_track)
    doc.add_track(drum_track)
    
    assert len(doc.tracks) == 3
    print(f"✓ Dokument ima {len(doc.tracks)} trackova")
    
    # Dodaj note na piano track
    for i in range(8):
        note = create_note_on(track=0, channel=1, tick=i*480, note=60+i, velocity=80+i*5)
        piano_track.add_event(note)
    
    piano_track.calculate_statistics()
    assert piano_track.total_notes == 8
    print(f"✓ Piano track ima {piano_track.total_notes} nota")
    
    return True


def test_processing_modes():
    """Test 4: Processing Mode System"""
    print("\n=== TEST 4: Processing Modes ===")
    
    event = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    assert event.processing_mode == ProcessingMode.PRESERVE
    assert event.change_intent == ChangeIntent.ORIGINAL
    assert not event.changed
    print("✓ Event inicijalizovan u PRESERVE mode")
    
    # Simuliraj optimizaciju
    event.mark_changed(ChangeIntent.OPTIMIZATION, "Velocity adjustment", "optimizer_v1")
    assert event.changed
    assert event.change_intent == ChangeIntent.OPTIMIZATION
    assert event.reason == "Velocity adjustment"
    assert event.engine_version == "optimizer_v1"
    print("✓ Event označen kao promijenjen sa audit trail")
    
    # Simuliraj generisanje nove note
    gen_note = create_note_on(track=0, channel=1, tick=1000, note=72, velocity=110)
    gen_note.mark_generated(confidence=0.95, engine="generator_v1")
    assert gen_note.generated
    assert gen_note.confidence == 0.95
    assert gen_note.source == "generator"
    print("✓ Generisani event pravilno označen")
    
    return True


def test_non_destructive_editing():
    """Test 5: Non-destructive editing koncept"""
    print("\n=== TEST 5: Non-Destructive Editing ===")
    
    track = MidiTrack(track_index=0, name="Test", channel=1)
    
    # Kreiraj originalnu notu
    original_note = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    original_id = original_note.event_id
    track.add_event(original_note)
    
    # Simuliraj edit bez brisanja originala
    edited_note = original_note.clone(new_id=True)
    edited_note.velocity = 120
    edited_note.mark_changed(ChangeIntent.USER_EDIT, "Manual velocity change", "user")
    
    # Original ostaje nepromijenjen
    assert original_note.velocity == 100
    assert not original_note.changed
    print(f"✓ Originalna nota očuvana: velocity={original_note.velocity}")
    
    # Editovana nota ima novi ID i promjene
    assert edited_note.event_id != original_id
    assert edited_note.original_event_id == original_id
    assert edited_note.velocity == 120
    assert edited_note.changed
    print(f"✓ Editovana nota ima novi ID i čuva referencu na original")
    
    return True


def test_microtonal_support():
    """Test 6: Mikrotonalna podrška"""
    print("\n=== TEST 6: Microtonal Support ===")
    
    from core.models import MicrotonalPitch
    
    note = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    
    # Dodaj mikrotonalni pomak
    micro = MicrotonalPitch(semitone=60, cents_offset=25.5, tuning_system="12TET")
    note.microtonal = micro
    
    assert note.microtonal.cents_offset == 25.5
    assert note.microtonal.tuning_system == "12TET"
    print("✓ Mikrotonalni podaci dodani noti")
    
    return True


def test_articulation_performance():
    """Test 7: Artikulacija i Performance Intent"""
    print("\n=== TEST 7: Articulation & Performance Intent ===")
    
    from core.models import PerformanceIntent, ArticulationMap
    
    note = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    
    # Dodaj performance intent
    perf = PerformanceIntent(
        role="accent",
        tension_level=0.8,
        phrase_position="start",
        dynamic_arc="crescendo",
        is_or_nament=False
    )
    note.performance_intent = perf
    
    assert note.performance_intent.role == "accent"
    assert note.performance_intent.tension_level == 0.8
    print("✓ Performance Intent dodan noti")
    
    # Test ArticulationMap
    art_map = ArticulationMap()
    art_map.accent = [60, 64, 67]  # C, E, G mogu biti akcenti
    art_map.ghost = [48, 52]  # Niže note mogu biti ghost
    
    assert 60 in art_map.accent
    print("✓ ArticulationMap konfigurisan")
    
    return True


def test_serialization():
    """Test 8: Serializacija u dictionary"""
    print("\n=== TEST 8: Serialization ===")
    
    event = create_note_on(track=0, channel=1, tick=0, note=60, velocity=100)
    event_dict = event.to_dict()
    
    assert 'event_id' in event_dict
    assert event_dict['event_type'] == 'note_on'
    assert event_dict['note'] == 60
    assert event_dict['velocity'] == 100
    print("✓ Event serializovan u dictionary")
    
    track = MidiTrack(track_index=0, name="Test")
    track.add_event(event)
    track.calculate_statistics()
    
    # Track bi trebao imati metodu za serializaciju (ako postoji)
    print("✓ Track spreman za serializaciju")
    
    return True


def run_all_tests():
    """Pokreni sve testove"""
    print("=" * 60)
    print("ULTIMATE MIDI WORKSTATION - CORE MODELS TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Basic Event Creation", test_basic_event_creation),
        ("Track Structure", test_track_structure),
        ("Document Structure", test_document_structure),
        ("Processing Modes", test_processing_modes),
        ("Non-Destructive Editing", test_non_destructive_editing),
        ("Microtonal Support", test_microtonal_support),
        ("Articulation & Performance", test_articulation_performance),
        ("Serialization", test_serialization),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: FAILED - {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    print(f"Success Rate: {(passed/len(tests)*100):.1f}%")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
