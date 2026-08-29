from midi_workstation.core.dual_representation import (
    MidiDocumentDual,
    Section,
    SectionType,
    SongSkeleton,
)
from midi_workstation.core.io import MidiParser, MidiWriter, load_midi, save_midi
from midi_workstation.core.models import (
    EventType,
    MidiDocument,
    MidiEvent,
    MidiProject,
    MidiTrack,
    ProcessingMode,
)
from midi_workstation.engine.skeleton_engine import SongSkeletonEngine
from midi_workstation.engine.suno_core import SunoMIDIEngine


def test_workstation_event_and_track():
    track = MidiTrack(name="Piano", channel=0)
    event = MidiEvent(event_type=EventType.NOTE_ON, note=60, velocity=100, absolute_tick=0)
    assert event.note_name == "C4"
    assert event.is_note_on
    cloned = event.clone()
    cloned.mark_changed(event.change_intent, "edit", "test")
    assert cloned.event_id != event.event_id
    track.add_event(event)
    track.add_note(64, 480, 90, 240)
    track.calculate_statistics()
    assert track.total_notes >= 1
    assert track.get_absolute_tick_max() >= 480


def test_document_tempo_meter_and_project():
    doc = MidiDocument(ppqn=480)
    doc.tempo_map.add_tempo(0, 100)
    doc.meter_map.add_meter(0, 3, 4)
    assert doc.tempo_map.get_tempo_at_tick(10) == 100
    assert doc.meter_map.get_meter_at_tick(10)["numerator"] == 3
    project = MidiProject(name="P")
    project.set_document(doc)
    project.add_analysis_result("key", "C")
    assert project.analysis_results["key"] == "C"
    assert project.to_dict()["name"] == "P"
    assert ProcessingMode.PRESERVE.value == "preserve"


def test_skeleton_and_suno_generate(tmp_path):
    project = MidiProject(name="src")
    doc = MidiDocument(ppqn=480)
    track = MidiTrack(name="Lead")
    for i in range(8):
        track.add_note(tick=i * 480, duration=240, pitch=60 + (i % 5), velocity=80)
    doc.add_track(track)
    project.set_document(doc)

    skeleton = SongSkeletonEngine().build_skeleton(project)
    assert skeleton.total_ticks >= 0
    assert skeleton.sections

    engine = SunoMIDIEngine()
    song = SongSkeleton()
    midi_bytes = engine.generate_from_prompt("balkanska balada 95 bpm c minor", song)
    assert isinstance(midi_bytes, (bytes, bytearray))
    assert midi_bytes[:4] == b"MThd"
    assert song.bpm == 95
    assert song.style == "Balkan Folk"


def test_workstation_roundtrip(tmp_path):
    import mido

    path = tmp_path / "ws.mid"
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("track_name", name="WS", time=0))
    tr.append(mido.Message("note_on", note=62, velocity=88, time=0))
    tr.append(mido.Message("note_off", note=62, velocity=0, time=240))
    mid.save(path)
    document = load_midi(str(path))
    notes = [e for t in document.tracks for e in t.events if e.event_type == EventType.NOTE_ON]
    assert notes and notes[0].note == 62
    out = tmp_path / "ws_out.mid"
    save_midi(document, str(out))
    assert out.exists()


def test_dual_representation_section_compat():
    section = Section(name="Intro", start_bar=1, length=4, energy=0.4)
    assert section.id == "Intro"
    assert section.bar_count == 4
    skeleton = SongSkeleton()
    skeleton.sections.append(section)
    assert skeleton.get_section_at(section.start_tick) is section
    dual = MidiDocumentDual(filename="x.mid", source_hash="abc")
    dual.link_event_to_note(1, "n1")
    assert dual.event_to_note_map[1] == "n1"
    assert SectionType.UNKNOWN.value == "unknown"
