"""
ULTIMATE MIDI WORKSTATION - CORE MODELS

Lossless MIDI Core Representation Layer
Supports: MIDI 1.0, MPE preparation, MIDI 2.0 UMP preparation
Non-destructive editing with full audit trail
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime
import hashlib
import uuid


class EventType(Enum):
    """Svi MIDI tipovi događaja"""
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    POLY_PRESSURE = "poly_pressure"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"
    CHANNEL_PRESSURE = "channel_pressure"
    PITCH_BEND = "pitch_bend"
    SYSTEM_EXCLUSIVE = "system_exclusive"
    SYSEX8 = "sysex8"  # MIDI 2.0
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
    LYRIC = "lyric"
    MARKER = "marker"
    CUE_POINT = "cue_point"
    PROGRAM_NAME = "program_name"
    DEVICE_NAME = "device_name"
    CHANNEL_PREFIX = "channel_prefix"
    MIDI_PORT = "midi_port"
    END_OF_TRACK = "end_of_track"
    TEMPO = "tempo"
    SMPTE_OFFSET = "smpte_offset"
    TIME_SIGNATURE = "time_signature"
    KEY_SIGNATURE = "key_signature"
    SEQUENCER_SPECIFIC = "sequencer_specific"
    RPN = "rpn"
    NRPN = "nrpn"
    UNKNOWN = "unknown"


class ProcessingMode(Enum):
    """Mode system iz Master Plana"""
    PRESERVE = "preserve"      # Mode A
    REPAIR = "repair"          # Mode B
    TRANSFORM = "transform"    # Mode C
    REBUILD = "rebuild"        # Mode D
    GENERATE = "generate"      # Mode E
    EXPERIMENTAL = "experimental"  # Mode F


class ChangeIntent(Enum):
    """Namjena svake promjene"""
    ORIGINAL = "original"
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
    VELOCITY_SCALE = "velocity_scale"
    GATE_ADJUST = "gate_adjust"
    TIMING_SHIFT = "timing_shift"
    CC_AUTOMATION = "cc_automation"
    PROGRAM_MAP = "program_map"
    CLEANUP = "cleanup"
    FORENSIC = "forensic"


class TrackRole(Enum):
    """Uloga tracka u aranžmanu"""
    UNDEFINED = "undefined"
    DRUMS = "drums"
    BASS = "bass"
    RHYTHM_GUITAR = "rhythm_guitar"
    LEAD_GUITAR = "lead_guitar"
    PIANO = "piano"
    STRINGS = "strings"
    PAD = "pad"
    BRASS = "brass"
    PERCUSSION = "percussion"
    SOLO = "solo"
    HARMONY = "harmony"
    COUNTERMELODY = "countermelody"
    FX = "fx"
    VOCALS = "vocals"
    STYLE_VAR1 = "style_var1"
    STYLE_VAR2 = "style_var2"
    STYLE_VAR3 = "style_var3"
    STYLE_VAR4 = "style_var4"
    STYLE_FILL = "style_fill"
    STYLE_BREAK = "style_break"
    STYLE_INTRO = "style_intro"
    STYLE_ENDING = "style_ending"


@dataclass
class ArticulationMap:
    """Mapiranje artikulacija za instrument (GAP 05)"""
    normal: List[int] = field(default_factory=list)  # note ranges
    legato: List[int] = field(default_factory=list)
    staccato: List[int] = field(default_factory=list)
    mute: List[int] = field(default_factory=list)
    palm_mute: List[int] = field(default_factory=list)
    slide: List[int] = field(default_factory=list)
    harmonic: List[int] = field(default_factory=list)
    accent: List[int] = field(default_factory=list)
    ghost: List[int] = field(default_factory=list)
    growl: List[int] = field(default_factory=list)
    fall: List[int] = field(default_factory=list)
    doit: List[int] = field(default_factory=list)
    trill: List[int] = field(default_factory=list)
    noise: List[int] = field(default_factory=list)
    custom: Dict[str, List[int]] = field(default_factory=dict)


@dataclass
class PerformanceIntent:
    """Meta-podatak za svrhu note (EXPANSION)"""
    role: str = "normal"  # normal, accent, ghost, approach, passing, neighbor
    tension_level: float = 0.0  # 0-1
    phrase_position: str = "middle"  # start, middle, end
    dynamic_arc: str = "steady"  # crescendo, diminuendo, steady
    articulation_confidence: float = 1.0
    human_feel_offset: int = 0  # namjerno odstupanje u tickovima
    is_or_nament: bool = False
    ornament_type: Optional[str] = None  # trill, mordent, turn, grace


@dataclass
class MicrotonalPitch:
    """Mikrotonalni pomak po noti (GAP)"""
    semitone: int = 0  # standardni MIDI note number
    cents_offset: float = 0.0  # -100 do +100 centi
    pitch_bend_value: int = 0  # raw pitch bend ako se koristi
    tuning_system: str = "12TET"  # 12TET, 19TET, 24TET, just, custom
    scale_degree: Optional[int] = None
    microtonal_accidental: Optional[str] = None  # quarter_sharp, three_quarter_flat, etc.


@dataclass
class RpnData:
    """RPN event podaci"""
    rpn_number: int  # 0-16383
    value_msb: int = 0
    value_lsb: int = 0
    value_combined: int = 0
    channel: int = 0
    absolute_tick: int = 0


@dataclass
class NrpnData:
    """NRPN event podaci"""
    nrpn_number: int  # 0-16383
    value_msb: int = 0
    value_lsb: int = 0
    value_combined: int = 0
    channel: int = 0
    absolute_tick: int = 0


@dataclass
class MidiEvent:
    """
    Univerzalni MIDI event sa punim metadata praćenjem.
    Svaki događaj ima unique ID i audit trail.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_event_id: Optional[str] = None
    
    # Pozicija u strukturi
    track_index: int = 0
    channel: int = 0
    absolute_tick: int = 0
    delta_tick: int = 0
    measure: int = 0
    beat: int = 0
    subbeat: int = 0
    original_index: int = 0  # indeks u originalnom fajlu
    
    # Tip i podaci
    event_type: EventType = EventType.UNKNOWN
    raw_bytes: Optional[bytes] = None
    
    # Note podaci
    note: Optional[int] = None
    note_name: Optional[str] = None
    velocity: int = 0
    release_velocity: int = 0
    duration_ticks: int = 0
    gate_percentage: float = 100.0
    
    # Controller podaci
    cc_number: Optional[int] = None
    cc_value: int = 0
    
    # Program/Bank
    program: Optional[int] = None
    bank_msb: Optional[int] = None
    bank_lsb: Optional[int] = None
    
    # Pitch/Pressure
    pitch_bend: Optional[int] = None
    pressure: Optional[int] = None  # Channel ili Poly pressure
    
    # SysEx
    sysex_data: Optional[bytes] = None
    manufacturer_id: Optional[int] = None
    device_id: Optional[int] = None
    model_id: Optional[int] = None
    
    # Meta events
    meta_type: Optional[int] = None
    text_data: Optional[str] = None
    tempo_bpm: Optional[float] = None
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    key_fifths: Optional[int] = None
    key_mode: Optional[int] = None  # 0=major, 1=minor
    
    # RPN/NRPN
    rpn_data: Optional[RpnData] = None
    nrpn_data: Optional[NrpnData] = None
    
    # Mikrotonalnost (GAP)
    microtonal: Optional[MicrotonalPitch] = None
    
    # Artikulacija i performansa
    performance_intent: Optional[PerformanceIntent] = None
    articulation_source: Optional[str] = None  # factory, gold, learned, inferred
    
    # Audit trail
    changed: bool = False
    generated: bool = False
    deleted: bool = False
    source: str = "file"  # file, user, engine, generator, transfer
    confidence: float = 1.0
    change_intent: ChangeIntent = ChangeIntent.ORIGINAL
    processing_mode: ProcessingMode = ProcessingMode.PRESERVE
    engine_version: Optional[str] = None
    timestamp_modified: Optional[datetime] = None
    reason: Optional[str] = None  # Zašto je promijenjen
    
    # Reference na roditeljske/izvedene evente
    parent_event_id: Optional[str] = None
    child_event_ids: List[str] = field(default_factory=list)
    
    # Additional context
    chord_root: Optional[int] = None
    chord_quality: Optional[str] = None
    scale_name: Optional[str] = None
    phrase_id: Optional[str] = None
    
    def __post_init__(self):
        if self.note is not None and self.note_name is None:
            self.note_name = self._note_to_name(self.note)

    @property
    def duration(self) -> int:
        return self.duration_ticks

    @duration.setter
    def duration(self, value: int) -> None:
        self.duration_ticks = int(value)

    @property
    def is_note_on(self) -> bool:
        return self.event_type == EventType.NOTE_ON

    @property
    def pitch(self) -> int:
        return int(self.note or 0)

    @pitch.setter
    def pitch(self, value: int) -> None:
        self.note = int(value)
        self.note_name = self._note_to_name(self.note)
    
    @staticmethod
    def _note_to_name(note: int) -> str:
        """Konvertuje MIDI note number u ime note"""
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = names[note % 12]
        return f"{name}{octave}"
    
    def clone(self, new_id: bool = True) -> 'MidiEvent':
        """Kreira kopiju eventa"""
        import copy
        cloned = copy.deepcopy(self)
        if new_id:
            cloned.event_id = str(uuid.uuid4())
            cloned.original_event_id = self.event_id
        return cloned
    
    def mark_changed(self, intent: ChangeIntent, reason: str, engine: str):
        """Označava event kao promijenjen sa audit podacima"""
        self.changed = True
        self.change_intent = intent
        self.reason = reason
        self.engine_version = engine
        self.timestamp_modified = datetime.now()
    
    def mark_generated(self, confidence: float, engine: str):
        """Označava event kao generisan"""
        self.generated = True
        self.confidence = confidence
        self.engine_version = engine
        self.source = "generator"
        self.timestamp_modified = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializacija u dictionary"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'track_index': self.track_index,
            'channel': self.channel,
            'absolute_tick': self.absolute_tick,
            'note': self.note,
            'velocity': self.velocity,
            'duration_ticks': self.duration_ticks,
            'cc_number': self.cc_number,
            'cc_value': self.cc_value,
            'changed': self.changed,
            'generated': self.generated,
            'change_intent': self.change_intent.value,
            'confidence': self.confidence
        }


