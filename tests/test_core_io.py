"""MIDI parse/write roundtrip tests."""

import hashlib
import tempfile
from pathlib import Path

import mido
import pytest

from core.io import MidiWriter, load_midi, save_midi
from core.models import MidiProject, MidiTrack, NoteEvent, create_note_on


def _write_simple_midi(path: Path, notes=((60, 100, 0, 480),), program=0, channel=0):
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Lead", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.Message("program_change", program=program, channel=channel, time=0))
    cursor = 0
    for pitch, velocity, start, duration in notes:
        delay = start - cursor
        track.append(mido.Message("note_on", note=pitch, velocity=velocity, channel=channel, time=delay))
        track.append(mido.Message("note_off", note=pitch, velocity=0, channel=channel, time=duration))
        cursor = start + duration
    mid.save(path)
    return path


def test_load_save_preserves_notes(tmp_path):
    source = _write_simple_midi(tmp_path / "in.mid", notes=((60, 90, 0, 240), (64, 80, 480, 240)))
    project = load_midi(str(source))
    ons = [
        e
        for t in project.document.tracks
        for e in t.events
        if isinstance(e, NoteEvent) and e.note_on
    ]
    assert [(e.pitch, e.velocity) for e in ons] == [(60, 90), (64, 80)]
    assert ons[0].duration_ticks == 240

    dest = tmp_path / "out.mid"
    save_midi(project, str(dest))
    reparsed = load_midi(str(dest))
    re_ons = [
        e
        for t in reparsed.document.tracks
        for e in t.events
        if isinstance(e, NoteEvent) and e.note_on
    ]
    assert [(e.pitch, e.velocity, e.absolute_tick) for e in re_ons] == [
        (e.pitch, e.velocity, e.absolute_tick) for e in ons
    ]


def test_corrupt_file_fails_closed(tmp_path):
    bad = tmp_path / "bad.mid"
    bad.write_bytes(b"not a midi file")
    with pytest.raises(ValueError):
        load_midi(str(bad))


def test_writer_returns_bytes():
    project = MidiProject(name="bytes")
    track = project.document.add_track(name="t")
    track.add_event(create_note_on(67, 100, 0))
    payload = MidiWriter().write(project)
    assert isinstance(payload, (bytes, bytearray))
    assert payload[:4] == b"MThd"


def test_project_load_save_helpers(tmp_path):
    source = _write_simple_midi(tmp_path / "song.mid")
    project = MidiProject.load(str(source))
    assert project.source_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    out = tmp_path / "copy.mid"
    project.save(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_note_on_velocity_zero_is_note_off(tmp_path):
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_on", note=60, velocity=0, time=120))
    path = tmp_path / "vel0.mid"
    mid.save(path)
    project = load_midi(str(path))
    events = [e for t in project.document.tracks for e in t.events if isinstance(e, NoteEvent)]
    assert events[0].note_on
    assert not events[1].note_on
    assert events[0].duration_ticks == 120
