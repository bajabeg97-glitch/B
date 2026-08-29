from core.models import MidiProject, MidiTrack, create_note_on
from engine.generators.bass_generator import BassGenerator
from engine.generators.fill_generator import FillGenerator
from engine.generators.guitar_generator import RhythmGuitarGenerator
from engine.generators.solo_harmony import HarmonyGenerator
from engine.generators.strings_pad import StringsPadGenerator
from engine.auto_enhancer import AutoEnhancer


def test_guitar_and_pad_generate_notes():
    guitar = RhythmGuitarGenerator([]).generate_pattern("strumming_acoustic")
    assert guitar.name
    assert any(getattr(e, "note_on", False) or getattr(e, "pitch", 0) for e in guitar.events)
    pad = StringsPadGenerator([]).generate_pad_layer()
    assert len(pad.events) >= 4


def test_fill_and_harmony_and_bass_ornament():
    fills = FillGenerator().generate_fills_for_project(MidiProject(), intensity="medium")
    assert fills.events

    solo = MidiTrack(name="Solo")
    solo.add_event(create_note_on(60, 90, 0))
    solo.events[-1].duration = 480
    harmony = HarmonyGenerator([]).generate_harmony_track(solo, interval="third")
    ons = [e for e in harmony.events if getattr(e, "is_note_on", False)]
    assert ons
    assert ons[0].pitch == 64

    bass = MidiTrack(name="Bass")
    bass.add_event(create_note_on(36, 90, 0))
    bass.add_event(create_note_on(48, 90, 960))
    ornaments = BassGenerator([]).generate_ornament_layer(bass)
    assert ornaments is not None


def test_auto_enhancer_on_solo_project():
    project = MidiProject(name="solo")
    track = project.document.add_track(name="Solo Melody")
    track.channel = 0
    for i, pitch in enumerate((60, 64, 67, 72)):
        note = create_note_on(pitch, 90, i * 480)
        note.duration = 480
        note.duration_ticks = 480
        track.add_event(note)
    enhancer = AutoEnhancer(project)
    analysis = enhancer.analyze()
    assert "found" in analysis
    enhanced = enhancer.enhance()
    assert enhanced.document.tracks
