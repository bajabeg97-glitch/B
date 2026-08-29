"""
ULTIMATE MIDI CORE - LOSSLESS REPRESENTATION LAYER

Ovaj modul definiše hijerarhijski model za MIDI reprezentaciju koji omogućava:
- Potpuno očuvanje originalnih podataka (Lossless)
- Non-destructive editing sa audit trail-om
- Praćenje promjena, generisanih događaja i izvora
- Podršku za sve MIDI 1.0 događaje uključujući RPN/NRPN i SysEx
- Pripremu za MIDI 2.0/UMP strukture
- Mikrotonalne pomake i izražajne metapodatke

Struktura:
MidiProject (kontejner za cijeli projekt)
└── MidiDocument (SMF struktura: header, PPQN, format)
    └── MidiTrack (lista događaja po track-u)
        └── MidiEvent (baza za sve tipove događaja)
            ├── NoteEvent
            ├── ControllerEvent (uključujući RPN/NRPN)
            ├── ProgramEvent
            ├── PitchBendEvent
            ├── AftertouchEvent
            ├── SysExEvent
            └── MetaEvent (Tempo, Meter, Marker, itd.)
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union, Tuple
from enum import Enum
from datetime import datetime
import uuid


class EventType(Enum):
    """Tipovi MIDI događaja"""
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    POLY_PRESSURE = "poly_pressure"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"
    CHANNEL_PRESSURE = "channel_pressure"
    PITCH_BEND = "pitch_bend"
    SYSTEM_EXCLUSIVE = "system_exclusive"
    SYSEX_END = "sysex_end"
    TIME_CODE = "time_code"
    SONG_POSITION = "song_position"
    SONG_SELECT = "song_select"
    TUNE_REQUEST = "tune_request"
    CLOCK = "clock"
    START = "start"
    CONTINUE = "continue"
    STOP = "stop"
    ACTIVE_SENSING = "active_sensing"
    SYSTEM_RESET = "system_reset"
    SEQUENCE_NUMBER = "sequence_number"
    TEXT_EVENT = "text_event"
    COPYRIGHT = "copyright"
    TRACK_NAME = "track_name"
    INSTRUMENT_NAME = "instrument_name"
    LYRICS = "lyrics"
    MARKER = "marker"
    CUE_POINT = "cue_point"
    CHANNEL_PREFIX = "channel_prefix"
    MIDI_PORT = "midi_port"
    END_OF_TRACK = "end_of_track"
    SET_TEMPO = "set_tempo"
    SMPTE_OFFSET = "smpte_offset"
    SEQUENCE_TRACK_NAME = "sequence_track_name"
    RPN = "rpn"
    NRPN = "nrpn"
    UNKNOWN = "unknown"


class ChangeType(Enum):
    """Tipovi promjena za audit trail"""
    UNCHANGED = "unchanged"
    USER_EDIT = "user_edit"
    REPAIR = "repair"
    OPTIMIZATION = "optimization"
    ARTICULATION = "articulation"
    GENERATION = "generation"
    TRANSFER = "transfer"
    QUANTIZE = "quantize"
    HUMANIZE = "humanize"
    TRANSPOSE = "transpose"
    REHARMONIZE = "reharmonize"
    REBUILD = "rebuild"
    CLEANUP = "cleanup"


class ProcessingMode(Enum):
    """Režimi obrade iz Master Plana"""
    PRESERVE = "preserve"      # Mode A
    REPAIR = "repair"          # Mode B
    TRANSFORM = "transform"    # Mode C
    REBUILD = "rebuild"        # Mode D
    GENERATE = "generate"      # Mode E
    EXPERIMENTAL = "experimental"  # Mode F


@dataclass
class SourceInfo:
    """Informacije o izvoru događaja"""
    source_type: str = 'unknown'  # 'file', 'user', 'ai', 'transfer', 'generator'
    source_id: Optional[str] = None  # ID fajla, sessiona, modela
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # 0.0 - 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Zapis o promjeni događaja"""
    change_type: ChangeType
    timestamp: datetime
    previous_value: Optional[Any] = None
    new_value: Optional[Any] = None
    reason: Optional[str] = None
    engine: Optional[str] = None
    mode: ProcessingMode = ProcessingMode.PRESERVE


