"""
AUTONOMOUS MIDI REBUILDER - CORE REPRESENTATION LAYER

Ovaj modul definira DUAL REPRESENTATION sistem:
1. LosslessEventStream: Za savršen import/export (byte-perfect za nepromijenjene dijelove).
2. MusicalNoteGraph: Za AI razumijevanje (vrijeme, visina, uloga, akord, fraza, takat).

Također definira SONG SKELETON hijerarhiju:
Song -> Section -> Phrase -> Bar -> Beat -> Note
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import hashlib

# --- ENUMS ---

class SectionType(Enum):
    INTRO = "intro"
    VERSE = "verse"
    PRE_CHORUS = "pre_chorus"
    CHORUS = "chorus"
    BRIDGE = "bridge"
    SOLO = "solo"
    INTERLUDE = "interlude"
    BREAKDOWN = "breakdown"
    OUTRO = "outro"
    UNKNOWN = "unknown"

class InstrumentRole(Enum):
    DRUMS = "drums"
    BASS = "bass"
    RHYTHM_GUITAR = "rhythm_guitar"
    POWERCHORD = "powerchord"
    PIANO = "piano"
    ACCORDION = "accordion"
    STRINGS = "strings"
    PAD = "pad"
    BRASS = "brass"
    SOLO_LEAD = "solo_lead"
    HARMONY_VOICE = "harmony_voice"
    COUNTER_MELODY = "counter_melody"
    PERCUSSION = "percussion"
    ARPEGGIO = "arpeggio"
    UNKNOWN = "unknown"

class RebuildDecision(Enum):
    KEEP = "keep"              # Savršeno ili dovoljno dobro
    POLISH = "polish"          # Samo velocity/timing/articulation
    REPAIR = "repair"          # Popravi note unutar tracka
    HEAVY_REPAIR = "heavy_repair" # Zamjeni 50%+ nota
    REBUILD = "rebuild"        # Generiši novi track zadržavajući ulogu
    GENERATE = "generate"      # Track ne postoji, kreiraj ga
    REMOVE = "remove"          # Track smeta aranžmanu
    SKELETON_ONLY = "skeleton_only" # Sačuvaj samo konturu za L5 rekonstrukciju

class ConfidenceLevel(Enum):
    VERY_LOW = 0.2
    LOW = 0.4
    MEDIUM = 0.6
    HIGH = 0.8
    VERY_HIGH = 0.95

# --- DATA MODELS: MUSICAL REPRESENTATION ---

@dataclass
class ChordSymbol:
    root: str  # npr. "C", "G", "F#"
    quality: str  # npr. "maj", "min", "7", "m7", "sus4", "dim"
    bass_note: Optional[str] = None  # Za slash chordove npr. "C/E"
    confidence: float = 0.0
    function: Optional[str] = None  # "Tonic", "Subdominant", "Dominant"

@dataclass
class MotifDNA:
    """
    Izvlači 1-2 taktne motive za prepoznavanje i varijaciju.
    """
    id: str
    length_ticks: int
    pitch_contour: List[int]  # Relativni intervali
    rhythm_pattern: List[int]  # Relativni onseti u tickovima
    harmony_context: Optional[ChordSymbol] = None
    occurrences: int = 1
    transformations: List[str] = field(default_factory=list)  # "transpose_up", "rhythmic_var"

@dataclass
class MusicalNote:
    """
    Visokonivolska reprezentacija note za AI engine.
    Ne sadrži raw MIDI bajtove, već muzičko značenje.
    """
    id: str
    pitch: int
    start_tick: int
    duration_ticks: int
    velocity: int
    channel: int
    track_index: int
    
    # Kontekstualni podaci (popunjava Skeleton Engine)
    bar_index: int = 0
    beat_index: float = 0.0
    position_in_bar: float = 0.0  # 0.0 do 4.0 (za 4/4)
    
    # Uloge i funkcije
    role: InstrumentRole = InstrumentRole.UNKNOWN
    is_accent: bool = False
    is_ghost: bool = False
    articulation: Optional[str] = None  # "slide", "mute", "staccato", "legato"
    
    # Harmonijski kontekst
    current_chord: Optional[ChordSymbol] = None
    chord_tone_type: Optional[str] = None  # "root", "third", "fifth", "passing"
    
    # Poveznice
    motif_id: Optional[str] = None
    phrase_id: Optional[str] = None
    section_id: str = ""
    
    # Provenance
    source_event_ids: List[int] = field(default_factory=list)  # Link na originalne evente
    is_generated: bool = False
    generation_confidence: float = 0.0

@dataclass
class Phrase:
    id: str
    start_tick: int
    end_tick: int
    section_id: str
    motif_ids: List[str] = field(default_factory=list)
    energy_level: float = 0.5  # 0.0 - 1.0
    cadence_type: Optional[str] = None  # "perfect", "plagal", "half", "none"
    notes: List[MusicalNote] = field(default_factory=list)

@dataclass
class Section:
    id: str = ""
    type: SectionType = SectionType.UNKNOWN
    start_tick: int = 0
    end_tick: int = 0
    bar_count: int = 0
    name: str = ""
    start_bar: int = 0
    length: int = 0
    energy: float = 0.5
    key_signature: Optional[str] = None
    tempo_bpm: float = 120.0
    energy_curve: List[float] = field(default_factory=list)  # Energy po taktu
    phrases: List[Phrase] = field(default_factory=list)
    dominant_chords: List[ChordSymbol] = field(default_factory=list)
    
    # Planirani instrumenti za ovu sekciju
    active_roles: List[InstrumentRole] = field(default_factory=list)
    density_target: float = 0.5  # 0.0 - 1.0

    def __post_init__(self):
        if self.name and not self.id:
            self.id = self.name
        if self.length and not self.bar_count:
            self.bar_count = self.length
        if self.start_bar and not self.start_tick:
            self.start_tick = max(0, self.start_bar - 1) * 1920
        if self.length and not self.end_tick:
            self.end_tick = self.start_tick + self.length * 1920

@dataclass
class SongSkeleton:
    """
    Glavna struktura koju Song Skeleton Engine gradi prije bilo kakve generacije.
    Ovo je "mapa" pjesme koju svi generatori koriste.
    """
    title: str = "Untitled"
    total_ticks: int = 0
    ppqn: int = 480
    bpm: float = 120.0
    key: Optional[str] = None
    style: str = ""
    time_signatures: List[Tuple[int, int, int]] = field(default_factory=list)  # (tick, numerator, denominator)
    tempo_map: List[Tuple[int, float]] = field(default_factory=list)  # (tick, bpm)
    
    sections: List[Section] = field(default_factory=list)
    global_key: Optional[str] = None
    global_tempo: float = 120.0
    
    # Factory/Gold Retrieval Cache
    retrieved_fingerprints: Dict[str, Any] = field(default_factory=dict)
    
    # Arrangement Plan (popunjava ArrangementPlanner)
    arrangement_plan: Dict[str, RebuildDecision] = field(default_factory=dict)  # track_name -> decision
    
    def get_section_at(self, tick: int) -> Optional[Section]:
        for sec in self.sections:
            if sec.start_tick <= tick < sec.end_tick:
                return sec
        return None

    def get_chord_at(self, tick: int) -> Optional[ChordSymbol]:
        # Implementacija će tražiti kroz sekcije i fraze
        # Ovo je placeholder za logiku
        return None

# --- DATA MODELS: LOSSLESS STREAM ---

@dataclass
class LosslessEvent:
    """
    Omotnica za originalni MIDI event koja čuva sve byte informacije.
    Koristi se za export nepromijenjenih dijelova.
    """
    event_id: int
    track_index: int
    absolute_tick: int
    delta_tick: int
    status_byte: int
    data_bytes: bytes
    is_modified: bool = False
    modified_event: Optional[Any] = None  # Ako je izmijenjen, ovdje je novi event
    original_hash: str = ""
    
    def __post_init__(self):
        if not self.original_hash:
            self.original_hash = hashlib.sha256(
                f"{self.status_byte}{self.data_bytes}".encode()
            ).hexdigest()[:16]

@dataclass
class MidiDocumentDual:
    """
    Glavni dokument koji drži OBA prikaza sinhronizovana.
    """
    filename: str
    source_hash: str
    
    # 1. Lossless Stream (za export)
    events: List[LosslessEvent] = field(default_factory=list)
    track_names: Dict[int, str] = field(default_factory=dict)
    
    # 2. Musical Graph (za AI)
    skeleton: Optional[SongSkeleton] = None
    notes: List[MusicalNote] = field(default_factory=list)
    
    # Mapiranje između dva svijeta
    event_to_note_map: Dict[int, str] = field(default_factory=dict)  # event_id -> note_id
    note_to_events_map: Dict[str, List[int]] = field(default_factory=dict)  # note_id -> [event_ids]
    
    # Metadata
    ppqn: int = 480
    smf_type: int = 1
    
    def link_event_to_note(self, event_id: int, note_id: str):
        self.event_to_note_map[event_id] = note_id
        if note_id not in self.note_to_events_map:
            self.note_to_events_map[note_id] = []
        self.note_to_events_map[note_id].append(event_id)
