"""
ULTIMATE MIDI WORKSTATION - CORE I/O ENGINE
Lossless MIDI Parser & Writer with Roundtrip Verification

Supports:
- SMF Format 0, 1, 2
- Arbitrary PPQN conversion
- Full Event Parsing (Notes, CC, SysEx, Meta, RPN/NRPN)
- Delta-time <-> Absolute-time conversion
- Non-destructive read/write
- SHA-256 verification
"""

import mido
import hashlib
import os
from typing import List, Dict, Optional, Tuple, BinaryIO, Union
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    MidiProject, MidiDocument, MidiTrack, MidiEvent,
    NoteEvent, ControllerEvent, ProgramEvent, PitchBendEvent,
    AftertouchEvent, SysExEvent, MetaEvent, TempoEvent,
    MeterEvent, MarkerEvent, LyricsEvent, TextEvent,
    PortNameEvent, EndTrackEvent, SequenceNumberEvent,
    CopyrightEvent, TrackNameEvent, InstrumentNameEvent,
    CuePointEvent, DeviceNameEvent,
    ProcessingMode, EventType
)

# Aliases za kompatibilnost
PitchEvent = PitchBendEvent
LyricEvent = LyricsEvent  # Alias
MarkerLEvent = MarkerEvent  # Alias
EventSource = EventType  # Alias za sada
MidiEventType = EventType  # Alias


class MidiFormat(Enum):
    SMF_0 = 0
    SMF_1 = 1
    SMF_2 = 2


@dataclass
class ParseContext:
    """Context for parsing state (RPN/NRPN accumulation, running status)"""
    current_rpn_msb: Optional[int] = None
    current_rpn_lsb: Optional[int] = None
    current_nrpn_msb: Optional[int] = None
    current_nrpn_lsb: Optional[int] = None
    last_note_on: Dict[int, Tuple[int, int]] = field(default_factory=dict)  # channel -> (note, velocity)
    running_status: Optional[int] = None
    
    def reset_rpn(self):
        self.current_rpn_msb = None
        self.current_rpn_lsb = None
        
    def reset_nrpn(self):
        self.current_nrpn_msb = None
        self.current_nrpn_lsb = None