@dataclass
class MidiEvent:
    """
    Bazna klasa za sve MIDI događaje.
    
    Svaki događaj ima:
    - event_id: jedinstveni ID
    - original_event_id: link na original ako je modificiran
    - absolute_tick: apsolutna pozicija u tickovima
    - delta_tick: delta od prethodnog događaja
    - measure, beat, subbeat: muzička pozicija
    - changed: da li je modificiran
    - generated: da li je generisan (nije iz originala)
    - source: informacije o izvoru
    - audit_trail: lista svih promjena
    - raw_bytes: sirovi bajtovi ako su dostupni
    """
    
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_event_id: Optional[str] = None
    track_index: int = 0
    channel: int = 0
    absolute_tick: int = 0
    delta_tick: int = 0
    measure: int = 0
    beat: int = 0
    subbeat: int = 0
    original_index: int = 0
    event_type: EventType = EventType.UNKNOWN
    raw_bytes: Optional[bytes] = None
    
    # Status promjena
    changed: bool = False
    generated: bool = False
    source: SourceInfo = field(default_factory=SourceInfo)
    audit_trail: List[AuditEntry] = field(default_factory=list)
    
    # Dodatni podaci specifični za tip događaja
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Mikrotonalni i izražajni podaci (za buduće proširenje)
    microtonal_offset: float = 0.0  # u centima, 0 = standardni pitch
    expression_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_audit_entry(self, change_type: ChangeType, 
                       previous_value: Any, 
                       new_value: Any,
                       reason: Optional[str] = None,
                       engine: Optional[str] = None,
                       mode: ProcessingMode = ProcessingMode.PRESERVE):
        """Dodaje zapis u audit trail"""
        entry = AuditEntry(
            change_type=change_type,
            timestamp=datetime.now(),
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            engine=engine,
            mode=mode
        )
        self.audit_trail.append(entry)
        if change_type != ChangeType.UNCHANGED:
            self.changed = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuje u dictionary za serializaciju"""
        return {
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
            'changed': self.changed,
            'generated': self.generated,
            'source': {
                'source_type': self.source.source_type,
                'source_id': self.source.source_id,
                'timestamp': self.source.timestamp.isoformat(),
                'confidence': self.source.confidence,
                'metadata': self.source.metadata
            },
            'audit_trail': [
                {
                    'change_type': entry.change_type.value,
                    'timestamp': entry.timestamp.isoformat(),
                    'previous_value': entry.previous_value,
                    'new_value': entry.new_value,
                    'reason': entry.reason,
                    'engine': entry.engine,
                    'mode': entry.mode.value
                }
                for entry in self.audit_trail
            ],
            'data': self.data,
            'microtonal_offset': self.microtonal_offset,
            'expression_data': self.expression_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MidiEvent':
        """Kreira instancu iz dictionary-a"""
        event = cls()
        event.event_id = data.get('event_id', str(uuid.uuid4()))
        event.original_event_id = data.get('original_event_id')
        event.track_index = data.get('track_index', 0)
        event.channel = data.get('channel', 0)
        event.absolute_tick = data.get('absolute_tick', 0)
        event.delta_tick = data.get('delta_tick', 0)
        event.measure = data.get('measure', 0)
        event.beat = data.get('beat', 0)
        event.subbeat = data.get('subbeat', 0)
        event.original_index = data.get('original_index', 0)
        event.event_type = EventType(data.get('event_type', 'unknown'))
        event.changed = data.get('changed', False)
        event.generated = data.get('generated', False)
        
        source_data = data.get('source', {})
        event.source = SourceInfo(
            source_type=source_data.get('source_type', 'unknown'),
            source_id=source_data.get('source_id'),
            timestamp=datetime.fromisoformat(source_data['timestamp']) if 'timestamp' in source_data else datetime.now(),
            confidence=source_data.get('confidence', 1.0),
            metadata=source_data.get('metadata', {})
        )
        
        audit_data = data.get('audit_trail', [])
        event.audit_trail = [
            AuditEntry(
                change_type=ChangeType(entry['change_type']),
                timestamp=datetime.fromisoformat(entry['timestamp']),
                previous_value=entry.get('previous_value'),
                new_value=entry.get('new_value'),
                reason=entry.get('reason'),
                engine=entry.get('engine'),
                mode=ProcessingMode(entry.get('mode', 'preserve'))
            )
            for entry in audit_data
        ]
        
        event.data = data.get('data', {})
        event.microtonal_offset = data.get('microtonal_offset', 0.0)
        event.expression_data = data.get('expression_data', {})
        
        return event


@dataclass
class NoteEvent(MidiEvent):
    """
    Note On / Note Off događaj.
    
    Podržava:
    - velocity i release_velocity
    - duration i gate time
    - note_off kao linked event
    - artikulacijske metapodatke
    """
    
    document: Optional['MidiDocument'] = None
    track: Optional['MidiTrack'] = None
    note_on: bool = True  # True = Note On, False = Note Off
    pitch: int = 60  # 0-127
    velocity: int = 64  # 0-127
    release_velocity: int = 0  # Note Off velocity (često ignorisan ali važan)
    duration_ticks: int = 0
    duration: int = 0  # alias za duration_ticks
    gate_time: float = 0.0  # u odnosu na duration (1.0 = full)
    channel: int = 0
    absolute_tick: int = 0
    delta_tick: int = 0
    
    # Link na povezani Note Off događaj
    linked_note_off: Optional[str] = None
    
    # Artikulacija i izraz
    articulation: Optional[str] = None  # 'normal', 'staccato', 'legato', 'accent', 'ghost'
    ornament: Optional[str] = None  # 'trill', 'mordent', 'turn', 'grace'
    
    def __post_init__(self):
        self.event_type = EventType.NOTE_ON if self.note_on else EventType.NOTE_OFF
        if self.duration == 0 and self.duration_ticks > 0:
            self.duration = self.duration_ticks
        self.data.update({
            'pitch': self.pitch,
            'velocity': self.velocity,
            'release_velocity': self.release_velocity,
            'duration_ticks': self.duration_ticks,
            'gate_time': self.gate_time,
            'articulation': self.articulation,
            'ornament': self.ornament
        })
        
        # Dodaj event na track ako je proslijeđen
        if self.track is not None:
            self.track.add_event(self)
    
    @property
    def note_name(self) -> str:
        """Vraća ime note (npr. C#4)"""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (self.pitch // 12) - 1
        note = notes[self.pitch % 12]
        return f"{note}{octave}"

    @property
    def note(self) -> int:
        """Alias for pitch (engine compatibility)."""
        return self.pitch

    @note.setter
    def note(self, value: int) -> None:
        self.pitch = int(value)
        self.data['pitch'] = self.pitch

    @property
    def is_note_on(self) -> bool:
        return bool(self.note_on)
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'note_on': self.note_on,
            'pitch': self.pitch,
            'velocity': self.velocity,
            'release_velocity': self.release_velocity,
            'duration_ticks': self.duration_ticks,
            'gate_time': self.gate_time,
            'linked_note_off': self.linked_note_off,
            'articulation': self.articulation,
            'ornament': self.ornament,
            'note_name': self.note_name
        })
        return base


