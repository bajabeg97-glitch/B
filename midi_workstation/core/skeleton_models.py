"""
DUAL REPRESENTATION CORE & SONG SKELETON ENGINE
------------------------------------------------
Ovaj modul prevodi 'glupe' MIDI evente u muzički smislene objekte.
Omogućava AI-u da razumije: Pjesma -> Sekcija -> Fraza -> Motiv -> Nota.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import numpy as np

# --- ENUMS ---

class SectionType(Enum):
    UNKNOWN = "Unknown"
    INTRO = "Intro"
    VERSE = "Verse"
    PRE_CHORUS = "Pre-Chorus"
    CHORUS = "Chorus"
    BRIDGE = "Bridge"
    SOLO = "Solo"
    OUTRO = "Outro"
    FILL = "Fill"
    BREAK = "Break"

class DecisionType(Enum):
    KEEP = "KEEP"           # Savršen ili vrlo dobar
    OPTIMIZE = "OPTIMIZE"   # Sitne popravke (velocity, timing)
    REPAIR = "REPAIR"       # Djelimična rekonstrukcija slabih dijelova
    REBUILD = "REBUILD"     # Potpuna zamjena tracka
    GENERATE = "GENERATE"   # Track ne postoji, treba ga napraviti
    REMOVE = "REMOVE"       # Track smeta aranžmanu

class InstrumentRole(Enum):
    DRUMS = "Drums"
    BASS = "Bass"
    RHYTHM_GUITAR = "Rhythm Guitar"
    POWERCHORD = "PowerChord"
    PIANO = "Piano"
    ACCORDION = "Accordion"
    STRINGS = "Strings"
    PAD = "Pad"
    SOLO = "Solo"
    TERCA = "Terca/Harmony"
    PERCUSSION = "Percussion"
    UNKNOWN = "Unknown"

# --- DATA MODELS ---

@dataclass
class MusicalNote:
    """Visokonivelska reprezentacija note, nezavisna od MIDI eventa."""
    pitch: int
    velocity: int
    start_tick: int
    duration_ticks: int
    channel: int
    track_index: int
    
    # Izvedene vrijednosti (popunjava analyzer)
    beat_position: float = 0.0
    measure_index: int = 0
    is_accent: bool = False
    articulation: str = "normal"  # normal, ghost, slide, mute
    role: Optional[str] = None    # root, third, fifth, passing, etc.

@dataclass
class Motif:
    """Najmanja muzička jedinica (1-2 takta)."""
    notes: List[MusicalNote]
    start_tick: int
    end_tick: int
    fingerprint: str = ""  # Hash za prepoznavanje ponavljanja

@dataclass
class Phrase:
    """Muzička rečenica (obično 4 ili 8 taktova)."""
    motifs: List[Motif]
    start_tick: int
    end_tick: int
    energy: float = 0.0  # 0.0 - 1.0
    density: float = 0.0 # Note po beatu
    tension: float = 0.0

@dataclass
class Section:
    """Dio pjesme (Verse, Chorus, itd.)."""
    type: SectionType
    phrases: List[Phrase]
    start_tick: int
    end_tick: int
    avg_energy: float = 0.0
    chord_progression: List[str] = field(default_factory=list)
    key_signature: Optional[str] = None

@dataclass
class TrackAnalysis:
    """Rezultat analize jednog tracka."""
    track_index: int
    instrument_role: InstrumentRole
    program_change: int
    total_notes: int
    quality_score: float = 0.0  # 0.0 - 1.0
    
    # Detaljni skorovi
    timing_score: float = 0.0
    velocity_score: float = 0.0
    harmony_score: float = 0.0
    groove_score: float = 0.0
    authenticity_score: float = 0.0
    
    # Detektovani problemi
    issues: List[str] = field(default_factory=list)

@dataclass
class TrackDecision:
    """Odluka šta uraditi sa trackom."""
    track_index: int
    decision: DecisionType
    confidence: float
    reason: str
    target_quality: float = 0.0
    parameters: Dict = field(default_factory=dict)

@dataclass
class SongSkeleton:
    """Kompletna struktura pjesme."""
    sections: List[Section]
    tempo_map: Dict[int, float]  # tick -> bpm
    time_sig_map: Dict[int, Tuple[int, int]]  # tick -> (numerator, denominator)
    global_key: Optional[str] = None
    total_ticks: int = 0
    duration_seconds: float = 0.0
