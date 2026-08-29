"""
INSTRUMENT-AWARE VALIDATOR & REPAIR ENGINE
------------------------------------------
Koristi InstrumentProfile bazu za detekciju nemogućih fraza, 
pogrešnih tehnika i automatsku popravku.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from core.models import MidiDocument, MidiTrack, NoteEvent, ControllerEvent, ProgramEvent
from core.instrument_profiles import (
    INSTRUMENT_DB, InstrumentProfile, PlayingTechnique, TechniqueConstraint, InstrumentFamily
)


class ViolationSeverity(Enum):
    WARNING = 1       # Moguće izvodljivo ali neobično
    ERROR = 2         # Fizički nemoguće
    CRITICAL = 3      # Potpuno van dometa instrumenta


@dataclass
class PerformanceViolation:
    note_event: NoteEvent
    violation_type: str
    severity: ViolationSeverity
    description: str
    suggested_fix: Optional[Dict] = None


class InstrumentValidator:
    """Validira MIDI performance protiv fizičkih ograničenja instrumenta"""
    
    def __init__(self, document: MidiDocument):
        self.document = document
        self.violations: List[PerformanceViolation] = []
    
    def validate_track(self, track: MidiTrack) -> List[PerformanceViolation]:
        """Validira cijeli track"""
        self.violations = []
        
        # Detektuj instrument
        profile = self._detect_instrument_profile(track)
        if not profile:
            return []  # Nepoznat instrument, preskoči
        
        # Analiziraj note sekvencijalno
        notes = [e for e in track.events if isinstance(e, NoteEvent)]
        if not notes:
            return []
        
        # Sortiraj po vremenu
        notes.sort(key=lambda x: x.absolute_tick)
        
        for i, note in enumerate(notes):
            self._validate_single_note(note, profile)
            
            if i > 0:
                prev_note = notes[i-1]
                self._validate_transition(prev_note, note, profile)
        
        return self.violations
    
    def _detect_instrument_profile(self, track: MidiTrack) -> Optional[InstrumentProfile]:
        """Detektuje profil na osnovu Program Change ili imena"""
        # Pokušaj preko Program Change eventa
        program_events = [e for e in track.events if isinstance(e, ProgramEvent)]
        if program_events:
            prog_num = program_events[0].program
            profile = INSTRUMENT_DB.get_profile_by_program(prog_num)
            if profile:
                return profile
        
        # Pokušaj preko imena tracka
        if track.name:
            for name, profile in INSTRUMENT_DB.profiles.items():
                if name.lower() in track.name.lower():
                    return profile
        
        # Default: Grand Piano ako je channel != 10
        if track.channel != 9:  # Channel 10 (index 9) su bubnjevi
            return INSTRUMENT_DB.get_profile("Grand Piano")
        else:
            return INSTRUMENT_DB.get_profile("Standard Drum Kit")
    
    def _validate_single_note(self, note: NoteEvent, profile: InstrumentProfile):
        """Validira pojedinačnu notu"""
        pitch = note.pitch  # Koristi 'pitch' umjesto 'note'
        velocity = note.velocity
        duration = note.duration_ticks
        
        # 1. Pitch Range check
        min_pitch, max_pitch = profile.pitch_range
        if pitch < min_pitch or pitch > max_pitch:
            self.violations.append(PerformanceViolation(
                note_event=note,
                violation_type="OUT_OF_RANGE",
                severity=ViolationSeverity.CRITICAL,
                description=f"Nota {pitch} je van dometa {profile.name} ({min_pitch}-{max_pitch})",
                suggested_fix={"pitch": max(min_pitch, min(pitch, max_pitch))}
            ))
        
        # 2. Velocity Range check
        min_vel, max_vel = profile.default_velocity_range
        if velocity < min_vel or velocity > max_vel:
            self.violations.append(PerformanceViolation(
                note_event=note,
                violation_type="VELOCITY_OUT_OF_DEFAULT",
                severity=ViolationSeverity.WARNING,
                description=f"Velocity {velocity} je izvan tipičnog dometa ({min_vel}-{max_vel})",
                suggested_fix={"velocity": max(min_vel, min(velocity, max_vel))}
            ))
        
        # 3. Duration check za specifične tehnike
        # (Ovdje bi išla detekcija da li je nota prekratka za staccato ili predugačka za bend)
    
    def _validate_transition(self, note1: NoteEvent, note2: NoteEvent, profile: InstrumentProfile):
        """Validira prelaz između dvije note"""
        if profile.is_monophonic:
            # Provjera preklapanja za monofone instrumente
            end_tick_1 = note1.absolute_tick + note1.duration_ticks
            start_tick_2 = note2.absolute_tick
            
            if start_tick_2 < end_tick_1:
                overlap = end_tick_1 - start_tick_2
                
                # Dozvoli minimalno preklapanje za legato
                if overlap > 50:  # Više od 50 tickova preklapanja
                    self.violations.append(PerformanceViolation(
                        note_event=note2,
                        violation_type="MONOPHONIC_OVERLAP",
                        severity=ViolationSeverity.ERROR,
                        description=f"Monofoni instrument ne može svirati dvije note istovremeno (overlap: {overlap} ticks)",
                        suggested_fix={"duration_note1": note1.duration_ticks - overlap}
                    ))
            
            # Provjera intervala (da li je skok prevelik?)
            interval = abs(note2.pitch - note1.pitch)  # Koristi 'pitch' umjesto 'note'
            if interval > 12:  # Veći od oktave
                # Za neke instrumente (flauta, violina) ovo je OK, za trombone teže
                if profile.family in [InstrumentFamily.BRASS]:
                    self.violations.append(PerformanceViolation(
                        note_event=note2,
                        violation_type="LARGE_LEAP",
                        severity=ViolationSeverity.WARNING,
                        description=f"Veliki skok ({interval} polustepeni) može biti težak za izvođenje",
                        suggested_fix=None
                    ))
        
        # Provjera brzine ponavljanja (trill limit)
        delta_time = note2.absolute_tick - note1.absolute_tick
        if delta_time < 100:  # Vrlo brzo
            # Da li instrument može izvesti tako brze note?
            pass  # TODO: Dodati limit po instrumentu
    
    def auto_repair(self, violations: List[PerformanceViolation]) -> int:
        """Automatski popravlja greške u MIDI eventima"""
        repaired_count = 0
        
        for v in violations:
            if v.suggested_fix and v.severity in [ViolationSeverity.ERROR, ViolationSeverity.CRITICAL]:
                note = v.note_event
                
                if "pitch" in v.suggested_fix:
                    old_pitch = note.pitch
                    note.pitch = v.suggested_fix["pitch"]
                    note.changed = True
                    repaired_count += 1
                
                if "velocity" in v.suggested_fix:
                    old_vel = note.velocity
                    note.velocity = v.suggested_fix["velocity"]
                    note.changed = True
                    repaired_count += 1
                
                if "duration_note1" in v.suggested_fix:
                    # Ovo zahtijeva pristup prethodnoj noti, preskoči za sada
                    pass
        
        return repaired_count


class TechniqueDetector:
    """Detektuje koje se tehnike izvode u MIDI tracku"""
    
    def __init__(self, document: MidiDocument):
        self.document = document
    
    def detect_techniques_in_track(self, track: MidiTrack) -> Dict[PlayingTechnique, List[NoteEvent]]:
        """Vraća mapu: Tehnika -> Lista nota koje je koriste"""
        profile = INSTRUMENT_DB.get_profile_by_program(0)  # TODO: Pravilna detekcija
        if not profile:
            return {}
        
        detected = {tech: [] for tech in profile.techniques.keys()}
        notes = [e for e in track.events if isinstance(e, NoteEvent)]
        notes.sort(key=lambda x: x.absolute_tick)
        
        for i, note in enumerate(notes):
            # Detekcija po velocity-u
            for technique, constraint in profile.techniques.items():
                match = True
                
                if note.velocity < constraint.min_velocity or note.velocity > constraint.max_velocity:
                    match = False
                
                if note.duration_ticks < constraint.min_duration_ticks or note.duration_ticks > constraint.max_duration_ticks:
                    match = False
                
                # Provjera CC uslova
                if constraint.required_cc:
                    # Potraži CC evente u blizini note
                    cc_found = False
                    for cc_num, expected_val in constraint.required_cc.items():
                        # Simplificirana provjera - treba poboljšati
                        pass
                
                if match:
                    detected[technique].append(note)
        
        # Filtriraj prazne liste
        return {k: v for k, v in detected.items() if len(v) > 0}
