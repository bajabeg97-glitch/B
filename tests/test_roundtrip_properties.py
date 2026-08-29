"""Property tests for MIDI roundtrip invariants."""

import tempfile
from pathlib import Path

import mido
from hypothesis import given, settings
from hypothesis import strategies as st

from core.io import load_midi, save_midi
from core.models import NoteEvent


@st.composite
def midi_note_lists(draw):
    count = draw(st.integers(min_value=1, max_value=8))
    notes = []
    tick = 0
    for _ in range(count):
        pitch = draw(st.integers(min_value=36, max_value=84))
        velocity = draw(st.integers(min_value=1, max_value=127))
        duration = draw(st.integers(min_value=60, max_value=480))
        gap = draw(st.integers(min_value=0, max_value=120))
        notes.append((pitch, velocity, tick, duration))
        tick += duration + gap
    return notes


def _write(path, notes):
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    cursor = 0
    for pitch, velocity, start, duration in notes:
        track.append(mido.Message("note_on", note=pitch, velocity=velocity, time=start - cursor))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=duration))
        cursor = start + duration
    mid.save(path)


@given(notes=midi_note_lists())
@settings(max_examples=25, deadline=None)
def test_roundtrip_preserves_pitch_velocity_and_order(notes):
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        source = tmp / "in.mid"
        dest = tmp / "out.mid"
        _write(source, notes)
        project = load_midi(str(source))
        save_midi(project, str(dest))
        reparsed = load_midi(str(dest))

        def signature(proj):
            return [
                (e.pitch, e.velocity)
                for t in proj.document.tracks
                for e in t.events
                if isinstance(e, NoteEvent) and e.note_on
            ]

        assert signature(project) == [(n[0], n[1]) for n in notes]
        assert signature(reparsed) == signature(project)
