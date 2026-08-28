"""
FACTORY VELOCITY ENGINE
=======================
Tehnička kalibracija velocity-a bazirana na hardverskim specifikacijama.
Ovaj engine ne brine o "muzičkom osjećaju" (to radi Gold Engine),
već osigurava da velocity vrijednosti budu tehnički ispravne za target uređaj.

Fokus:
- Precizno mapiranje velocity zona za RX/DNC
- Hard limiting (sprječavanje klipinga/ekstremnih vrijednosti)
- CC coupling (vezivanje velocity-a sa CC kontrolama)
- Release Velocity validacija
"""

from typing import Dict, List, Optional, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.velocity_models import (
    ArticulationType, ArticulationMap, VelocityProfile, 
    ProcessedNoteData, VelocityContext, VelocityCurve
)
from core.models import MidiEvent, NoteEvent

class FactoryVelocityEngine:
    """
    Engine za tehničku obradu velocity-a prema Factory specifikacijama.
    """
    
    def __init__(self):
        # Default Korg Pa800/Roland zone konfiguracije
        self.default_zones = {
            'piano': [
                (0, 40, ArticulationType.GHOST),
                (41, 70, ArticulationType.NORMAL),
                (71, 100, ArticulationType.ACCENT),
                (101, 127, ArticulationType.MARCATO)
            ],
            'guitar': [
                (0, 50, ArticulationType.GHOST),
                (51, 80, ArticulationType.NORMAL),
                (81, 105, ArticulationType.SLIDE),  # Slide trigger
                (106, 127, ArticulationType.NOISE)  # Noise/Scratch trigger
            ],
            'bass': [
                (0, 45, ArticulationType.GHOST),
                (46, 75, ArticulationType.NORMAL),
                (76, 100, ArticulationType.ACCENT),
                (101, 127, ArticulationType.MUTE)   # Mute/Slap trigger
            ],
            'drums': [
                (0, 30, ArticulationType.GHOST),
                (31, 60, ArticulationType.NORMAL),
                (61, 90, ArticulationType.ACCENT),
                (91, 110, ArticulationType.FLAM),
                (111, 127, ArticulationType.ROLL)
            ]
        }
        
    def create_articulation_map(self, instrument_type: str, program_number: int) -> ArticulationMap:
        """Kreira ArticulationMap za specifičan instrument"""
        zones = self.default_zones.get(instrument_type, self.default_zones['piano'])
        
        art_map = ArticulationMap(
            instrument_id=instrument_type,
            program_number=program_number,
            rx_noise_threshold=100 if instrument_type == 'guitar' else 127,
            legato_window_ms=50
        )
        
        for min_v, max_v, art_type in zones:
            art_map.add_zone(min_v, max_v, art_type)
            
        return art_map
        
    def apply_hard_limiting(self, velocity: int, min_limit: int = 10, max_limit: int = 120) -> int:
        """
        Sprječava ekstremne velocity vrijednosti koje mogu izazvati probleme.
        Neki soundovi imaju "mrtve zone" na 0-5 ili 125-127.
        """
        if velocity < min_limit:
            return min_limit
        if velocity > max_limit:
            return max_limit
        return velocity
        
    def couple_cc_with_velocity(self, event: MidiEvent, cc_mod_depth: int = 74) -> List[MidiEvent]:
        """
        Automatski dodaje CC kontrolere bazirane na velocity-u.
        Npr. visoki velocity → dodaj CC74 (Brightness) za sjajniji zvuk.
        """
        if not isinstance(event, NoteEvent):
            return [event]
            
        result_events = [event]
        
        # Primjer: Velocity > 100 → dodaj Brightness boost
        if event.velocity > 100:
            brightness_cc = min(127, int((event.velocity - 100) * 2.5))
            cc_event = MidiEvent(
                event_type='control_change',
                channel=event.channel,
                absolute_tick=event.absolute_tick,
                control=74,  # Brightness
                value=brightness_cc
            )
            result_events.append(cc_event)
            
        # Primjer: Ghost note → dodaj malo Timbre/Harmonic content
        elif event.velocity < 50:
            timbre_cc = max(0, int(50 - event.velocity))
            cc_event = MidiEvent(
                event_type='control_change',
                channel=event.channel,
                absolute_tick=event.absolute_tick,
                control=71,  # Harmonic Content
                value=timbre_cc
            )
            result_events.append(cc_event)
            
        return result_events
        
    def validate_release_velocity(self, note_on_vel: int, note_off_vel: Optional[int]) -> int:
        """
        Validira i popravlja Release Velocity.
        Mnogi uređaji ignorišu note-off velocity, ali RX engine ga koristi za noise/release sample.
        """
        if note_off_vel is None:
            # Ako nema note-off velocity, generiši logičan default
            # Obično je release tiši od attack-a
            return max(0, note_on_vel - 40)
            
        # Ako je release glasniji od attack-a (često greška), smanji ga
        if note_off_vel > note_on_vel:
            return int(note_on_vel * 0.6)
            
        return note_off_vel
        
    def process_note(self, event: NoteEvent, art_map: ArticulationMap) -> ProcessedNoteData:
        """
        Glavna metoda za obradu jedne note kroz Factory engine.
        """
        # 1. Odredi artikulaciju
        articulation = art_map.get_articulation(event.velocity)
        
        # 2. Aplikuj hard limiting ako je potrebno
        original_vel = event.velocity
        if articulation in [ArticulationType.NOISE, ArticulationType.SLIDE]:
            # Ove artikulacije trebaju biti u specifičnom range-u
            processed_vel = self.apply_hard_limiting(event.velocity, min_limit=80, max_limit=127)
        else:
            processed_vel = self.apply_hard_limiting(event.velocity)
            
        # 3. Validiraj release velocity
        release_vel = self.validate_release_velocity(event.velocity, getattr(event, 'release_velocity', None))
        
        # 4. Kreiraj kontekst (pojednostavljen za sada)
        context = VelocityContext(
            position_in_phrase=0.5,  # Placeholder
            position_in_measure=0.0, # Placeholder
            beat_strength=1.0,
            is_chord_tone=True,
            is_passing_tone=False,
            surrounding_density=0,
            previous_velocity=original_vel,
            next_velocity=original_vel
        )
        
        # 5. Odredi da li je došlo do modifikacije
        is_modified = (processed_vel != original_vel)
        reason = ""
        if is_modified:
            if processed_vel > original_vel:
                reason = f"Factory limit boost for {articulation.value}"
            else:
                reason = f"Factory hard limit for {articulation.value}"
                
        return ProcessedNoteData(
            original_velocity=original_vel,
            processed_velocity=processed_vel,
            release_velocity=release_vel,
            articulation=articulation,
            confidence=0.95,  # Factory pravila su visoko pouzdana
            context=context,
            is_modified=is_modified,
            modification_reason=reason
        )

    def analyze_track_profile(self, notes: List[NoteEvent], instrument_type: str) -> VelocityProfile:
        """
        Analizira cijeli track i kreira VelocityProfile.
        """
        if not notes:
            return VelocityProfile(
                mean_velocity=0, std_deviation=0, min_velocity=0, 
                max_velocity=0, dynamic_range=0, ghost_ratio=0, 
                accent_ratio=0, normal_ratio=0, timing_velocity_corr=0
            )
            
        velocities = [n.velocity for n in notes]
        mean_vel = sum(velocities) / len(velocities)
        std_dev = (sum((v - mean_vel) ** 2 for v in velocities) / len(velocities)) ** 0.5
        
        # Brojanje artikulacija
        art_map = self.create_articulation_map(instrument_type, 0)
        ghost_count = 0
        accent_count = 0
        normal_count = 0
        
        for note in notes:
            art = art_map.get_articulation(note.velocity)
            if art == ArticulationType.GHOST:
                ghost_count += 1
            elif art in [ArticulationType.ACCENT, ArticulationType.MARCATO]:
                accent_count += 1
            else:
                normal_count += 1
                
        total = len(notes)
        
        return VelocityProfile(
            mean_velocity=mean_vel,
            std_deviation=std_dev,
            min_velocity=min(velocities),
            max_velocity=max(velocities),
            dynamic_range=max(velocities) - min(velocities),
            ghost_ratio=ghost_count / total,
            accent_ratio=accent_count / total,
            normal_ratio=normal_count / total,
            phrase_arc=[],  # Popuniti u Gold Engine-u
            timing_velocity_corr=0.0  # Popuniti u Gold Engine-u
        )