@dataclass
class ControllerEvent(MidiEvent):
    """
    Control Change događaj.
    
    Posebna podrška za:
    - RPN (Registered Parameter Numbers)
    - NRPN (Non-Registered Parameter Numbers)
    - Standard CC mapping
    """
    
    document: Optional['MidiDocument'] = None
    track: Optional['MidiTrack'] = None
    cc_number: int = 0  # 0-127
    value: int = 0  # 0-127
    channel: int = 0
    absolute_tick: int = 0
    delta_tick: int = 0
    
    # Za RPN/NRPN sekvence
    is_rpn: bool = False
    is_nrpn: bool = False
    rpn_number: Optional[int] = None
    nrpn_number: Optional[int] = None
    rpn_value: Optional[int] = None  # Kombinirana vrijednost (MSB + LSB)
    
    # CC ime ako je poznato
    cc_name: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.CONTROL_CHANGE
        
        if self.is_rpn:
            self.event_type = EventType.RPN
            self.cc_name = f"RPN {self.rpn_number}"
        elif self.is_nrpn:
            self.event_type = EventType.NRPN
            self.cc_name = f"NRPN {self.nrpn_number}"
        else:
            self.cc_name = self._get_cc_name()
        
        self.data.update({
            'cc_number': self.cc_number,
            'value': self.value,
            'is_rpn': self.is_rpn,
            'is_nrpn': self.is_nrpn,
            'rpn_number': self.rpn_number,
            'nrpn_number': self.nrpn_number,
            'rpn_value': self.rpn_value,
            'cc_name': self.cc_name
        })
        
        # Dodaj event na track ako je proslijeđen
        if self.track is not None:
            self.track.add_event(self)
    
    def _get_cc_name(self) -> str:
        """Vraća ljudsko čitljivo ime za standardne CC brojeve"""
        cc_names = {
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
            64: "Sustain Pedal",
            65: "Portamento",
            66: "Sostenuto",
            67: "Soft Pedal",
            68: "Legato Footswitch",
            69: "Hold 2",
            70: "Sound Controller 1",
            71: "Sound Controller 2",
            72: "Sound Controller 3",
            73: "Sound Controller 4",
            74: "Sound Controller 5",
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
            88: "High Resolution Velocity Prefix",
            91: "Effects 1 Depth",
            92: "Effects 2 Depth",
            93: "Effects 3 Depth",
            94: "Effects 4 Depth",
            95: "Effects 5 Depth",
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
            124: "Omni Off",
            125: "Omni On",
            126: "Mono On",
            127: "Poly On"
        }
        return cc_names.get(self.cc_number, f"CC {self.cc_number}")


@dataclass
class ProgramEvent(MidiEvent):
    """Program Change događaj"""
    
    program: int = 0  # 0-127
    bank_msb: int = 0  # Bank Select MSB
    bank_lsb: int = 0  # Bank Select LSB
    
    # Ime instrumenta ako je poznato
    instrument_name: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.PROGRAM_CHANGE
        self.data.update({
            'program': self.program,
            'bank_msb': self.bank_msb,
            'bank_lsb': self.bank_lsb,
            'instrument_name': self.instrument_name
        })


@dataclass
class PitchBendEvent(MidiEvent):
    """Pitch Bend događaj"""
    
    value: int = 8192  # 0-16383, 8192 = center
    bend_range_semitones: int = 2  # Očekivani range
    
    def __post_init__(self):
        self.event_type = EventType.PITCH_BEND
        # Izračunaj bend u semitonima
        normalized = (self.value - 8192) / 8192.0
        self.bend_semitones = normalized * self.bend_range_semitones
        self.data.update({
            'value': self.value,
            'bend_range_semitones': self.bend_range_semitones,
            'bend_semitones': self.bend_semitones
        })


