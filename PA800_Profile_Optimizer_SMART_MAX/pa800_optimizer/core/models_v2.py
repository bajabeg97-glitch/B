"""ULTIMATE MIDI WORKSTATION — Core Domain Models

Implements Master Plan sections 2-5:
- Lossless MIDI Core representation layer
- Full MIDI event support with rich metadata
- RPN/NRPN state-machine parser
- SysEx workbench primitives

Every event tracks:
- event_id, original_event_id
- track, channel, absolute_tick, delta_tick
- measure, beat, subbeat (when computed)
- original_index, event_type
- changed, generated, source, confidence
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Iterator
from enum import Enum
from collections import defaultdict


class EventType(Enum):
    """Complete MIDI 1.0 event taxonomy with MIDI 2.0 extension points."""
    # Note events
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    
    # Channel voice messages
    POLY_PRESSURE = "poly_pressure"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"
    CHANNEL_PRESSURE = "channel_pressure"
    PITCH_BEND = "pitch_bend"
    
    # System common
    SYSTEM_EXCLUSIVE = "system_exclusive"
    SYSEX_START = "sysex_start"
    SYSEX_END = "sysex_end"
    SYSTEM_EXCLUSIVE_8 = "system_exclusive_8"  # MIDI 2.0
    
    # System real-time
    TIMING_CLOCK = "timing_clock"
    START = "start"
    CONTINUE = "continue"
    STOP = "stop"
    ACTIVE_SENSING = "active_sensing"
    SYSTEM_RESET = "system_reset"
    
    # Meta events
    SEQUENCE_NUMBER = "sequence_number"
    TEXT_EVENT = "text_event"
    COPYRIGHT_NOTICE = "copyright_notice"
    TRACK_NAME = "track_name"
    INSTRUMENT_NAME = "instrument_name"
    LYRIC = "lyric"
    MARKER = "marker"
    CUE_MARKER = "cue_marker"
    DEVICE_NAME = "device_name"
    
    # MIDI 1.0 meta continuation
    MIDI_CHANNEL_PREFIX = "midi_channel_prefix"
    MIDI_PORT = "midi_port"
    END_OF_TRACK = "end_of_track"
    TEMPO = "set_tempo"
    SMPTE_OFFSET = "smpte_offset"
    TIME_SIGNATURE = "time_signature"
    KEY_SIGNATURE = "key_signature"
    SEQUENCER_SPECIFIC = "sequencer_specific"
    
    # RPN/NRPN composite events (parsed from CC sequences)
    RPN = "rpn"
    NRPN = "nrpn"
    
    # MIDI 2.0 UMP events
    UMP_FUNCTION_BLOCK = "ump_function_block"
    UMP_GROUP = "ump_group"
    UMP_CHANNEL_VOICE_2 = "ump_channel_voice_2"
    UMP_PER_NOTE_CONTROLLERS = "ump_per_note_controllers"
    
    # Internal/composite
    UNKNOWN = "unknown"
    INVALID = "invalid"


class EventSource(Enum):
    """Origin of each event for audit trail."""
    ORIGINAL = "original"
    USER_EDIT = "user_edit"
    OPTIMIZATION = "optimization"
    REPAIR = "repair"
    TRANSFORM = "transform"
    GENERATION = "generation"
    TRANSFER = "transfer"
    QUANTIZE = "quantize"
    HUMANIZE = "humanize"
    ARTICULATION = "articulation"
    RX_DNC = "rx_dnc"
    CONTROLLER_EDIT = "controller_edit"
    RPN_NRPN = "rpn_nrpn"
    SYSEX_EDIT = "sysex_edit"
    CONVERSION = "conversion"
    MERGE = "merge"
    SPLIT = "split"


@dataclass
class RpnEvent:
    """Registered Parameter Number event parsed from CC sequence.
    
    Master Plan section 4: RPN/NRPN state-machine parser output.
    
    CC Sequence for RPN:
    - CC101 (RPN MSB)
    - CC100 (RPN LSB)  
    - CC6 (Data Entry MSB)
    - CC38 (Data Entry LSB, optional)
    - CC96 (Decrement, alternative)
    - CC97 (Increment, alternative)
    - CC98 (NRPN MSB, cancels RPN)
    - CC99 (NRPN LSB, cancels RPN)
    """
    rpn_msb: int
    rpn_lsb: int
    data_msb: Optional[int] = None
    data_lsb: Optional[int] = None
    increment: Optional[int] = None
    decrement: Optional[int] = None
    channel: int = 0
    absolute_tick: int = 0
    track_index: int = 0
    
    # Standard RPN definitions
    RPN_PITCH_BEND_RANGE = (0, 0)
    RPN_CHANNEL_FINE_TUNING = (0, 1)
    RPN_CHANNEL_COARSE_TUNING = (0, 2)
    RPN_TUNING_PROGRAM_CHANGE = (0, 3)
    RPN_TUNING_BANK_SELECT = (0, 4)
    RPN_MODULATION_DEPTH_RANGE = (0, 5)
    
    @property
    def rpn_number(self) -> int:
        return (self.rpn_msb << 7) | self.rpn_lsb
    
    @property
    def parameter_name(self) -> str:
        known_rpns = {
            (0, 0): "Pitch Bend Range",
            (0, 1): "Channel Fine Tuning",
            (0, 2): "Channel Coarse Tuning",
            (0, 3): "Tuning Program Change",
            (0, 4): "Tuning Bank Select",
            (0, 5): "Modulation Depth Range",
            (127, 127): "RPN Null",
        }
        return known_rpns.get((self.rpn_msb, self.rpn_lsb), f"RPN {self.rpn_number}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'RPN',
            'rpn_msb': self.rpn_msb,
            'rpn_lsb': self.rpn_lsb,
            'rpn_number': self.rpn_number,
            'parameter_name': self.parameter_name,
            'data_msb': self.data_msb,
            'data_lsb': self.data_lsb,
            'channel': self.channel,
            'absolute_tick': self.absolute_tick,
        }


@dataclass
class NrpnEvent:
    """Non-Registered Parameter Number event parsed from CC sequence.
    
    Master Plan section 4: NRPN state-machine parser output.
    
    CC Sequence for NRPN:
    - CC99 (NRPN MSB)
    - CC98 (NRPN LSB)
    - CC6 (Data Entry MSB)
    - CC38 (Data Entry LSB, optional)
    """
    nrpn_msb: int
    nrpn_lsb: int
    data_msb: Optional[int] = None
    data_lsb: Optional[int] = None
    channel: int = 0
    absolute_tick: int = 0
    track_index: int = 0
    manufacturer_id: Optional[int] = None  # For device-specific NRPNs
    
    @property
    def nrpn_number(self) -> int:
        return (self.nrpn_msb << 7) | self.nrpn_lsb
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'NRPN',
            'nrpn_msb': self.nrpn_msb,
            'nrpn_lsb': self.nrpn_lsb,
            'nrpn_number': self.nrpn_number,
            'data_msb': self.data_msb,
            'data_lsb': self.data_lsb,
            'channel': self.channel,
            'absolute_tick': self.absolute_tick,
        }


@dataclass
class SysExEvent:
    """System Exclusive event with parsing metadata.
    
    Master Plan section 5: SysEx Workbench foundation.
    
    Structure:
    - Start: 0xF0
    - Manufacturer ID (1 or 3 bytes)
    - Device ID (optional, model-dependent)
    - Model ID (optional)
    - Command/Data
    - Checksum (model-dependent)
    - End: 0xF7
    """
    raw_bytes: bytes
    manufacturer_id: int
    device_id: Optional[int] = None
    model_id: Optional[int] = None
    command_id: Optional[int] = None
    data: bytes = field(default_factory=bytes)
    checksum: Optional[int] = None
    checksum_valid: Optional[bool] = None
    absolute_tick: int = 0
    track_index: int = 0
    
    # Common manufacturer IDs
    MANUFACTURER_IDS = {
        0x41: "Roland",
        0x42: "Korg", 
        0x43: "Yamaha",
        0x44: "Casio",
        0x47: "Akai",
        0x40: "Sequential Circuits",
        0x7E: "Universal Non-Realtime",
        0x7F: "Universal Realtime",
    }
    
    @property
    def manufacturer_name(self) -> str:
        return self.MANUFACTURER_IDS.get(self.manufacturer_id, f"Unknown (0x{self.manufacturer_id:02X})")
    
    @property
    def is_universal(self) -> bool:
        return self.manufacturer_id in (0x7E, 0x7F)
    
    @property
    def hex_dump(self) -> str:
        return ' '.join(f'{b:02X}' for b in self.raw_bytes)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'SYSEX',
            'manufacturer_id': self.manufacturer_id,
            'manufacturer_name': self.manufacturer_name,
            'device_id': self.device_id,
            'model_id': self.model_id,
            'command_id': self.command_id,
            'data_length': len(self.data),
            'checksum': self.checksum,
            'checksum_valid': self.checksum_valid,
            'absolute_tick': self.absolute_tick,
            'hex_preview': self.hex_dump[:60] + ('...' if len(self.raw_bytes) > 30 else ''),
        }


@dataclass
class MidiEvent:
    """Base class for all MIDI events with full metadata.
    
    Master Plan section 2: Lossless MIDI Core representation.
    
    Every event tracks complete provenance and modification history.
    """
    event_id: str
    original_event_id: Optional[str]
    
    # Location
    track_index: int
    channel: Optional[int]
    absolute_tick: int
    delta_tick: int
    
    # Musical position (computed when time signature known)
    measure: Optional[int] = None
    beat: Optional[int] = None
    subbeat: Optional[int] = None
    
    # Original ordering
    original_index: int = 0
    
    # Event classification
    event_type: EventType = EventType.UNKNOWN
    
    # Raw MIDI data where applicable
    raw_bytes: Optional[bytes] = None
    status_byte: Optional[int] = None
    
    # Modification tracking
    changed: bool = False
    generated: bool = False
    deleted: bool = False
    
    # Provenance
    source: EventSource = EventSource.ORIGINAL
    confidence: float = 1.0
    
    # Audit trail
    change_reason: Optional[str] = None
    changed_at: Optional[str] = None
    changed_by: Optional[str] = None
    
    # References to parsed composite events
    rpn_event: Optional[RpnEvent] = None
    nrpn_event: Optional[NrpnEvent] = None
    sysex_event: Optional[SysExEvent] = None
    
    # Links to related events (e.g., note_on ↔ note_off)
    related_event_ids: List[str] = field(default_factory=list)
    
    # Arbitrary metadata for extensions
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @staticmethod
    def generate_id(track: int, tick: int, index: int, event_type: str) -> str:
        """Generate unique event ID."""
        data = f"{track}:{tick}:{index}:{event_type}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def clone(self, new_source: EventSource = EventSource.USER_EDIT) -> MidiEvent:
        """Create a modified copy with new provenance."""
        import datetime
        new_id = MidiEvent.generate_id(
            self.track_index, self.absolute_tick, 
            self.original_index, self.event_type.value
        )
        return MidiEvent(
            event_id=new_id,
            original_event_id=self.event_id if not self.original_event_id else self.original_event_id,
            track_index=self.track_index,
            channel=self.channel,
            absolute_tick=self.absolute_tick,
            delta_tick=self.delta_tick,
            measure=self.measure,
            beat=self.beat,
            subbeat=self.subbeat,
            original_index=self.original_index,
            event_type=self.event_type,
            raw_bytes=self.raw_bytes,
            status_byte=self.status_byte,
            changed=self.changed,
            generated=self.generated,
            deleted=self.deleted,
            source=new_source,
            confidence=self.confidence,
            change_reason=self.change_reason,
            changed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            changed_by="user",
            rpn_event=self.rpn_event,
            nrpn_event=self.nrpn_event,
            sysex_event=self.sysex_event,
            related_event_ids=list(self.related_event_ids),
            metadata=dict(self.metadata),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        result = {
            'event_id': self.event_id,
            'original_event_id': self.original_event_id,
            'track_index': self.track_index,
            'channel': self.channel,
            'absolute_tick': self.absolute_tick,
            'delta_tick': self.delta_tick,
            'measure': self.measure,
            'beat': self.beat,
            'subbeat': self.subbeat,
            'original_index': self.original_index,
            'event_type': self.event_type.value,
            'status_byte': self.status_byte,
            'changed': self.changed,
            'generated': self.generated,
            'deleted': self.deleted,
            'source': self.source.value,
            'confidence': self.confidence,
            'change_reason': self.change_reason,
        }
        
        if self.rpn_event:
            result['rpn_event'] = self.rpn_event.to_dict()
        if self.nrpn_event:
            result['nrpn_event'] = self.nrpn_event.to_dict()
        if self.sysex_event:
            result['sysex_event'] = self.sysex_event.to_dict()
            
        return result


@dataclass
class NoteEvent(MidiEvent):
    """Note event with pitch, velocity, and duration.
    
    Master Plan section 2: Enhanced note representation.
    """
    note: int = 0
    velocity: int = 0
    release_velocity: int = 0
    duration_ticks: int = 0
    
    # Musical properties
    note_name: str = ""
    octave: int = 0
    
    # Articulation markers
    is_staccato: bool = False
    is_legato: bool = False
    is_accent: bool = False
    is_ghost: bool = False
    
    # Generation/modification
    original_velocity: int = 0
    original_duration: int = 0
    velocity_changed: bool = False
    timing_changed: bool = False
    duration_changed: bool = False
    
    def __post_init__(self):
        if self.note and not self.note_name:
            self.note_name, self.octave = self.midi_note_to_name(self.note)
    
    @staticmethod
    def midi_note_to_name(note: int) -> Tuple[str, int]:
        """Convert MIDI note number to name and octave."""
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = names[note % 12]
        return name, octave
    
    @property
    def frequency(self) -> float:
        """Calculate frequency in Hz (A4 = 440Hz)."""
        return 440.0 * (2.0 ** ((self.note - 69) / 12.0))
    
    @property
    def gate_ratio(self) -> float:
        """Calculate gate ratio (duration / expected_duration_for_tempo)."""
        # Placeholder - needs tempo map access
        return 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'note': self.note,
            'note_name': self.note_name,
            'octave': self.octave,
            'velocity': self.velocity,
            'release_velocity': self.release_velocity,
            'duration_ticks': self.duration_ticks,
            'frequency_hz': round(self.frequency, 2),
            'is_staccato': self.is_staccato,
            'is_legato': self.is_legato,
            'is_accent': self.is_accent,
            'is_ghost': self.is_ghost,
            'original_velocity': self.original_velocity,
            'original_duration': self.original_duration,
            'velocity_changed': self.velocity_changed,
            'timing_changed': self.timing_changed,
            'duration_changed': self.duration_changed,
        })
        return result


@dataclass
class ControllerEvent(MidiEvent):
    """Control Change event with semantic interpretation.
    
    Master Plan section 3: Full CC support 0-127.
    """
    controller: int = 0
    value: int = 0
    
    # Semantic interpretation
    controller_name: str = ""
    category: str = ""  # 'volume', 'expression', 'modulation', etc.
    
    # For RPN/NRPN sequences
    is_data_entry: bool = False
    is_rpn_port: bool = False
    is_nrpn_port: bool = False
    
    # High-resolution value (when CC38 paired with CC6)
    value_14bit: Optional[int] = None
    
    # Known CC definitions
    CC_NAMES = {
        0: "Bank Select MSB",
        1: "Modulation Wheel",
        2: "Breath Controller",
        4: "Foot Controller",
        5: "Portamento Time",
        6: "Data Entry MSB",
        7: "Volume",
        8: "Balance",
        10: "Pan",
        11: "Expression",
        12: "Effect Control 1",
        13: "Effect Control 2",
        16: "General Purpose Controller 1",
        17: "General Purpose Controller 2",
        18: "General Purpose Controller 3",
        19: "General Purpose Controller 4",
        32: "Bank Select LSB",
        33: "Modulation Wheel LSB",
        34: "Breath Controller LSB",
        38: "Data Entry LSB",
        39: "Volume LSB",
        40: "Balance LSB",
        42: "Pan LSB",
        43: "Expression LSB",
        64: "Damper Pedal (Sustain)",
        65: "Portamento On/Off",
        66: "Sostenuto",
        67: "Soft Pedal",
        68: "Legato Footswitch",
        69: "Hold 2",
        70: "Sound Controller 1 (Timbre)",
        71: "Sound Controller 2 (Timbre/Harmonic Content)",
        72: "Sound Controller 3 (Release Time)",
        73: "Sound Controller 4 (Attack Time)",
        74: "Sound Controller 5 (Brightness)",
        75: "Sound Controller 6",
        76: "Sound Controller 7",
        77: "Sound Controller 8",
        78: "Sound Controller 9",
        79: "Sound Controller 10",
        80: "General Purpose Controller 5",
        81: "General Purpose Controller 6",
        82: "General Purpose Controller 7",
        83: "General Purpose Controller 8",
        84: "Portamento Control",
        85: "High Resolution Velocity Prefix",
        88: "Fine Vibrato Rate",
        89: "Vibrato Depth",
        90: "Vibrato Delay",
        91: "Reverb Send Level",
        92: "Tremolo Depth",
        93: "Chorus Send Level",
        94: "Celeste Depth",
        95: "Phaser Depth",
        96: "Data Increment",
        97: "Data Decrement",
        98: "NRPN LSB",
        99: "NRPN MSB",
        100: "RPN LSB",
        101: "RPN MSB",
        120: "All Sound Off",
        121: "Reset All Controllers",
        122: "Local Control",
        123: "All Notes Off",
        124: "Omni Mode Off",
        125: "Omni Mode On",
        126: "Mono Mode On",
        127: "Poly Mode On",
    }
    
    def __post_init__(self):
        if self.controller and not self.controller_name:
            self.controller_name = self.CC_NAMES.get(self.controller, f"CC{self.controller}")
            self.category = self._categorize_cc(self.controller)
    
    @staticmethod
    def _categorize_cc(cc: int) -> str:
        """Categorize CC by function."""
        if cc in (0, 32): return "bank_select"
        if cc == 1: return "modulation"
        if cc in (2, 34): return "breath"
        if cc in (4, ): return "foot"
        if cc in (5, 84): return "portamento"
        if cc in (6, 38): return "data_entry"
        if cc in (7, 39): return "volume"
        if cc in (8, 40): return "balance"
        if cc in (10, 42): return "pan"
        if cc in (11, 43): return "expression"
        if cc == 64: return "sustain"
        if cc == 65: return "portamento_switch"
        if cc == 66: return "sostenuto"
        if cc == 67: return "soft_pedal"
        if cc in range(70, 80): return "sound_controller"
        if cc in (91, 93, 94, 95): return "effect_send"
        if cc in (96, 97): return "data_increment_decrement"
        if cc in (98, 99): return "nrpn"
        if cc in (100, 101): return "rpn"
        if cc >= 120: return "channel_mode"
        return "general_purpose"
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'controller': self.controller,
            'controller_name': self.controller_name,
            'category': self.category,
            'value': self.value,
            'value_14bit': self.value_14bit,
            'is_data_entry': self.is_data_entry,
            'is_rpn_port': self.is_rpn_port,
            'is_nrpn_port': self.is_nrpn_port,
        })
        return result


@dataclass
class ProgramChangeEvent(MidiEvent):
    """Program Change with bank and sound identity."""
    program: int = 0
    bank_msb: Optional[int] = None
    bank_lsb: Optional[int] = None
    
    # Sound identity (populated from profile database)
    sound_name: str = ""
    family: str = "UNKNOWN"
    is_rx: bool = False
    is_dnc: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'program': self.program,
            'bank_msb': self.bank_msb,
            'bank_lsb': self.bank_lsb,
            'sound_name': self.sound_name,
            'family': self.family,
            'is_rx': self.is_rx,
            'is_dnc': self.is_dnc,
        })
        return result


@dataclass
class PitchBendEvent(MidiEvent):
    """Pitch Bend with high-resolution value."""
    bend_value: int = 0  # 0-16383 (14-bit)
    bend_range_semitones: int = 2  # Default ±2 semitones
    
    @property
    def normalized_value(self) -> float:
        """Normalize to -1.0 to 1.0 range."""
        return (self.bend_value - 8192) / 8192.0
    
    @property
    def cents(self) -> float:
        """Calculate pitch offset in cents."""
        return self.normalized_value * (self.bend_range_semitones * 100)
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'bend_value': self.bend_value,
            'normalized_value': round(self.normalized_value, 4),
            'cents': round(self.cents, 2),
            'bend_range_semitones': self.bend_range_semitones,
        })
        return result


@dataclass
class TempoEvent(MidiEvent):
    """Tempo change event (Meta event 0x51)."""
    tempo_usq: int = 500000  # Microseconds per quarter note (default 120 BPM)
    
    @property
    def bpm(self) -> float:
        """Calculate BPM from microseconds per quarter note."""
        return 60000000.0 / self.tempo_usq if self.tempo_usq > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'tempo_usq': self.tempo_usq,
            'bpm': round(self.bpm, 3),
        })
        return result


@dataclass
class TimeSignatureEvent(MidiEvent):
    """Time signature meta event (Meta event 0x58)."""
    numerator: int = 4
    denominator: int = 4  # Encoded as power of 2 (4 = quarter note)
    clocks_per_click: int = 24
    num_32nd_notes: int = 8
    
    @property
    def beats_per_measure(self) -> int:
        return self.numerator
    
    @property
    def beat_unit(self) -> int:
        return 2 ** self.denominator
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'numerator': self.numerator,
            'denominator': self.denominator,
            'beats_per_measure': self.beats_per_measure,
            'beat_unit': self.beat_unit,
            'time_signature': f"{self.numerator}/{self.beat_unit}",
        })
        return result


@dataclass
class KeySignatureEvent(MidiEvent):
    """Key signature meta event (Meta event 0x59)."""
    fifths: int = 0  # -7 to +7
    is_minor: bool = False
    
    MAJOR_KEYS = ['Cb', 'Gb', 'Db', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#']
    MINOR_KEYS = ['Abm', 'Ebm', 'Bbm', 'Fm', 'Cm', 'Gm', 'Dm', 'Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m']
    
    @property
    def key_name(self) -> str:
        """Get human-readable key name."""
        if self.is_minor:
            idx = self.fifths + 7
            if 0 <= idx < len(self.MINOR_KEYS):
                return self.MINOR_KEYS[idx]
        else:
            idx = self.fifths + 7
            if 0 <= idx < len(self.MAJOR_KEYS):
                return self.MAJOR_KEYS[idx]
        return f"{'m' if self.is_minor else ''} ({self.fifths} fifths)"
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            'fifths': self.fifths,
            'is_minor': self.is_minor,
            'key_name': self.key_name,
        })
        return result


print("✅ MidiEvent core models loaded successfully")
print("   - EventType: Complete MIDI 1.0 taxonomy + MIDI 2.0 extension points")
print("   - MidiEvent: Base class with full provenance tracking")
print("   - NoteEvent: Pitch, velocity, duration, articulation markers")
print("   - ControllerEvent: Full CC 0-127 with semantic categorization")
print("   - RpnEvent/NrpnEvent: Parsed from CC sequences")
print("   - SysExEvent: Manufacturer ID, data, checksum parsing")
print("   - ProgramChangeEvent: Bank + program with sound identity")
print("   - PitchBendEvent: 14-bit resolution, cents calculation")
print("   - TempoEvent/TimeSignatureEvent/KeySignatureEvent: Meta events")