@dataclass
class MidiTrack:
    """
    MIDI Track sa naprednim metapodacima
    """
    track_index: int = 0
    name: str = ""
    channel: int = 0  # Primary channel za monofone trackove
    channels: List[int] = field(default_factory=list)  # Svi korišteni kanali
    events: List[MidiEvent] = field(default_factory=list)
    
    # Metapodaci
    instrument_name: str = ""
    program: int = 0
    bank_msb: int = 0
    bank_lsb: int = 0
    is_drum_track: bool = False
    
    # Analitički podaci
    role: TrackRole = TrackRole.UNDEFINED
    detected_role_confidence: float = 0.0
    note_range_min: int = 0
    note_range_max: int = 0
    velocity_min: int = 0
    velocity_max: int = 0
    polyphony_max: int = 0
    total_notes: int = 0
    total_events: int = 0
    duration_ticks: int = 0
    duration_measures: int = 0
    
    # Articulation map (GAP 05)
    articulation_map: Optional[ArticulationMap] = None
    
    # Performance fingerprint (GAP 03)
    timing_dna: Dict[str, float] = field(default_factory=dict)
    velocity_dna: Dict[str, float] = field(default_factory=dict)
    groove_dna: Dict[str, float] = field(default_factory=dict)
    
    # Processing state
    processing_mode: ProcessingMode = ProcessingMode.PRESERVE
    frozen: bool = False  # Da li je track "frozen" (baked)
    
    # Reference na source
    source_file: Optional[str] = None
    hash_original: Optional[str] = None
    
    def get_absolute_tick_max(self) -> int:
        if not self.events:
            return 0
        return max(event.absolute_tick for event in self.events)

    def is_empty(self) -> bool:
        return not self.events

    def add_note(self, a=None, b=None, c=None, d=None, *, pitch=None, tick=None,
                 duration=None, velocity=None):
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

        on = MidiEvent(
            event_type=EventType.NOTE_ON,
            note=int(pitch),
            velocity=int(velocity),
            absolute_tick=int(tick),
            duration_ticks=int(duration),
            channel=self.channel,
            track_index=self.track_index,
        )
        self.add_event(on)
        off = MidiEvent(
            event_type=EventType.NOTE_OFF,
            note=int(pitch),
            velocity=0,
            absolute_tick=int(tick) + int(duration),
            channel=self.channel,
            track_index=self.track_index,
        )
        self.add_event(off)
        return on

    def add_event(self, event: MidiEvent):
        """Dodaje event i ažurira reference"""
        event.track_index = self.track_index
        self.events.append(event)
        self.total_events = len(self.events)
        
        # Ažuriraj note statistiku
        if event.event_type in [EventType.NOTE_ON, EventType.NOTE_OFF]:
            self.total_notes += 1
            if event.note is not None:
                if self.note_range_min == 0 or event.note < self.note_range_min:
                    self.note_range_min = event.note
                if event.note > self.note_range_max:
                    self.note_range_max = event.note
                if event.velocity > self.velocity_max:
                    self.velocity_max = event.velocity
                if event.velocity < self.velocity_min and event.velocity > 0:
                    self.velocity_min = event.velocity
    
    def get_events_by_type(self, event_type: EventType) -> List[MidiEvent]:
        """Filtrira evente po tipu"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_notes(self) -> List[MidiEvent]:
        """Vraća sve note events"""
        return self.get_events_by_type(EventType.NOTE_ON)
    
    def get_controllers(self, cc_number: int) -> List[MidiEvent]:
        """Vraća sve CC evente određenog broja"""
        return [e for e in self.events 
                if e.event_type == EventType.CONTROL_CHANGE and e.cc_number == cc_number]
    
    def clone(self) -> 'MidiTrack':
        """Kreira duboku kopiju tracka"""
        import copy
        return copy.deepcopy(self)
    
    def calculate_statistics(self):
        """Izračunava sve statistike tracka"""
        if not self.events:
            return
        
        notes = self.get_notes()
        if notes:
            self.total_notes = len(notes)
            note_values = [n.note for n in notes if n.note is not None]
            if note_values:
                self.note_range_min = min(note_values)
                self.note_range_max = max(note_values)
            
            velocities = [n.velocity for n in notes if n.velocity > 0]
            if velocities:
                self.velocity_min = min(velocities)
                self.velocity_max = max(velocities)
        
        self.total_events = len(self.events)
        if self.events:
            self.duration_ticks = max(e.absolute_tick for e in self.events)


@dataclass
class TempoMap:
    """Tempo mapa pjesme"""
    tempos: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {'absolute_tick': int, 'bpm': float}
    
    def add_tempo(self, absolute_tick: int, bpm: float):
        self.tempos.append({'absolute_tick': absolute_tick, 'bpm': bpm})
        self.tempos.sort(key=lambda x: x['absolute_tick'])
    
    def get_tempo_at_tick(self, absolute_tick: int) -> float:
        if not self.tempos:
            return 120.0  # Default
        
        for i in range(len(self.tempos) - 1, -1, -1):
            if self.tempos[i]['absolute_tick'] <= absolute_tick:
                return self.tempos[i]['bpm']
        
        return self.tempos[0]['bpm'] if self.tempos else 120.0
    
    def tick_to_ms(self, tick: int) -> float:
        """Konvertuje tickove u milisekunde"""
        if not self.tempos:
            return (tick / 480) * 500  # Default 120 BPM, 480 PPQN
        
        ms = 0.0
        prev_tick = 0
        
        for tempo_event in self.tempos:
            curr_tick = tempo_event['absolute_tick']
            if curr_tick > tick:
                break
            
            bpm = tempo_event['bpm']
            ticks_in_segment = curr_tick - prev_tick
            ms += (ticks_in_segment / 480) * (60000 / bpm)
            prev_tick = curr_tick
        
        # Preostali tickovi
        if prev_tick < tick:
            last_bpm = self.get_tempo_at_tick(tick)
            remaining_ticks = tick - prev_tick
            ms += (remaining_ticks / 480) * (60000 / last_bpm)
        
        return ms


@dataclass
class MeterMap:
    """Meter/Takt mapa pjesme"""
    meters: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {'absolute_tick': int, 'numerator': int, 'denominator': int}
    
    def add_meter(self, absolute_tick: int, numerator: int, denominator: int = 4):
        self.meters.append({
            'absolute_tick': absolute_tick,
            'numerator': numerator,
            'denominator': denominator
        })
        self.meters.sort(key=lambda x: x['absolute_tick'])
    
    def get_meter_at_tick(self, absolute_tick: int) -> Dict[str, int]:
        if not self.meters:
            return {'numerator': 4, 'denominator': 4}
        
        for i in range(len(self.meters) - 1, -1, -1):
            if self.meters[i]['absolute_tick'] <= absolute_tick:
                return {
                    'numerator': self.meters[i]['numerator'],
                    'denominator': self.meters[i]['denominator']
                }
        
        return {
            'numerator': self.meters[0]['numerator'],
            'denominator': self.meters[0]['denominator']
        }


@dataclass
class ChordEvent:
    """Chord Track event (Master Plan #10)"""
    absolute_tick: int = 0
    duration_ticks: int = 0
    root: int = 0  # MIDI note number
    quality: str = "major"  # major, minor, 7, maj7, m7, dim, aug, sus, etc.
    inversion: int = 0
    bass_note: Optional[int] = None
    confidence: float = 1.0
    source: str = "detected"  # detected, manual, generated


@dataclass
class Phrase:
    """Phrase objekat (Master Plan #14)"""
    phrase_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_tick: int = 0
    end_tick: int = 0
    role: str = "melody"  # melody, bass, rhythm, fill, transition
    motif: Optional[str] = None
    contour: str = "mixed"  # ascending, descending, mixed, static
    density: float = 0.0  # notes per beat
    velocity_arc: List[int] = field(default_factory=list)
    articulation_profile: Dict[str, float] = field(default_factory=dict)
    event_ids: List[str] = field(default_factory=list)


@dataclass
class MidiDocument:
    """
    Glavni dokument koji sadrži sve trackove i globalne podatke
    """
    filename: Optional[str] = None
    filepath: Optional[str] = None
    
    # MIDI Header informacije
    format_type: int = 1  # 0, 1, 2
    ppqn: int = 480  # Pulses Per Quarter Note
    num_tracks: int = 0
    
    # Sadržaj
    tracks: List[MidiTrack] = field(default_factory=list)
    
    # Globalne mape
    tempo_map: TempoMap = field(default_factory=TempoMap)
    meter_map: MeterMap = field(default_factory=MeterMap)
    key_signature: Optional[Dict[str, int]] = None
    
    # Chord Track (Master Plan #10)
    chord_track: List[ChordEvent] = field(default_factory=list)
    
    # Phrases (Master Plan #14)
    phrases: List[Phrase] = field(default_factory=list)
    
    # Metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    copyright: Optional[str] = None
    comments: Optional[str] = None
    
    # Analysis results
    detected_tempo: float = 0.0
    detected_key: Optional[str] = None
    detected_style: Optional[str] = None
    total_duration_ticks: int = 0
    total_duration_ms: float = 0.0
    total_measures: int = 0
    
    # Processing state
    processing_mode: ProcessingMode = ProcessingMode.PRESERVE
    hash_original: Optional[str] = None
    hash_current: Optional[str] = None
    
    # Versioning
    version: str = "1.0.0"
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    
    # Undo/Redo stack (Master Plan #111)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    redo_stack: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_track(self, track: MidiTrack):
        """Dodaje track u dokument"""
        track.track_index = len(self.tracks)
        self.tracks.append(track)
        self.num_tracks = len(self.tracks)
    
    def get_track_by_index(self, index: int) -> Optional[MidiTrack]:
        """Dohvaća track po indeksu"""
        if 0 <= index < len(self.tracks):
            return self.tracks[index]
        return None
    
    def get_track_by_name(self, name: str) -> Optional[MidiTrack]:
        """Dohvaća track po imenu"""
        for track in self.tracks:
            if track.name.lower() == name.lower():
                return track
        return None
    
    def get_all_events(self) -> List[MidiEvent]:
        """Vraća sve evente iz svih trackova"""
        all_events = []
        for track in self.tracks:
            all_events.extend(track.events)
        return sorted(all_events, key=lambda e: e.absolute_tick)
    
    def calculate_statistics(self):
        """Izračunava globalne statistike"""
        if not self.tracks:
            return
        
        self.total_duration_ticks = max(
            (track.duration_ticks for track in self.tracks),
            default=0
        )
        
        for track in self.tracks:
            track.calculate_statistics()
        
        # Konverzija u milisekunde
        self.total_duration_ms = self.tempo_map.tick_to_ms(self.total_duration_ticks)
        
        # Broj takta (aproksimacija)
        if self.meter_map.meters:
            meter = self.meter_map.get_meter_at_tick(0)
            ticks_per_measure = (480 * 4 * meter['numerator']) / meter['denominator']
            self.total_measures = int(self.total_duration_ticks / ticks_per_measure) + 1
    
    def update_hash(self):
        """Ažurira hash trenutnog stanja"""
        # Pojednostavljeni hash - u produkciji koristiti kompletnu serializaciju
        content = str([t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in self.tracks])
        self.hash_current = hashlib.sha256(content.encode()).hexdigest()
    
    def save_snapshot(self, description: str = ""):
        """Snima snapshot za undo (Master Plan #111)"""
        import copy
        snapshot = {
            'timestamp': datetime.now(),
            'description': description,
            'document_state': copy.deepcopy(self)
        }
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()  # Clear redo stack on new action
    
    def undo(self) -> bool:
        """Undo operacija"""
        if not self.undo_stack:
            return False
        
        # Snimi trenutno stanje u redo
        import copy
        redo_snapshot = {
            'timestamp': datetime.now(),
            'description': "Undo",
            'document_state': copy.deepcopy(self)
        }
        self.redo_stack.append(redo_snapshot)
        
        # Vrati iz undo stacka
        undo_snapshot = self.undo_stack.pop()
        # Restauriraj stanje (pojednostavljeno - treba duboko kopiranje)
        self.modified = datetime.now()
        return True
    
    def redo(self) -> bool:
        """Redo operacija"""
        if not self.redo_stack:
            return False
        
        redo_snapshot = self.redo_stack.pop()
        self.undo_stack.append(redo_snapshot)
        self.modified = datetime.now()
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializacija u dictionary"""
        return {
            'filename': self.filename,
            'format_type': self.format_type,
            'ppqn': self.ppqn,
            'num_tracks': self.num_tracks,
            'title': self.title,
            'detected_tempo': self.detected_tempo,
            'detected_key': self.detected_key,
            'total_duration_ms': self.total_duration_ms,
            'total_measures': self.total_measures,
            'processing_mode': self.processing_mode.value,
            'version': self.version
        }


@dataclass
class MidiProject:
    """
    Najviši nivo - projekat koji može sadržavati više dokumenata,
    reference na source fajlove, analize, i postavke.
    """
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Project"
    filepath: Optional[str] = None
    
    # Source dokument
    document: Optional[MidiDocument] = None
    
    # Reference na source fajlove
    source_files: List[Dict[str, str]] = field(default_factory=list)
    # Format: {'path': str, 'hash': str, 'role': str}
    
    # Factory/Gold reference (Master Plan #77-79)
    factory_references: List[str] = field(default_factory=list)
    gold_references: List[str] = field(default_factory=list)
    custom_references: List[str] = field(default_factory=list)
    
    # Analitički rezultati
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    
    # Processing plan (Brain Engine - Master Plan #121)
    processing_plan: Optional[Dict[str, Any]] = None
    
    # Postavke projekta
    settings: Dict[str, Any] = field(default_factory=dict)
    default_processing_mode: ProcessingMode = ProcessingMode.PRESERVE
    
    # Session podaci
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    last_saved: Optional[datetime] = None
    
    # Plugin stanje
    active_plugins: List[str] = field(default_factory=list)
    
    def set_document(self, document: MidiDocument):
        """Postavlja glavni dokument"""
        self.document = document
        self.modified = datetime.now()
    
    def add_source_file(self, path: str, role: str = "primary"):
        """Dodaje source fajl u projekat"""
        import hashlib
        
        try:
            with open(path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            file_hash = "unknown"
        
        self.source_files.append({
            'path': path,
            'hash': file_hash,
            'role': role
        })
        self.modified = datetime.now()
    
    def add_analysis_result(self, key: str, value: Any):
        """Dodaje rezultat analize"""
        self.analysis_results[key] = value
        self.modified = datetime.now()
    
    def set_processing_plan(self, plan: Dict[str, Any]):
        """Postavlja processing plan iz Brain Engine"""
        self.processing_plan = plan
        self.modified = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializacija u dictionary"""
        return {
            'project_id': self.project_id,
            'name': self.name,
            'filepath': self.filepath,
            'source_files': self.source_files,
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'processing_mode': self.default_processing_mode.value,
            'document_summary': self.document.to_dict() if self.document else None
        }


# Helper klase za buduće proširenja

@dataclass
class VoiceLeadingConstraint:
    """Voice leading pravila (GAP 02)"""
    allow_parallel_fifths: bool = False
    allow_parallel_octaves: bool = False
    max_voice_leap: int = 12  # semitones
    prefer_common_tones: bool = True
    smooth_voice_leading: bool = True


@dataclass
class GrooveTemplate:
    """Groove template (Master Plan #17)"""
    name: str = ""
    timing_offsets: Dict[int, int] = field(default_factory=dict)  # beat_position -> offset_ticks
    velocity_accents: Dict[int, int] = field(default_factory=dict)  # beat_position -> velocity_multiplier
    swing_amount: float = 0.0
    source: str = "extracted"  # extracted, factory, gold, custom


@dataclass
class NeuralModelConfig:
    """Konfiguracija za neuralne modele (CPU-only)"""
    model_type: str = "transformer"  # transformer, lstm, gru, cnn
    input_features: List[str] = field(default_factory=list)
    output_features: List[str] = field(default_factory=list)
    hidden_size: int = 256
    num_layers: int = 3
    dropout: float = 0.1
    use_cpu_only: bool = True  # Force CPU training/inference
    batch_size: int = 32
    learning_rate: float = 0.001
    max_epochs: int = 100
    checkpoint_path: Optional[str] = None
    
    def __post_init__(self):
        # Force CPU usage
        import os
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


# Parser emits MidiEvent; engines that import NoteEvent still type-check.
NoteEvent = MidiEvent