@dataclass
class AftertouchEvent(MidiEvent):
    """Aftertouch događaj (Channel ili Polyphonic)"""
    
    is_polyphonic: bool = False
    pitch: Optional[int] = None  # Samo za polyphonic
    pressure: int = 0  # 0-127
    
    def __post_init__(self):
        self.event_type = EventType.POLY_PRESSURE if self.is_polyphonic else EventType.CHANNEL_PRESSURE
        self.data.update({
            'is_polyphonic': self.is_polyphonic,
            'pitch': self.pitch,
            'pressure': self.pressure
        })


@dataclass
class SysExEvent(MidiEvent):
    """
    System Exclusive događaj.
    
    Podržava:
    - HEX prikaz
    - Parser za Manufacturer ID
    - Checksum validaciju
    - Template matching
    """
    
    data_bytes: bytes = field(default_factory=bytes)
    manufacturer_id: Optional[int] = None
    device_id: Optional[int] = None
    model_id: Optional[int] = None
    checksum: Optional[int] = None
    checksum_valid: Optional[bool] = None
    
    def __post_init__(self):
        self.event_type = EventType.SYSTEM_EXCLUSIVE
        if self.data_bytes:
            self._parse_sysex()
        self.data.update({
            'data_bytes': list(self.data_bytes),
            'manufacturer_id': self.manufacturer_id,
            'device_id': self.device_id,
            'model_id': self.model_id,
            'checksum': self.checksum,
            'checksum_valid': self.checksum_valid,
            'hex_string': self.data_bytes.hex().upper()
        })
    
    def _parse_sysex(self):
        """Parsira SysEx bajtove za osnovne informacije"""
        if len(self.data_bytes) < 3:
            return
        
        # Prvi bajt mora biti 0xF0
        if self.data_bytes[0] != 0xF0:
            return
        
        # Manufacturer ID (1 ili 3 bajta)
        man_id = self.data_bytes[1]
        if man_id == 0x00:
            # Extended manufacturer ID (3 bajta)
            if len(self.data_bytes) >= 4:
                self.manufacturer_id = (man_id << 16) | (self.data_bytes[2] << 8) | self.data_bytes[3]
                offset = 4
            else:
                return
        else:
            self.manufacturer_id = man_id
            offset = 2
        
        # Device ID i Model ID (zavisi od proizvođača)
        if len(self.data_bytes) > offset:
            self.device_id = self.data_bytes[offset]
        if len(self.data_bytes) > offset + 1:
            self.model_id = self.data_bytes[offset + 1]
        
        # Checksum (posljednji bajt prije 0xF7)
        if self.data_bytes[-1] == 0xF7 and len(self.data_bytes) > 2:
            # Jednostavna checksum logika (može se proširiti)
            self.checksum = self.data_bytes[-2]
            # Validacija zavisi od proizvođača


@dataclass
class MetaEvent(MidiEvent):
    """
    Meta događaji (nisu MIDI poruke već SMF metapodaci).
    """
    
    meta_type: int = 0
    text: Optional[str] = None
    tempo: Optional[int] = None  # microseconds per quarter note
    numerator: Optional[int] = None  # za Time Signature
    denominator: Optional[int] = None
    clocks_per_click: Optional[int] = None
    num_32nds: Optional[int] = None
    smpte_format: Optional[int] = None
    hours: Optional[int] = None
    minutes: Optional[int] = None
    seconds: Optional[int] = None
    frames: Optional[int] = None
    sub_frames: Optional[int] = None
    
    def __post_init__(self):
        # Mapiranje meta tipa u EventType
        type_mapping = {
            0x00: EventType.SEQUENCE_NUMBER,
            0x01: EventType.TEXT_EVENT,
            0x02: EventType.COPYRIGHT,
            0x03: EventType.TRACK_NAME,
            0x04: EventType.INSTRUMENT_NAME,
            0x05: EventType.LYRICS,
            0x06: EventType.MARKER,
            0x07: EventType.CUE_POINT,
            0x20: EventType.CHANNEL_PREFIX,
            0x21: EventType.MIDI_PORT,
            0x2F: EventType.END_OF_TRACK,
            0x51: EventType.SET_TEMPO,
            0x54: EventType.SMPTE_OFFSET,
            0x58: EventType.SEQUENCE_TRACK_NAME,
        }
        self.event_type = type_mapping.get(self.meta_type, EventType.UNKNOWN)
        
        self.data.update({
            'meta_type': self.meta_type,
            'text': self.text,
            'tempo': self.tempo,
            'numerator': self.numerator,
            'denominator': self.denominator,
            'clocks_per_click': self.clocks_per_click,
            'num_32nds': self.num_32nds,
            'smpte_format': self.smpte_format,
            'hours': self.hours,
            'minutes': self.minutes,
            'seconds': self.seconds,
            'frames': self.frames,
            'sub_frames': self.sub_frames
        })


# Specijalizirani MetaEvent podtipovi za lakšu upotrebu
@dataclass
class TempoEvent(MetaEvent):
    """Tempo change event"""
    def __post_init__(self):
        self.meta_type = 0x51
        super().__post_init__()


@dataclass
class MeterEvent(MetaEvent):
    """Time signature event"""
    def __post_init__(self):
        self.meta_type = 0x58
        super().__post_init__()