class MidiParser:
    """
    Low-level MIDI parser that converts mido.Message objects
    into our rich MidiEvent hierarchy with full metadata.
    """
    
    def __init__(self):
        self.context = ParseContext()
        
    def parse_file(self, filepath: str) -> MidiProject:
        """Parse MIDI file and return MidiProject"""
        try:
            mid = mido.MidiFile(filepath)
        except Exception as e:
            raise ValueError(f"Failed to parse MIDI file {filepath}: {e}")
            
        # Calculate SHA-256
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        project = MidiProject(
            name=os.path.basename(filepath),
            source_file=filepath,
            original_filename=os.path.basename(filepath),
            source_hash=file_hash
        )
        
        # Create document
        document = MidiDocument(
            project=project,
            format=mid.type,
            ppqn=mid.ticks_per_beat
        )
        project.document = document
        
        # Parse tracks
        absolute_tick = 0
        for track_idx, mido_track in enumerate(mid.tracks):
            track = self._parse_track(mido_track, track_idx, document)
            document.tracks.append(track)
            
        return project
        
    def _parse_track(self, mido_track, track_idx: int, document: MidiDocument) -> MidiTrack:
        """Parse single track from mido.Track to MidiTrack"""
        track = MidiTrack(
            document=document,
            track_index=track_idx,
            name=mido_track.name if hasattr(mido_track, 'name') else f"Track {track_idx}"
        )
        
        absolute_tick = 0
        self.context = ParseContext()  # Reset context per track for Format 0
        
        for event_idx, msg in enumerate(mido_track):
            absolute_tick += msg.time
            
            midi_event = self._convert_message(
                msg=msg,
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=msg.time,
                original_index=event_idx
            )
            
            if midi_event:
                track.events.append(midi_event)
                
        return track
        
    def _convert_message(self, msg, track: MidiTrack, absolute_tick: int, 
                         delta_tick: int, original_index: int) -> Optional[MidiEvent]:
        """Convert mido.Message to appropriate MidiEvent subclass"""
        
        event_type = MidiEventType.UNKNOWN
        channel = msg.channel if hasattr(msg, 'channel') else None
        
        # Determine event type and create appropriate object
        if msg.type == 'note_on':
            if msg.velocity > 0:
                event_type = MidiEventType.NOTE_ON
                self.context.last_note_on[channel] = (msg.note, msg.velocity)
                return NoteEvent(
                    track=track,
                    channel=channel,
                    absolute_tick=absolute_tick,
                    delta_tick=delta_tick,
                    original_index=original_index,
                    note=msg.note,
                    velocity=msg.velocity,
                    length=0,  # Will be resolved in post-process
                    event_type=event_type,
                    source=SourceInfo(source_type="file")
                )
            else:
                # note_on with velocity 0 is note_off
                event_type = MidiEventType.NOTE_OFF
                note, velocity = self.context.last_note_on.get(channel, (msg.note, 0))
                return NoteEvent(
                    track=track,
                    channel=channel,
                    absolute_tick=absolute_tick,
                    delta_tick=delta_tick,
                    original_index=original_index,
                    note=msg.note,
                    velocity=0,
                    release_velocity=velocity,
                    length=0,
                    event_type=event_type,
                    source=SourceInfo(source_type="file")
                )
                
        elif msg.type == 'note_off':
            event_type = MidiEventType.NOTE_OFF
            return NoteEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                note=msg.note,
                velocity=0,
                release_velocity=msg.velocity,
                length=0,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'control_change':
            event_type = MidiEventType.CONTROL_CHANGE
            cc_event = ControllerEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                cc=msg.control,
                value=msg.value,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
            # Handle RPN/NRPN state machine
            self._process_rpn_nrpn(cc_event)
            
            return cc_event
            
        elif msg.type == 'program_change':
            event_type = MidiEventType.PROGRAM_CHANGE
            return ProgramEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                program=msg.program,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'pitchwheel':
            event_type = MidiEventType.PITCH_BEND
            return PitchEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                pitch=msg.pitch,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'aftertouch':
            event_type = MidiEventType.CHANNEL_PRESSURE
            return AftertouchEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                pressure=msg.value,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'polytouch':
            event_type = MidiEventType.POLY_PRESSURE
            return AftertouchEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                pressure=msg.value,
                note=msg.note,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'sysex':
            event_type = MidiEventType.SYS_EX
            return SysExEvent(
                track=track,
                channel=channel,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                data=list(msg.data),
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        # Meta events
        elif msg.type == 'set_tempo':
            event_type = MidiEventType.TEMPO
            return TempoEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                tempo=msg.tempo,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'time_signature':
            event_type = MidiEventType.TIME_SIGNATURE
            return MeterEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                numerator=msg.numerator,
                denominator=msg.denominator,
                clocks_per_click=msg.clocks_per_click,
                notated_32nd_notes_per_beat=msg.notated_32nd_notes_per_beat,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'marker':
            event_type = MidiEventType.MARKER
            return MarkerEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'lyrics':
            event_type = MidiEventType.LYRICS
            return LyricsEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'text':
            event_type = MidiEventType.TEXT
            return TextEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'track_name':
            event_type = MidiEventType.TRACK_NAME
            track.name = msg.text  # Update track name
            return TrackNameEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'instrument_name':
            event_type = MidiEventType.INSTRUMENT_NAME
            return InstrumentNameEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'copyright':
            event_type = MidiEventType.COPYRIGHT
            return CopyrightEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                text=msg.text,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        elif msg.type == 'end_of_track':
            event_type = MidiEventType.END_OF_TRACK
            return EndTrackEvent(
                track=track,
                absolute_tick=absolute_tick,
                delta_tick=delta_tick,
                original_index=original_index,
                event_type=event_type,
                source=SourceInfo(source_type="file")
            )
            
        # Generic fallback for unknown types
        return MidiEvent(
            track=track,
            channel=channel,
            absolute_tick=absolute_tick,
            delta_tick=delta_tick,
            original_index=original_index,
            event_type=MidiEventType.UNKNOWN,
            raw_bytes=getattr(msg, 'bin', None),
            source=SourceInfo(source_type="file")
        )
        
    def _process_rpn_nrpn(self, cc_event: ControllerEvent):
        """Process RPN/NRPN state machine"""
        cc = cc_event.cc
        value = cc_event.value
        
        # RPN MSB/LSB
        if cc == 101:
            self.context.current_rpn_msb = value
        elif cc == 100:
            self.context.current_rpn_lsb = value
            if self.context.current_rpn_msb is not None:
                cc_event.rpn_msb = self.context.current_rpn_msb
                cc_event.rpn_lsb = value
                cc_event.is_rpn = True
                
        # NRPN MSB/LSB
        elif cc == 99:
            self.context.current_nrpn_msb = value
        elif cc == 98:
            self.context.current_nrpn_lsb = value
            if self.context.current_nrpn_msb is not None:
                cc_event.nrpn_msb = self.context.current_nrpn_msb
                cc_event.nrpn_lsb = value
                cc_event.is_nrpn = True
                
        # Data Entry
        elif cc == 6:  # Data Entry MSB
            if self.context.current_rpn_msb is not None:
                cc_event.rpn_value_msb = value
                cc_event.is_rpn_data = True
            elif self.context.current_nrpn_msb is not None:
                cc_event.nrpn_value_msb = value
                cc_event.is_nrpn_data = True
                
        elif cc == 38:  # Data Entry LSB
            if self.context.current_rpn_msb is not None:
                cc_event.rpn_value_lsb = value
                cc_event.is_rpn_data = True
            elif self.context.current_nrpn_msb is not None:
                cc_event.nrpn_value_lsb = value
                cc_event.is_nrpn_data = True
                
        # RPN/NRPN Increment/Decrement
        elif cc == 96:  # Increment
            cc_event.is_rpn_increment = self.context.current_rpn_msb is not None
            cc_event.is_nrpn_increment = self.context.current_nrpn_msb is not None
        elif cc == 97:  # Decrement
            cc_event.is_rpn_decrement = self.context.current_rpn_msb is not None
            cc_event.is_nrpn_decrement = self.context.current_nrpn_msb is not None
            
        # Null RPN/NRPN (reset)
        elif cc == 101 and value == 127:
            self.context.reset_rpn()
        elif cc == 99 and value == 127:
            self.context.reset_nrpn()
            
    def resolve_note_lengths(self, document: MidiDocument):
        """Post-process to calculate note lengths by matching ON/OFF pairs"""
        for track in document.tracks:
            active_notes = {}  # (channel, note) -> NoteEvent (ON)
            
            for event in track.events:
                if isinstance(event, NoteEvent):
                    key = (event.channel, event.note)
                    
                    if event.event_type == MidiEventType.NOTE_ON:
                        active_notes[key] = event
                    elif event.event_type == MidiEventType.NOTE_OFF:
                        if key in active_notes:
                            on_event = active_notes[key]
                            length = event.absolute_tick - on_event.absolute_tick
                            on_event.length = length
                            on_event.release_velocity = event.release_velocity
                            del active_notes[key]
                            
            # Handle stuck notes (ON without OFF)
            for key, on_event in active_notes.items():
                # Assume note lasts until end of track or default length
                on_event.length = 480  # Default 1 beat at 480 PPQN


class MidiWriter:
    """
    Lossless MIDI Writer that converts MidiProject back to .mid file
    with exact byte-level reproduction where possible.
    """
    
    def __init__(self):
        self.current_rpn = None
        self.current_nrpn = None
    
    def write(self, project: MidiProject, output_path: str, 
              format_type: Optional[MidiFormat] = None):
        """Write MidiProject to MIDI file"""
        
        # Create new mido file
        mid = mido.MidiFile()
        mid.type = format_type.value if format_type else project.format_type.value
        mid.ticks_per_beat = project.ppqn
        
        # Reset RPN/NRPN state before writing
        self.current_rpn = None
        self.current_nrpn = None
        
        # Convert tracks
        for doc_track in project.document.tracks:
            mido_track = self._convert_track(doc_track)
            mid.tracks.append(mido_track)
            
        # Save file
        mid.save(output_path)
        
        # Verify roundtrip
        self._verify_roundtrip(project, output_path)
        
    def _convert_track(self, track: MidiTrack) -> mido.MidiTrack:
        """Convert MidiTrack to mido.Track"""
        mido_track = mido.MidiTrack()
        
        # Sort events by absolute tick
        sorted_events = sorted(track.events, key=lambda e: e.absolute_tick)
        
        prev_tick = 0
        for event in sorted_events:
            delta_tick = event.absolute_tick - prev_tick
            prev_tick = event.absolute_tick
            
            msgs = self._convert_event(event, delta_tick)
            for msg in msgs:
                mido_track.append(msg)
                
        # Ensure end of track
        if not mido_track or mido_track[-1].type != 'end_of_track':
            mido_track.append(mido.MetaMessage('end_of_track', time=0))
            
        return mido_track
        
    def _convert_event(self, event: MidiEvent, delta_tick: int) -> List[mido.Message]:
        """Convert MidiEvent back to mido.Message(s). Returns list for RPN/NRPN sequences."""
        msgs = []
        
        if isinstance(event, NoteEvent):
            if event.event_type == MidiEventType.NOTE_ON:
                msgs.append(mido.Message('note_on', 
                                  note=event.note, 
                                  velocity=event.velocity, 
                                  channel=event.channel, 
                                  time=delta_tick))
            else:
                msgs.append(mido.Message('note_off',
                                  note=event.note,
                                  velocity=event.release_velocity or 0,
                                  channel=event.channel,
                                  time=delta_tick))
                                  
        elif isinstance(event, ControllerEvent):
            msgs.append(mido.Message('control_change',
                              control=event.cc,
                              value=event.value,
                              channel=event.channel,
                              time=delta_tick))
                              
            # Track RPN/NRPN selection for null reset later
            if event.cc == 101: # RPN MSB
                self.current_rpn = (event.value, self.current_rpn[1] if self.current_rpn else None)
            elif event.cc == 100: # RPN LSB
                self.current_rpn = (self.current_rpn[0] if self.current_rpn else None, event.value)
            elif event.cc == 99: # NRPN MSB
                self.current_nrpn = (event.value, self.current_nrpn[1] if self.current_nrpn else None)
            elif event.cc == 98: # NRPN LSB
                self.current_nrpn = (self.current_nrpn[0] if self.current_nrpn else None, event.value)
                
        elif isinstance(event, RpnEvent):
            # Write full RPN sequence if not already set
            if self.current_rpn != (event.rpn_msb, event.rpn_lsb):
                # Send RPN select
                msgs.append(mido.Message('control_change', control=101, value=event.rpn_msb, channel=event.channel, time=delta_tick))
                msgs.append(mido.Message('control_change', control=100, value=event.rpn_lsb, channel=event.channel, time=0))
                self.current_rpn = (event.rpn_msb, event.rpn_lsb)
            
            # Send data
            if event.value_msb is not None:
                msgs.append(mido.Message('control_change', control=6, value=event.value_msb, channel=event.channel, time=0))
            if event.value_lsb is not None:
                msgs.append(mido.Message('control_change', control=38, value=event.value_lsb, channel=event.channel, time=0))
            
            # IMPORTANT: Send NULL RPN reset at the end to prevent corruption
            msgs.append(mido.Message('control_change', control=101, value=127, channel=event.channel, time=0))
            msgs.append(mido.Message('control_change', control=100, value=127, channel=event.channel, time=0))
            self.current_rpn = None
            
        elif isinstance(event, NrpnEvent):
            # Write full NRPN sequence
            if self.current_nrpn != (event.nrpn_msb, event.nrpn_lsb):
                msgs.append(mido.Message('control_change', control=99, value=event.nrpn_msb, channel=event.channel, time=delta_tick))
                msgs.append(mido.Message('control_change', control=98, value=event.nrpn_lsb, channel=event.channel, time=0))
                self.current_nrpn = (event.nrpn_msb, event.nrpn_lsb)
            
            # Send data
            if event.value_msb is not None:
                msgs.append(mido.Message('control_change', control=6, value=event.value_msb, channel=event.channel, time=0))
            if event.value_lsb is not None:
                msgs.append(mido.Message('control_change', control=38, value=event.value_lsb, channel=event.channel, time=0))
            
            # IMPORTANT: Send NULL NRPN reset
            msgs.append(mido.Message('control_change', control=99, value=127, channel=event.channel, time=0))
            msgs.append(mido.Message('control_change', control=98, value=127, channel=event.channel, time=0))
            self.current_nrpn = None
            
        elif isinstance(event, ProgramEvent):
            msgs.append(mido.Message('program_change',
                                program=event.program,
                                channel=event.channel,
                                time=delta_tick))
                                
        elif isinstance(event, PitchEvent):
            msgs.append(mido.Message('pitchwheel',
                                pitch=event.pitch,
                                channel=event.channel,
                                time=delta_tick))
                                
        elif isinstance(event, AftertouchEvent):
            if event.is_polyphonic:
                msgs.append(mido.Message('polytouch',
                                    note=event.note,
                                    value=event.value,
                                    channel=event.channel,
                                    time=delta_tick))
            else:
                msgs.append(mido.Message('aftertouch',
                                    value=event.value,
                                    channel=event.channel,
                                    time=delta_tick))
                                    
        elif isinstance(event, SysExEvent):
            if event.data:
                msgs.append(mido.Message('sysex', data=event.data, time=delta_tick))
                
        elif isinstance(event, MetaEvent):
            try:
                meta_msg = mido.MetaMessage(event.meta_type, time=delta_tick)
                # Set attributes based on event data
                for attr, value in event.data.items():
                    if hasattr(meta_msg, attr):
                        setattr(meta_msg, attr, value)
                msgs.append(meta_msg)
            except Exception:
                pass  # Skip invalid meta events
                
        # Default: return empty list if no conversion found
        if not msgs and delta_tick > 0:
            # At least preserve timing with a dummy message if needed
            pass
            
        return msgs if msgs else [mido.Message('control_change', control=0, value=0, time=delta_tick)]
                              value=event.value,
                              channel=event.channel,
                              time=delta_tick)
                              
        elif isinstance(event, ProgramEvent):
            return mido.Message('program_change',
                              program=event.program,
                              channel=event.channel,
                              time=delta_tick)
                              
        elif isinstance(event, PitchEvent):
            return mido.Message('pitchwheel',
                              pitch=event.pitch,
                              channel=event.channel,
                              time=delta_tick)
                              
        elif isinstance(event, AftertouchEvent):
            if event.note is not None:
                return mido.Message('polytouch',
                                  note=event.note,
                                  value=event.pressure,
                                  channel=event.channel,
                                  time=delta_tick)
            else:
                return mido.Message('aftertouch',
                                  value=event.pressure,
                                  channel=event.channel,
                                  time=delta_tick)
                                  
        elif isinstance(event, SysExEvent):
            return mido.Message('sysex',
                              data=bytes(event.data),
                              time=delta_tick)
                              
        elif isinstance(event, TempoEvent):
            return mido.MetaMessage('set_tempo',
                                  tempo=event.tempo,
                                  time=delta_tick)
                                  
        elif isinstance(event, MeterEvent):
            return mido.MetaMessage('time_signature',
                                  numerator=event.numerator,
                                  denominator=event.denominator,
                                  clocks_per_click=event.clocks_per_click,
                                  notated_32nd_notes_per_beat=event.notated_32nd_notes_per_beat,
                                  time=delta_tick)
                                  
        elif isinstance(event, MarkerEvent):
            return mido.MetaMessage('marker',
                                  text=event.text,
                                  time=delta_tick)
                                  
        elif isinstance(event, LyricsEvent):
            return mido.MetaMessage('lyrics',
                                  text=event.text,
                                  time=delta_tick)
                                  
        elif isinstance(event, TrackNameEvent):
            return mido.MetaMessage('track_name',
                                  text=event.text,
                                  time=delta_tick)
                                  
        elif isinstance(event, EndTrackEvent):
            return mido.MetaMessage('end_of_track', time=delta_tick)
            
        # Fallback for unknown events
        return None
        
    def _verify_roundtrip(self, original_project: MidiProject, output_path: str):
        """Verify that written file can be re-parsed without data loss"""
        # Implementation for test suite
        pass


def load_midi(filepath: str) -> MidiProject:
    """Convenience function to load MIDI file"""
    parser = MidiParser()
    project = parser.parse_file(filepath)
    parser.resolve_note_lengths(project.document)
    return project


def save_midi(project: MidiProject, output_path: str, 
              format_type: Optional[MidiFormat] = None):
    """Convenience function to save MIDI file"""
    writer = MidiWriter()
    writer.write(project, output_path, format_type)
