"""
Lossless MIDI parser and writer aligned with core.models.

Supports SMF 0/1/2, notes, CC, program, pitch bend, aftertouch, SysEx and
common meta events. Roundtrip keeps pitch, velocity, channel and tick timing.
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import mido

from .models import (
    AftertouchEvent,
    ControllerEvent,
    CopyrightEvent,
    EndTrackEvent,
    EventType,
    InstrumentNameEvent,
    LyricsEvent,
    MarkerEvent,
    MetaEvent,
    MeterEvent,
    MidiDocument,
    MidiEvent,
    MidiProject,
    MidiTrack,
    NoteEvent,
    PitchBendEvent,
    ProgramEvent,
    SourceInfo,
    SysExEvent,
    TempoEvent,
    TextEvent,
    TrackNameEvent,
)


class MidiFormat(Enum):
    SMF_0 = 0
    SMF_1 = 1
    SMF_2 = 2


@dataclass
class ParseContext:
    current_rpn_msb: Optional[int] = None
    current_rpn_lsb: Optional[int] = None
    current_nrpn_msb: Optional[int] = None
    current_nrpn_lsb: Optional[int] = None
    last_note_on: Dict[int, Tuple[int, int]] = field(default_factory=dict)


class MidiParser:
    def __init__(self):
        self.context = ParseContext()

    def parse_file(self, filepath: str) -> MidiProject:
        try:
            mid = mido.MidiFile(filepath)
        except Exception as exc:
            raise ValueError(f"Failed to parse MIDI file {filepath}: {exc}") from exc

        with open(filepath, "rb") as handle:
            file_hash = hashlib.sha256(handle.read()).hexdigest()

        project = MidiProject(
            name=os.path.basename(filepath),
            source_file=filepath,
            original_filename=os.path.basename(filepath),
            source_hash=file_hash,
        )
        document = MidiDocument(project=project, format=mid.type, ppqn=mid.ticks_per_beat)
        project.document = document

        for track_idx, mido_track in enumerate(mid.tracks):
            document.tracks.append(self._parse_track(mido_track, track_idx, document))

        self.resolve_note_lengths(document)
        document._calculate_duration()
        return project

    def _parse_track(self, mido_track, track_idx: int, document: MidiDocument) -> MidiTrack:
        track = MidiTrack(
            document=document,
            track_index=track_idx,
            name=getattr(mido_track, "name", "") or f"Track {track_idx}",
        )
        absolute_tick = 0
        self.context = ParseContext()

        for event_idx, msg in enumerate(mido_track):
            absolute_tick += msg.time
            midi_event = self._convert_message(msg, absolute_tick, msg.time, event_idx)
            if midi_event is None:
                continue
            midi_event.source = SourceInfo(source_type="file")
            track.add_event(midi_event)
            if isinstance(midi_event, TrackNameEvent) and midi_event.text:
                track.name = midi_event.text
            if isinstance(midi_event, ProgramEvent):
                track.program = midi_event.program
                track.channel = midi_event.channel
            if midi_event.channel == 9:
                track.has_drums = True

        return track

    def _convert_message(self, msg, absolute_tick: int, delta_tick: int, original_index: int):
        channel = getattr(msg, "channel", 0) or 0
        source = SourceInfo(source_type="file")
        common = dict(
            channel=channel,
            absolute_tick=absolute_tick,
            delta_tick=delta_tick,
            original_index=original_index,
            source=source,
        )

        if msg.type == "note_on":
            if msg.velocity > 0:
                self.context.last_note_on[channel] = (msg.note, msg.velocity)
                return NoteEvent(note_on=True, pitch=msg.note, velocity=msg.velocity, **common)
            return NoteEvent(
                note_on=False,
                pitch=msg.note,
                velocity=0,
                release_velocity=msg.velocity,
                **common,
            )

        if msg.type == "note_off":
            return NoteEvent(
                note_on=False,
                pitch=msg.note,
                velocity=0,
                release_velocity=msg.velocity,
                **common,
            )

        if msg.type == "control_change":
            event = ControllerEvent(cc_number=msg.control, value=msg.value, **common)
            self._process_rpn_nrpn(event)
            return event

        if msg.type == "program_change":
            return ProgramEvent(program=msg.program, **common)

        if msg.type == "pitchwheel":
            return PitchBendEvent(value=msg.pitch + 8192, **common)

        if msg.type == "aftertouch":
            return AftertouchEvent(is_polyphonic=False, pressure=msg.value, **common)

        if msg.type == "polytouch":
            return AftertouchEvent(
                is_polyphonic=True, pitch=msg.note, pressure=msg.value, **common
            )

        if msg.type == "sysex":
            return SysExEvent(data_bytes=bytes(msg.data), **common)

        if msg.type == "set_tempo":
            event = TempoEvent(tempo=msg.tempo, **common)
            return event

        if msg.type == "time_signature":
            return MeterEvent(
                numerator=msg.numerator,
                denominator=msg.denominator,
                clocks_per_click=msg.clocks_per_click,
                num_32nds=msg.notated_32nd_notes_per_beat,
                **common,
            )

        if msg.type == "marker":
            return MarkerEvent(text=msg.text, **common)

        if msg.type == "lyrics":
            return LyricsEvent(text=msg.text, **common)

        if msg.type == "text":
            return TextEvent(text=msg.text, **common)

        if msg.type == "track_name":
            return TrackNameEvent(text=msg.name if hasattr(msg, "name") else msg.text, **common)

        if msg.type == "instrument_name":
            return InstrumentNameEvent(text=msg.name if hasattr(msg, "name") else msg.text, **common)

        if msg.type == "copyright":
            return CopyrightEvent(text=msg.text, **common)

        if msg.type == "end_of_track":
            return EndTrackEvent(**common)

        return MidiEvent(event_type=EventType.UNKNOWN, **common)

    def _process_rpn_nrpn(self, cc_event: ControllerEvent) -> None:
        cc = cc_event.cc_number
        value = cc_event.value
        if cc == 101:
            self.context.current_rpn_msb = value
        elif cc == 100:
            self.context.current_rpn_lsb = value
            if self.context.current_rpn_msb is not None:
                cc_event.is_rpn = True
                cc_event.rpn_number = (self.context.current_rpn_msb << 7) | value
        elif cc == 99:
            self.context.current_nrpn_msb = value
        elif cc == 98:
            self.context.current_nrpn_lsb = value
            if self.context.current_nrpn_msb is not None:
                cc_event.is_nrpn = True
                cc_event.nrpn_number = (self.context.current_nrpn_msb << 7) | value
        elif cc == 6:
            if self.context.current_rpn_msb is not None:
                cc_event.is_rpn = True
                cc_event.rpn_value = value
            elif self.context.current_nrpn_msb is not None:
                cc_event.is_nrpn = True
                cc_event.rpn_value = value

    def resolve_note_lengths(self, document: MidiDocument) -> None:
        for track in document.tracks:
            active = {}
            for event in track.events:
                if not isinstance(event, NoteEvent):
                    continue
                key = (event.channel, event.pitch)
                if event.note_on:
                    active[key] = event
                elif key in active:
                    on_event = active.pop(key)
                    length = max(0, event.absolute_tick - on_event.absolute_tick)
                    on_event.duration_ticks = length
                    on_event.duration = length
                    on_event.release_velocity = event.release_velocity
                    on_event.linked_note_off = event.event_id


class MidiWriter:
    def write(
        self,
        project: Union[MidiProject, MidiDocument],
        output_path: Optional[str] = None,
        format_type: Optional[Union[MidiFormat, int]] = None,
    ):
        document = project.document if isinstance(project, MidiProject) else project
        mid = mido.MidiFile()
        if isinstance(format_type, MidiFormat):
            mid.type = format_type.value
        elif isinstance(format_type, int):
            mid.type = format_type
        else:
            mid.type = document.format
        mid.ticks_per_beat = document.ppqn

        for doc_track in document.tracks:
            mid.tracks.append(self._convert_track(doc_track))

        if output_path:
            mid.save(output_path)
            return output_path

        buffer = io.BytesIO()
        mid.save(file=buffer)
        return buffer.getvalue()

    def _convert_track(self, track: MidiTrack) -> mido.MidiTrack:
        mido_track = mido.MidiTrack()
        sorted_events = sorted(track.events, key=lambda event: event.absolute_tick)
        prev_tick = 0
        wrote_end = False
        for event in sorted_events:
            if isinstance(event, EndTrackEvent):
                delta = max(0, event.absolute_tick - prev_tick)
                mido_track.append(mido.MetaMessage("end_of_track", time=delta))
                wrote_end = True
                prev_tick = event.absolute_tick
                continue
            msg = self._convert_event(event, max(0, event.absolute_tick - prev_tick))
            if msg is None:
                continue
            mido_track.append(msg)
            prev_tick = event.absolute_tick
        if not wrote_end:
            mido_track.append(mido.MetaMessage("end_of_track", time=0))
        return mido_track

    def _convert_event(self, event: MidiEvent, delta_tick: int):
        channel = max(0, min(15, int(getattr(event, "channel", 0) or 0)))
        if isinstance(event, NoteEvent):
            pitch = max(0, min(127, int(event.pitch)))
            if event.note_on:
                return mido.Message(
                    "note_on",
                    note=pitch,
                    velocity=max(0, min(127, int(event.velocity))),
                    channel=channel,
                    time=delta_tick,
                )
            return mido.Message(
                "note_off",
                note=pitch,
                velocity=max(0, min(127, int(event.release_velocity or 0))),
                channel=channel,
                time=delta_tick,
            )

        if isinstance(event, ControllerEvent):
            return mido.Message(
                "control_change",
                control=max(0, min(127, int(event.cc_number))),
                value=max(0, min(127, int(event.value))),
                channel=channel,
                time=delta_tick,
            )

        if isinstance(event, ProgramEvent):
            return mido.Message(
                "program_change",
                program=max(0, min(127, int(event.program))),
                channel=channel,
                time=delta_tick,
            )

        if isinstance(event, PitchBendEvent):
            pitch = int(event.value) - 8192
            pitch = max(-8192, min(8191, pitch))
            return mido.Message("pitchwheel", pitch=pitch, channel=channel, time=delta_tick)

        if isinstance(event, AftertouchEvent):
            if event.is_polyphonic:
                return mido.Message(
                    "polytouch",
                    note=max(0, min(127, int(event.pitch or 0))),
                    value=max(0, min(127, int(event.pressure))),
                    channel=channel,
                    time=delta_tick,
                )
            return mido.Message(
                "aftertouch",
                value=max(0, min(127, int(event.pressure))),
                channel=channel,
                time=delta_tick,
            )

        if isinstance(event, SysExEvent):
            data = list(event.data_bytes)
            if data and data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            return mido.Message("sysex", data=data, time=delta_tick)

        if isinstance(event, TempoEvent) or (
            isinstance(event, MetaEvent) and event.meta_type == 0x51 and event.tempo
        ):
            return mido.MetaMessage("set_tempo", tempo=int(event.tempo), time=delta_tick)

        if isinstance(event, MeterEvent) or (
            isinstance(event, MetaEvent) and event.numerator and event.denominator
        ):
            return mido.MetaMessage(
                "time_signature",
                numerator=int(event.numerator or 4),
                denominator=int(event.denominator or 4),
                clocks_per_click=int(event.clocks_per_click or 24),
                notated_32nd_notes_per_beat=int(event.num_32nds or 8),
                time=delta_tick,
            )

        if isinstance(event, MarkerEvent) and event.text is not None:
            return mido.MetaMessage("marker", text=event.text, time=delta_tick)

        if isinstance(event, LyricsEvent) and event.text is not None:
            return mido.MetaMessage("lyrics", text=event.text, time=delta_tick)

        if isinstance(event, TextEvent) and event.text is not None:
            return mido.MetaMessage("text", text=event.text, time=delta_tick)

        if isinstance(event, TrackNameEvent) and event.text is not None:
            return mido.MetaMessage("track_name", name=event.text, time=delta_tick)

        if isinstance(event, InstrumentNameEvent) and event.text is not None:
            return mido.MetaMessage("instrument_name", name=event.text, time=delta_tick)

        if isinstance(event, CopyrightEvent) and event.text is not None:
            return mido.MetaMessage("copyright", text=event.text, time=delta_tick)

        return None

    def _verify_roundtrip(self, original_project: MidiProject, output_path: str) -> bool:
        reparsed = MidiParser().parse_file(output_path)
        original_notes = _note_signature(original_project.document)
        reparsed_notes = _note_signature(reparsed.document)
        return original_notes == reparsed_notes


def _note_signature(document: MidiDocument) -> List[Tuple[int, int, int, int, int]]:
    notes = []
    for track in document.tracks:
        for event in track.events:
            if isinstance(event, NoteEvent) and event.note_on:
                notes.append(
                    (track.track_index, event.channel, event.pitch, event.velocity, event.absolute_tick)
                )
    return notes


def load_midi(filepath: str) -> MidiProject:
    parser = MidiParser()
    return parser.parse_file(filepath)


def save_midi(
    project: Union[MidiProject, MidiDocument],
    output_path: str,
    format_type: Optional[Union[MidiFormat, int]] = None,
) -> str:
    writer = MidiWriter()
    writer.write(project, output_path, format_type)
    return output_path