@dataclass
class MarkerEvent(MetaEvent):
    """Marker event"""
    def __post_init__(self):
        self.meta_type = 0x06
        super().__post_init__()


@dataclass
class LyricsEvent(MetaEvent):
    """Lyrics event"""
    def __post_init__(self):
        self.meta_type = 0x05
        super().__post_init__()


@dataclass
class TextEvent(MetaEvent):
    """Text event"""
    def __post_init__(self):
        self.meta_type = 0x01
        super().__post_init__()


@dataclass
class TrackNameEvent(MetaEvent):
    """Track name event"""
    def __post_init__(self):
        self.meta_type = 0x03
        super().__post_init__()


@dataclass
class InstrumentNameEvent(MetaEvent):
    """Instrument name event"""
    def __post_init__(self):
        self.meta_type = 0x04
        super().__post_init__()


@dataclass
class CopyrightEvent(MetaEvent):
    """Copyright event"""
    def __post_init__(self):
        self.meta_type = 0x02
        super().__post_init__()


@dataclass
class EndTrackEvent(MetaEvent):
    """End of track event"""
    def __post_init__(self):
        self.meta_type = 0x2F
        super().__post_init__()


@dataclass
class SequenceNumberEvent(MetaEvent):
    """Sequence number event"""
    def __post_init__(self):
        self.meta_type = 0x00
        super().__post_init__()


@dataclass
class CuePointEvent(MetaEvent):
    """Cue point event"""
    def __post_init__(self):
        self.meta_type = 0x07
        super().__post_init__()


@dataclass
class PortNameEvent(MetaEvent):
    """MIDI port name event"""
    def __post_init__(self):
        self.meta_type = 0x09
        super().__post_init__()


@dataclass
class DeviceNameEvent(MetaEvent):
    """Device name event"""
    def __post_init__(self):
        self.meta_type = 0x09
        super().__post_init__()


