"""
ADVANCED VELOCITY & ARTICULATION MODELS
=======================================
Ovaj modul definiše napredne strukture podataka za obradu velocity-a.
Umjesto običnog integera (0-127), svaka nota sada ima bogat metadata kontekst.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import numpy as np

class ArticulationType(Enum):
    """Definicija svih mogućih artikulacija"""
    NORMAL = "normal"
    GHOST = "ghost"          # Tiha nota, ritmički filler
    ACCENT = "accent"        # Naglašena nota
    STACCATO = "staccato"    # Kratka nota
    LEGATO = "legato"        # Povezana nota
    TENUTO = "tenuto"        # Zadržana nota
    MARCATO = "marcato"      # Jako naglašena
    MUTE = "mute"            # Prigušena (gitara/bubanj)
    SLIDE = "slide"          # Slide trigger (gitara)
    NOISE = "noise"          # Noise/Slide trigger (Korg RX)
    FLAM = "flam"            # Bubanj flam
    ROLL = "roll"            # Bubanj roll
    
@dataclass
class VelocityContext:
    """
    Kontekstualni podaci za svaku notu.
    Ne gleda velocity izolovano, već u odnosu na okolinu.
    """
    position_in_phrase: float  # 0.0 (početak) do 1.0 (kraj)
    position_in_measure: float # Pozicija u taktu (0.0 - 4.0)
    beat_strength: float       # Jačina bita (1.0 = downbeat, 0.2 = off-beat)
    is_chord_tone: bool        # Da li je nota ton akorda
    is_passing_tone: bool      # Da li je prolazna nota
    surrounding_density: int   # Broj nota u +/- 500ms prozoru
    previous_velocity: int     # Velocity prethodne note (isti instrument)
    next_velocity: int         # Velocity sljedeće note
    
@dataclass
class ArticulationMap:
    """
    Mapa koja prevodi velocity range u artikulaciju.
    Specifično za svaki instrument/program.
    """
    instrument_id: str
    program_number: int
    
    # Definicija zona: (min_vel, max_vel) -> ArticulationType
    zones: List[Tuple[int, int, ArticulationType]] = field(default_factory=list)
    
    # DNC/RX specifični triggeri (Korg/Roland)
    rx_noise_threshold: int = 100  # Velocity iznad ovoga triggera noise/scratch
    legato_window_ms: int = 50     # Vremenski prozor za legato detekciju
    
    def get_articulation(self, velocity: int) -> ArticulationType:
        """Odredi artikulaciju na osnovu velocity-a"""
        for min_v, max_v, art_type in self.zones:
            if min_v <= velocity <= max_v:
                return art_type
        return ArticulationType.NORMAL
        
    def add_zone(self, min_v: int, max_v: int, art_type: ArticulationType):
        self.zones.append((min_v, max_v, art_type))
        self.zones.sort(key=lambda x: x[0])

@dataclass
class VelocityProfile:
    """
    Statistički profil velocity-a za track ili frazu.
    Koristi se za analizu i transfer stila.
    """
    mean_velocity: float
    std_deviation: float
    min_velocity: int
    max_velocity: int
    dynamic_range: int  # max - min
    
    # Distribucija po artikulacijama
    ghost_ratio: float      # % ghost nota
    accent_ratio: float     # % accent nota
    normal_ratio: float     # % normal nota
    
    # Phrase contour (prosječni velocity po dijelovima fraze)
    phrase_arc: List[float] = field(default_factory=list) # [start, mid, end] avg velocities
    
    # Timing-Velocity korelacija (da li kasnije note imaju manji velocity?)
    timing_velocity_corr: float = 0.0 

@dataclass
class ProcessedNoteData:
    """
    Obogaćeni podaci za jednu notu nakon analize.
    Ovo se čuva uz MidiEvent za brzi pristup.
    """
    original_velocity: int
    processed_velocity: int
    release_velocity: int   # Note-off velocity (često ignorisan, ali bitan za RX)
    
    articulation: ArticulationType
    confidence: float       # Koliko smo sigurni u detekciju artikulacije (0.0-1.0)
    
    context: VelocityContext
    is_modified: bool = False
    modification_reason: str = ""  # Zašto je velocity promijenjen? (npr. "Ghost detection", "Accent fix")

class VelocityCurve:
    """
    Klasa za manipulaciju velocity krivuljama.
    Podržava linearne, eksponencijalne, S-krive i custom mape.
    """
    
    @staticmethod
    def linear(v: int) -> int:
        return v
        
    @staticmethod
    def exponential(v: int, factor: float = 1.5) -> int:
        """Jači velocity-i postaju još jači (kompresija dinamike)"""
        normalized = v / 127.0
        scaled = np.power(normalized, factor)
        return int(min(127, scaled * 127))
        
    @staticmethod
    def logarithmic(v: int, factor: float = 0.7) -> int:
        """Slabiji velocity-i postaju jači (ekspanzija tihih detalja)"""
        normalized = v / 127.0
        # Izbjegavanje log(0)
        safe_norm = max(0.001, normalized)
        scaled = np.log(safe_norm * factor + 1) / np.log(factor + 1)
        return int(min(127, scaled * 127))
        
    @staticmethod
    def s_curve(v: int, threshold: int = 64, steepness: float = 2.0) -> int:
        """S-kriva za balansiranje ekstremnih vrijednosti"""
        normalized = v / 127.0
        # Sigmoid funkcija
        scaled = 1 / (1 + np.exp(-steepness * (normalized - (threshold/127.0))))
        return int(min(127, scaled * 127))
        
    @staticmethod
    def custom_map(v: int, mapping_table: Dict[int, int]) -> int:
        """Custom mapa (npr. iz Factory profila)"""
        # Interpolacija ako tačna vrijednost ne postoji
        if v in mapping_table:
            return mapping_table[v]
        
        keys = sorted(mapping_table.keys())
        if v < keys[0]: return mapping_table[keys[0]]
        if v > keys[-1]: return mapping_table[keys[-1]]
        
        # Linearna interpolacija između susjednih tačaka
        for i in range(len(keys) - 1):
            if keys[i] <= v <= keys[i+1]:
                k1, k2 = keys[i], keys[i+1]
                v1, v2 = mapping_table[k1], mapping_table[k2]
                ratio = (v - k1) / (k2 - k1)
                return int(v1 + ratio * (v2 - v1))
        
        return v
