"""
CORE INSTRUMENT PROFILES & KNOWLEDGE BASE
-----------------------------------------
Definicija fizičkih i muzičkih ograničenja, tehnika i raspona za svaki instrument.
Ovo je "Bible" koju engine-i koriste za validaciju i generisanje.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from enum import Enum, auto


class InstrumentFamily(Enum):
    STRING = auto()
    WIND = auto()
    BRASS = auto()
    PERCUSSION = auto()
    KEYBOARD = auto()
    SYNTH = auto()


class PlayingTechnique(Enum):
    # Opšte
    LEGATO = auto()
    STACCATO = auto()
    ACCENT = auto()
    GHOST = auto()
    
    # Žice (Guitar/Bass/Strings)
    HAMMER_ON = auto()
    PULL_OFF = auto()
    SLIDE_UP = auto()
    SLIDE_DOWN = auto()
    BEND = auto()
    VIBRATO = auto()
    PALM_MUTE = auto()
    HARMONIC_NATURAL = auto()
    HARMONIC_ARTIFICIAL = auto()
    STRUM_DOWN = auto()
    STRUM_UP = auto()
    CHORD_ARPEGGIO = auto()
    PIZZICATO = auto()  # Dodano za violine/gudala
    POWER_CHORD = auto() # Dodano za gitaru
    SLAP = auto()        # Dodano za bas
    POP = auto()         # Dodano za bas
    
    # Klavir
    PEDAL_SUSTAIN = auto()
    PEDAL_SOSTENUTO = auto()
    BROKEN_CHORD = auto()
    
    # Bubnjevi
    FLAM = auto()
    DRAG_RUFF = auto()
    ROLL = auto()
    HIHAT_OPEN = auto()
    HIHAT_HALF_OPEN = auto()
    RIMSHOT = auto()
    CROSS_STICK = auto()
    
    # Duvači
    BREATH_NOISE = auto()
    FALL_OFF = auto()
    DOIT = auto()
    TRILL = auto()
    DOUBLE_TONGUE = auto()


@dataclass
class TechniqueConstraint:
    """Fizička ograničenja za tehniku"""
    min_velocity: int = 0
    max_velocity: int = 127
    min_duration_ticks: int = 0
    max_duration_ticks: int = 10000
    required_cc: Optional[Dict[int, int]] = None  # {cc_number: value}
    forbidden_cc: Optional[List[int]] = None
    max_polyphony: int = 1  # Za monofone instrumente
    transition_time_ticks: int = 50  # Vrijeme potrebno za prelazak između nota


@dataclass
class InstrumentProfile:
    name: str
    family: InstrumentFamily
    midi_program: int
    is_monophonic: bool
    pitch_range: Tuple[int, int]  # (min_note, max_note)
    default_velocity_range: Tuple[int, int]
    
    # Mapiranje tehnika na MIDI signale
    techniques: Dict[PlayingTechnique, TechniqueConstraint] = field(default_factory=dict)
    
    # Specifična pravila
    allowed_intervals: List[int] = field(default_factory=list)  # U polustepenima
    preferred_scales: List[str] = field(default_factory=list)
    
    # Korg RX/DNC specifičnosti
    rx_zones: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # {"normal": (0, 60), "accent": (61, 100)}
    dnc_triggers: Dict[PlayingTechnique, int] = field(default_factory=dict)  # Tehnika -> CC value


class InstrumentDatabase:
    """Centralna baza profila"""
    
    def __init__(self):
        self.profiles: Dict[str, InstrumentProfile] = {}
        self._load_builtin_profiles()
    
    def get_profile(self, instrument_name: str) -> Optional[InstrumentProfile]:
        return self.profiles.get(instrument_name)
    
    def get_profile_by_program(self, program: int, bank: int = 0) -> Optional[InstrumentProfile]:
        for profile in self.profiles.values():
            if profile.midi_program == program:
                return profile
        return None
    
    def _load_builtin_profiles(self):
        # --- SOLO INSTRUMENTS (Wind/Brass/Strings) ---
        sax_alto = InstrumentProfile(
            name="Alto Sax",
            family=InstrumentFamily.WIND,
            midi_program=65,
            is_monophonic=True,
            pitch_range=(58, 93),  # Eb3 do C#7
            default_velocity_range=(40, 110),
            techniques={
                PlayingTechnique.VIBRATO: TechniqueConstraint(min_velocity=70, required_cc={1: 64}),
                PlayingTechnique.BEND: TechniqueConstraint(required_cc={1: 64}), # Pitch bend
                PlayingTechnique.FALL_OFF: TechniqueConstraint(max_duration_ticks=200),
                PlayingTechnique.DOIT: TechniqueConstraint(min_velocity=90),
                PlayingTechnique.TRILL: TechniqueConstraint(max_duration_ticks=400),
                PlayingTechnique.BREATH_NOISE: TechniqueConstraint(max_velocity=40),
            },
            rx_zones={"normal": (0, 60), "accent": (61, 95), "breath": (0, 30)},
            dnc_triggers={PlayingTechnique.VIBRATO: 1, PlayingTechnique.BEND: 2}
        )
        self.profiles["Alto Sax"] = sax_alto
        
        trumpet = InstrumentProfile(
            name="Trumpet",
            family=InstrumentFamily.BRASS,
            midi_program=56,
            is_monophonic=True,
            pitch_range=(60, 96),
            default_velocity_range=(50, 120),
            techniques={
                PlayingTechnique.STACCATO: TechniqueConstraint(max_duration_ticks=150),
                PlayingTechnique.ACCENT: TechniqueConstraint(min_velocity=100),
                PlayingTechnique.FALL_OFF: TechniqueConstraint(),
                PlayingTechnique.DOIT: TechniqueConstraint(),
            },
            rx_zones={"normal": (0, 70), "accent": (71, 120)}
        )
        self.profiles["Trumpet"] = trumpet
        
        violin = InstrumentProfile(
            name="Violin",
            family=InstrumentFamily.STRING,
            midi_program=40,
            is_monophonic=True,
            pitch_range=(67, 108),
            default_velocity_range=(30, 110),
            techniques={
                PlayingTechnique.LEGATO: TechniqueConstraint(transition_time_ticks=20),
                PlayingTechnique.VIBRATO: TechniqueConstraint(min_velocity=60),
                PlayingTechnique.PIZZICATO: TechniqueConstraint(max_duration_ticks=300, min_velocity=80),
                PlayingTechnique.TRILL: TechniqueConstraint(),
            },
            rx_zones={"arco": (0, 80), "pizz": (81, 120)}
        )
        self.profiles["Violin"] = violin

        # --- GUITAR ---
        clean_guitar = InstrumentProfile(
            name="Clean Guitar",
            family=InstrumentFamily.STRING,
            midi_program=25,
            is_monophonic=False,
            pitch_range=(40, 84),
            default_velocity_range=(40, 100),
            techniques={
                PlayingTechnique.HAMMER_ON: TechniqueConstraint(min_velocity=70),
                PlayingTechnique.PULL_OFF: TechniqueConstraint(max_velocity=90),
                PlayingTechnique.SLIDE_UP: TechniqueConstraint(),
                PlayingTechnique.SLIDE_DOWN: TechniqueConstraint(),
                PlayingTechnique.BEND: TechniqueConstraint(required_cc={1: 64}),
                PlayingTechnique.PALM_MUTE: TechniqueConstraint(max_velocity=60, max_duration_ticks=400),
                PlayingTechnique.STRUM_DOWN: TechniqueConstraint(),
                PlayingTechnique.STRUM_UP: TechniqueConstraint(),
                PlayingTechnique.HARMONIC_NATURAL: TechniqueConstraint(min_velocity=50, max_velocity=80),
            },
            rx_zones={"normal": (0, 60), "accent": (61, 90), "mute": (0, 50), "slide": (91, 120)},
            dnc_triggers={
                PlayingTechnique.HAMMER_ON: 10, 
                PlayingTechnique.SLIDE_UP: 20, 
                PlayingTechnique.PALM_MUTE: 30
            }
        )
        self.profiles["Clean Guitar"] = clean_guitar
        
        distortion_guitar = InstrumentProfile(
            name="Distortion Guitar",
            family=InstrumentFamily.STRING,
            midi_program=29,
            is_monophonic=False,
            pitch_range=(40, 84),
            default_velocity_range=(60, 120),
            techniques={
                PlayingTechnique.PALM_MUTE: TechniqueConstraint(max_velocity=80),
                PlayingTechnique.BEND: TechniqueConstraint(),
                PlayingTechnique.HARMONIC_ARTIFICIAL: TechniqueConstraint(min_velocity=100),
                PlayingTechnique.POWER_CHORD: TechniqueConstraint(max_polyphony=3),
            },
            rx_zones={"normal": (0, 70), "mute": (0, 60), "accent": (71, 120)}
        )
        self.profiles["Distortion Guitar"] = distortion_guitar

        # --- BASS ---
        finger_bass = InstrumentProfile(
            name="Finger Bass",
            family=InstrumentFamily.STRING,
            midi_program=32,
            is_monophonic=True,
            pitch_range=(28, 58),
            default_velocity_range=(50, 110),
            techniques={
                PlayingTechnique.GHOST: TechniqueConstraint(max_velocity=50),
                PlayingTechnique.ACCENT: TechniqueConstraint(min_velocity=90),
                PlayingTechnique.SLIDE_UP: TechniqueConstraint(),
                PlayingTechnique.SLAP: TechniqueConstraint(min_velocity=100), # Custom technique
                PlayingTechnique.POP: TechniqueConstraint(min_velocity=90),
            },
            rx_zones={"normal": (0, 70), "ghost": (0, 50), "accent": (71, 110), "slide": (80, 120)}
        )
        self.profiles["Finger Bass"] = finger_bass
        
        slap_bass = InstrumentProfile(
            name="Slap Bass",
            family=InstrumentFamily.STRING,
            midi_program=36,
            is_monophonic=True,
            pitch_range=(28, 58),
            default_velocity_range=(70, 120),
            techniques={
                PlayingTechnique.SLAP: TechniqueConstraint(min_velocity=90),
                PlayingTechnique.POP: TechniqueConstraint(min_velocity=80),
                PlayingTechnique.GHOST: TechniqueConstraint(max_velocity=60),
            },
            rx_zones={"slap": (90, 120), "pop": (80, 110), "ghost": (0, 60)}
        )
        self.profiles["Slap Bass"] = slap_bass

        # --- DRUMS ---
        drum_kit = InstrumentProfile(
            name="Standard Drum Kit",
            family=InstrumentFamily.PERCUSSION,
            midi_program=0, # Channel 10 usually
            is_monophonic=False,
            pitch_range=(35, 81),
            default_velocity_range=(40, 127),
            techniques={
                PlayingTechnique.FLAM: TechniqueConstraint(max_duration_ticks=50), # Very short delta
                PlayingTechnique.DRAG_RUFF: TechniqueConstraint(),
                PlayingTechnique.ROLL: TechniqueConstraint(),
                PlayingTechnique.HIHAT_OPEN: TechniqueConstraint(min_velocity=90),
                PlayingTechnique.HIHAT_HALF_OPEN: TechniqueConstraint(min_velocity=70, max_velocity=90),
                PlayingTechnique.RIMSHOT: TechniqueConstraint(min_velocity=100),
                PlayingTechnique.CROSS_STICK: TechniqueConstraint(max_velocity=80),
            },
            rx_zones={
                "kick_normal": (0, 100), "kick_accent": (101, 127),
                "snare_ghost": (0, 50), "snare_normal": (51, 90), "snare_accent": (91, 127),
                "hihat_closed": (0, 80), "hihat_open": (81, 127)
            }
        )
        self.profiles["Standard Drum Kit"] = drum_kit

        # --- PIANO ---
        grand_piano = InstrumentProfile(
            name="Grand Piano",
            family=InstrumentFamily.KEYBOARD,
            midi_program=0,
            is_monophonic=False,
            pitch_range=(21, 108),
            default_velocity_range=(10, 127),
            techniques={
                PlayingTechnique.LEGATO: TechniqueConstraint(transition_time_ticks=10),
                PlayingTechnique.STACCATO: TechniqueConstraint(max_duration_ticks=200),
                PlayingTechnique.PEDAL_SUSTAIN: TechniqueConstraint(required_cc={64: 127}),
                PlayingTechnique.BROKEN_CHORD: TechniqueConstraint(),
                PlayingTechnique.ACCENT: TechniqueConstraint(min_velocity=100),
            },
            rx_zones={"soft": (0, 40), "normal": (41, 90), "forte": (91, 127)}
        )
        self.profiles["Grand Piano"] = grand_piano

# Global instance
INSTRUMENT_DB = InstrumentDatabase()