@dataclass
class MidiTrack:
    """
    Reprezentacija MIDI track-a.
    
    Sadrži:
    - Listu MidiEvent objekata
    - Metapodatke track-a
    - Informacije o kanalu/instrumentu
    """
    
    document: Optional['MidiDocument'] = None
    track_index: int = 0
    name: str = ""
    channel: int = 0
    instrument: Optional[str] = None
    program: int = 0
    bank_msb: int = 0
    bank_lsb: int = 0
    
    events: List[MidiEvent] = field(default_factory=list)
    
    # Analitički podaci
    note_count: int = 0
    controller_count: int = 0
    has_drums: bool = False
    pitch_range: Tuple[int, int] = (0, 127)
    velocity_range: Tuple[int, int] = (0, 127)
    
    # Originalni podaci
    original_event_count: int = 0
    hash: str = ""
    
    def __post_init__(self):
        self._update_analytics()
    
    def add_event(self, event: MidiEvent):
        """Dodaje događaj na track"""
        event.track_index = self.track_index
        self.events.append(event)
        self._update_analytics()
    
    def remove_event(self, event_id: str) -> bool:
        """Uklanja događaj sa track-a"""
        for i, event in enumerate(self.events):
            if event.event_id == event_id:
                self.events.pop(i)
                self._update_analytics()
                return True
        return False

    def remove_event_by_id(self, event_id: int) -> bool:
        """Uklanja događaj po ID-u (alias za remove_event radi kompatibilnosti)"""
        return self.remove_event(str(event_id))

    def get_event_by_id(self, event_id) -> Optional['MidiEvent']:
        """Pronalazi događaj po ID-u (string UUID ili int)."""
        sid = str(event_id)
        for event in self.events:
            if str(event.event_id) == sid:
                return event
        return None

    def is_empty(self) -> bool:
        return not self.events

    def get_program_change(self) -> int:
        for event in self.events:
            if isinstance(event, ProgramEvent):
                return event.program
        return self.program

    def get_duration_bars(self, ppqn: int = 480, beats: int = 4) -> int:
        if not self.events:
            return 1
        max_tick = max(event.absolute_tick for event in self.events)
        ticks_per_bar = max(1, ppqn * beats)
        return max(1, (max_tick + ticks_per_bar - 1) // ticks_per_bar)

    def get_absolute_tick_max(self) -> int:
        if not self.events:
            return 0
        return max(event.absolute_tick for event in self.events)

    def program_change(self, channel: int, program: int) -> None:
        self.channel = channel
        self.program = program
        self.add_event(ProgramEvent(program=program, channel=channel, absolute_tick=0))

    def add_note(self, a=None, b=None, c=None, d=None, *, pitch=None, tick=None,
                 duration=None, velocity=None):
        """
        Add a note-on/note-off pair.

        Keyword form: add_note(tick=..., duration=..., pitch=..., velocity=...)
        Positional:
          - duration > 127 → (pitch, tick, velocity, duration)  [Suno]
          - otherwise       → (tick, duration, pitch, velocity) [generators]
        """
        if pitch is not None and tick is not None:
            duration = 480 if duration is None else duration
            velocity = 64 if velocity is None else velocity
        elif None not in (a, b, c, d):
            if d > 127:
                pitch, tick, velocity, duration = a, b, c, d
            else:
                tick, duration, pitch, velocity = a, b, c, d
        else:
            raise TypeError("add_note requires keywords or four positional arguments")

        on = NoteEvent(
            note_on=True,
            pitch=int(pitch),
            velocity=int(velocity),
            absolute_tick=int(tick),
            duration_ticks=int(duration),
            duration=int(duration),
            channel=self.channel,
        )
        self.add_event(on)
        off = NoteEvent(
            note_on=False,
            pitch=int(pitch),
            velocity=0,
            absolute_tick=int(tick) + int(duration),
            channel=self.channel,
        )
        self.add_event(off)
        return on
    
    def _update_analytics(self):
        """Ažurira analitičke podatke track-a"""
        self.note_count = sum(1 for e in self.events if isinstance(e, NoteEvent) and e.note_on)
        self.controller_count = sum(1 for e in self.events if isinstance(e, ControllerEvent))
        self.has_drums = self.channel == 9  # Channel 10 (0-indexed = 9)
        
        pitches = [e.pitch for e in self.events if isinstance(e, NoteEvent) and e.note_on]
        velocities = [e.velocity for e in self.events if isinstance(e, NoteEvent) and e.note_on]
        
        if pitches:
            self.pitch_range = (min(pitches), max(pitches))
        if velocities:
            self.velocity_range = (min(velocities), max(velocities))
        
        self.original_event_count = sum(1 for e in self.events if not e.generated)
        
        # Izračunaj hash sadržaja
        content = json.dumps([e.to_dict() for e in self.events], sort_keys=True)
        self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_events_by_type(self, event_type: EventType) -> List[MidiEvent]:
        """Vraća sve događaje određenog tipa"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_notes_in_range(self, start_tick: int, end_tick: int) -> List[NoteEvent]:
        """Vraća note u vremenskom rasponu"""
        return [
            e for e in self.events 
            if isinstance(e, NoteEvent) and e.note_on 
            and start_tick <= e.absolute_tick <= end_tick
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuje u dictionary"""
        return {
            'track_index': self.track_index,
            'name': self.name,
            'channel': self.channel,
            'instrument': self.instrument,
            'program': self.program,
            'bank_msb': self.bank_msb,
            'bank_lsb': self.bank_lsb,
            'events': [e.to_dict() for e in self.events],
            'note_count': self.note_count,
            'controller_count': self.controller_count,
            'has_drums': self.has_drums,
            'pitch_range': self.pitch_range,
            'velocity_range': self.velocity_range,
            'original_event_count': self.original_event_count,
            'hash': self.hash
        }


@dataclass
class MidiDocument:
    """
    Reprezentacija SMF (Standard MIDI File) dokumenta.
    
    Sadrži:
    - Format (0, 1, 2)
    - PPQN (Pulses Per Quarter Note)
    - Liste track-ova
    - Tempo i meter map-e
    """
    
    ppqn: int = 480  # Standardni PPQN
    format: int = 1  # 0, 1, ili 2
    project: Optional['MidiProject'] = None  # Reference na parent project
    tracks: List[MidiTrack] = field(default_factory=list)
    
    # Globalne informacije
    tempo_map: List[Tuple[int, int]] = field(default_factory=list)  # (tick, microseconds_per_quarter)
    meter_map: List[Tuple[int, int, int]] = field(default_factory=list)  # (tick, numerator, denominator)
    key_signature: Optional[Tuple[int, bool]] = None  # (fifths, is_major)
    
    # Metapodaci
    copyright: Optional[str] = None
    sequence_name: Optional[str] = None
    
    # Analitički podaci
    total_ticks: int = 0
    duration_seconds: float = 0.0
    tempo_bpm: float = 120.0
    
    def __post_init__(self):
        self._calculate_duration()
    
    def add_track(self, track: Optional[MidiTrack] = None, name: str = "") -> MidiTrack:
        """Dodaje track i vraća ga (generatori očekuju objekat, ne index)."""
        if track is None:
            track = MidiTrack(document=self, name=name)
        else:
            track.document = self
            if name:
                track.name = name
        track.track_index = len(self.tracks)
        self.tracks.append(track)
        return track

    def get_tempo(self) -> float:
        return float(self.tempo_bpm)
    
    def remove_track(self, track_index: int) -> bool:
        """Uklanja track po indexu"""
        if 0 <= track_index < len(self.tracks):
            self.tracks.pop(track_index)
            # Re-index remaining tracks
            for i, track in enumerate(self.tracks):
                track.track_index = i
            return True
        return False
    
    def set_tempo(self, tick: int, microseconds_per_quarter: int):
        """Postavlja tempo na određenoj poziciji"""
        # Ukloni postojeći tempo na ovoj poziciji
        self.tempo_map = [(t, v) for t, v in self.tempo_map if t != tick]
        self.tempo_map.append((tick, microseconds_per_quarter))
        self.tempo_map.sort(key=lambda x: x[0])
        self._calculate_duration()
    
    def set_meter(self, tick: int, numerator: int, denominator: int):
        """Postavlja mjeru na određenoj poziciji"""
        self.meter_map = [(t, n, d) for t, n, d in self.meter_map if t != tick]
        self.meter_map.append((tick, numerator, denominator))
        self.meter_map.sort(key=lambda x: x[0])
    
    def _calculate_duration(self):
        """Izračunava trajanje pjesme u sekundama"""
        if not self.tempo_map:
            self.tempo_map = [(0, 500000)]  # Default 120 BPM
        
        total_ticks = 0
        total_seconds = 0.0
        current_tempo = 500000  # microseconds per quarter
        
        # Sortiraj sve događaje po tickovima
        all_events = []
        for track in self.tracks:
            for event in track.events:
                all_events.append(event.absolute_tick)
        
        if all_events:
            total_ticks = max(all_events)
        
        # Izračunaj vrijeme prolaskom kroz tempo promjene
        tempo_changes = sorted(self.tempo_map, key=lambda x: x[0])
        current_tick = 0
        
        for tempo_tick, tempo_value in tempo_changes:
            if tempo_tick > current_tick:
                ticks_in_segment = tempo_tick - current_tick
                quarters = ticks_in_segment / self.ppqn
                seconds = (quarters * tempo_value) / 1000000.0
                total_seconds += seconds
            
            current_tick = tempo_tick
            current_tempo = tempo_value
        
        # Dodaj preostalo vrijeme do kraja
        if total_ticks > current_tick:
            ticks_remaining = total_ticks - current_tick
            quarters = ticks_remaining / self.ppqn
            seconds = (quarters * current_tempo) / 1000000.0
            total_seconds += seconds
        
        self.total_ticks = total_ticks
        self.duration_seconds = total_seconds
        
        if self.tempo_map:
            self.tempo_bpm = 60000000.0 / self.tempo_map[0][1]
    
    def get_tempo_at_tick(self, tick: int) -> int:
        """Vraća tempo na određenoj poziciji"""
        if not self.tempo_map:
            return 500000
        
        current_tempo = 500000
        for tempo_tick, tempo_value in self.tempo_map:
            if tick >= tempo_tick:
                current_tempo = tempo_value
            else:
                break
        return current_tempo
    
    def get_meter_at_tick(self, tick: int) -> Tuple[int, int]:
        """Vraća mjeru na određenoj poziciji"""
        if not self.meter_map:
            return (4, 4)
        
        current_meter = (4, 4)
        for meter_tick, num, den in self.meter_map:
            if tick >= meter_tick:
                current_meter = (num, den)
            else:
                break
        return current_meter
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuje u dictionary"""
        return {
            'format': self.format,
            'ppqn': self.ppqn,
            'tracks': [t.to_dict() for t in self.tracks],
            'tempo_map': self.tempo_map,
            'meter_map': self.meter_map,
            'key_signature': self.key_signature,
            'copyright': self.copyright,
            'sequence_name': self.sequence_name,
            'total_ticks': self.total_ticks,
            'duration_seconds': self.duration_seconds,
            'tempo_bpm': self.tempo_bpm
        }


@dataclass
class MidiProject:
    """
    Glavni kontejner za cijeli MIDI projekt.
    
    Sadrži:
    - MidiDocument (SMF struktura)
    - Metapodatke projekta
    - Source informacije
    - Historiju izmjena (Undo/Redo)
    - Analitičke rezultate
    """
    
    name: str = "Untitled"
    source_file: Optional[str] = None
    document: MidiDocument = field(default_factory=MidiDocument)
    
    # Project metadata
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"
    
    # Source identification
    source_hash: str = ""
    original_filename: Optional[str] = None
    
    # Undo/Redo stack
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    redo_stack: List[Dict[str, Any]] = field(default_factory=list)
    
    # Analysis results
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    
    # Processing mode
    processing_mode: ProcessingMode = ProcessingMode.PRESERVE
    
    # Snapshots za non-destructive editing
    snapshots: Dict[str, MidiDocument] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.source_file:
            self.original_filename = self.source_file.split('/')[-1]
    
    def save_snapshot(self, name: str = "auto"):
        """Čuva snapshot trenutnog stanja"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{name}_{timestamp}"
        # Duboko kopiranje dokumenta
        self.snapshots[snapshot_name] = self.document
        return snapshot_name
    
    def restore_snapshot(self, name: str) -> bool:
        """Obnavlja snapshot"""
        if name in self.snapshots:
            self.document = self.snapshots[name]
            self.modified_at = datetime.now()
            return True
        return False
    
    def push_undo(self, action: Dict[str, Any]):
        """Dodaje akciju na undo stack"""
        self.undo_stack.append(action)
        self.redo_stack.clear()  # Clear redo na novu akciju
        self.modified_at = datetime.now()
    
    def undo(self) -> Optional[Dict[str, Any]]:
        """Vraća posljednju akciju"""
        if self.undo_stack:
            action = self.undo_stack.pop()
            self.redo_stack.append(action)
            return action
        return None
    
    def redo(self) -> Optional[Dict[str, Any]]:
        """Ponavlja posljednju undo akciju"""
        if self.redo_stack:
            action = self.redo_stack.pop()
            self.undo_stack.append(action)
            return action
        return None
    
    def analyze(self) -> Dict[str, Any]:
        """
        Vrši osnovnu analizu projekta.
        Ovo će biti prošireno sa posebnim Analyzer engine-om.
        """
        results = {
            'total_tracks': len(self.document.tracks),
            'total_notes': 0,
            'total_controllers': 0,
            'duration_seconds': self.document.duration_seconds,
            'tempo_bpm': self.document.tempo_bpm,
            'ppqn': self.document.ppqn,
            'format': self.document.format,
            'tracks_info': []
        }
        
        for track in self.document.tracks:
            track_info = {
                'index': track.track_index,
                'name': track.name,
                'channel': track.channel,
                'notes': track.note_count,
                'controllers': track.controller_count,
                'has_drums': track.has_drums,
                'pitch_range': track.pitch_range,
                'velocity_range': track.velocity_range,
                'program': track.program,
                'instrument': track.instrument
            }
            results['tracks_info'].append(track_info)
            results['total_notes'] += track.note_count
            results['total_controllers'] += track.controller_count
        
        self.analysis_results = results
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuje cijeli projekt u dictionary"""
        return {
            'name': self.name,
            'source_file': self.source_file,
            'original_filename': self.original_filename,
            'source_hash': self.source_hash,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'version': self.version,
            'document': self.document.to_dict(),
            'processing_mode': self.processing_mode.value,
            'analysis_results': self.analysis_results,
            'snapshot_count': len(self.snapshots),
            'undo_stack_size': len(self.undo_stack)
        }
    
    def get_summary(self) -> str:
        """Vraća tekstualni sažetak projekta"""
        summary = []
        summary.append(f"Project: {self.name}")
        summary.append(f"Source: {self.original_filename or 'New'}")
        summary.append(f"Format: SMF {self.document.format}, PPQN: {self.document.ppqn}")
        summary.append(f"Duration: {self.document.duration_seconds:.2f}s ({self.document.tempo_bpm:.1f} BPM)")
        summary.append(f"Tracks: {len(self.document.tracks)}")
        
        for track in self.document.tracks:
            if track.name or track.instrument:
                summary.append(f"  - Track {track.track_index}: {track.name or track.instrument} (Ch: {track.channel + 1})")
        
        return "\n".join(summary)

    @property
    def active_document(self) -> MidiDocument:
        return self.document

    @active_document.setter
    def active_document(self, doc: MidiDocument) -> None:
        self.document = doc
        if doc is not None:
            doc.project = self

    @property
    def ppqn(self) -> int:
        return self.document.ppqn

    @property
    def format_type(self) -> int:
        return self.document.format

    @classmethod
    def load(cls, filepath: str) -> "MidiProject":
        from core.io import load_midi
        return load_midi(filepath)

    def save(self, filepath: str) -> str:
        from core.io import save_midi
        save_midi(self, filepath)
        return filepath


# Helper funkcije za kreiranje događaja

def create_note_on(pitch: int, velocity: int, tick: int, channel: int = 0) -> NoteEvent:
    """Kreira Note On događaj"""
    return NoteEvent(
        note_on=True,
        pitch=pitch,
        velocity=velocity,
        absolute_tick=tick,
        channel=channel
    )


def create_note_off(pitch: int, tick: int, channel: int = 0, release_velocity: int = 0) -> NoteEvent:
    """Kreira Note Off događaj"""
    return NoteEvent(
        note_on=False,
        pitch=pitch,
        velocity=release_velocity,
        absolute_tick=tick,
        channel=channel
    )


def create_cc(cc_number: int, value: int, tick: int, channel: int = 0) -> ControllerEvent:
    """Kreira Control Change događaj"""
    return ControllerEvent(
        cc_number=cc_number,
        value=value,
        absolute_tick=tick,
        channel=channel
    )


def create_program_change(program: int, tick: int, channel: int = 0, 
                         bank_msb: int = 0, bank_lsb: int = 0) -> ProgramEvent:
    """Kreira Program Change događaj"""
    return ProgramEvent(
        program=program,
        bank_msb=bank_msb,
        bank_lsb=bank_lsb,
        absolute_tick=tick,
        channel=channel
    )


def create_pitch_bend(value: int, tick: int, channel: int = 0) -> PitchBendEvent:
    """Kreira Pitch Bend događaj"""
    return PitchBendEvent(
        value=value,
        absolute_tick=tick,
        channel=channel
    )


def create_tempo_change(tick: int, bpm: float) -> MetaEvent:
    """Kreira Tempo Change meta događaj"""
    microseconds_per_quarter = int(60000000 / bpm)
    return MetaEvent(
        meta_type=0x51,
        tempo=microseconds_per_quarter,
        absolute_tick=tick
    )


def create_time_signature(tick: int, numerator: int = 4, denominator: int = 4) -> MetaEvent:
    """Kreira Time Signature meta događaj"""
    return MetaEvent(
        meta_type=0x58,
        numerator=numerator,
        denominator=denominator,
        clocks_per_click=24,
        num_32nds=8,
        absolute_tick=tick
    )


def create_marker(tick: int, text: str) -> MetaEvent:
    """Kreira Marker meta događaj"""
    return MetaEvent(
        meta_type=0x06,
        text=text,
        absolute_tick=tick
    )
