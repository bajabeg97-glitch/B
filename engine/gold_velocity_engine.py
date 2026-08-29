"""
GOLD VELOCITY ENGINE
====================
Muzička obrada velocity-a bazirana na analizi referentnih "Gold" MIDI fajlova.
Dok Factory engine brine o tehničkoj ispravnosti, Gold engine unosi:
- Muzički osjećaj (feel)
- Frazeologiju (phrase contour)
- Stilsku specifičnost (Balkan, Jazz, Funk, itd.)
- Ljudske nesavršenosti koje čine izvedbu živom

Ovaj engine uči iz referentnih fajlova i primjenjuje "DNA" tih izvedbi na target note.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.velocity_models import (
    ArticulationType, VelocityProfile, ProcessedNoteData, 
    VelocityContext, VelocityCurve
)
from core.models import NoteEvent

class GoldVelocityEngine:
    """
    Engine za muzičku obradu velocity-a baziran na Gold referencama.
    """
    
    def __init__(self):
        # Učitani Gold profili (u produkciji bi se učitali iz baze)
        self.gold_profiles = {}
        
    def load_gold_profile(self, profile_name: str, reference_notes: List[NoteEvent]):
        """
        Analizira referentne note i kreira Gold profil.
        Ovo simulira učenje iz stvarnih ljudskih izvedbi.
        """
        if not reference_notes:
            return
            
        # Ekstrakcija phrase contour-a
        velocities = [n.velocity for n in reference_notes]
        positions = [n.absolute_tick for n in reference_notes]
        
        # Podjela fraze na 3 dijela (početak, sredina, kraj)
        n = len(velocities)
        third = max(1, n // 3)
        
        start_avg = np.mean(velocities[:third]) if n >= 3 else velocities[0]
        mid_avg = np.mean(velocities[third:2*third]) if n >= 6 else (np.mean(velocities[third:]) if n > 3 else velocities[-1])
        end_avg = np.mean(velocities[2*third:]) if n >= 3 else velocities[-1]
        
        # Detekcija ghost nota patterna
        ghost_threshold = np.percentile(velocities, 25)
        ghost_positions = [positions[i] for i, v in enumerate(velocities) if v < ghost_threshold]
        
        # Detekcija accent patterna
        accent_threshold = np.percentile(velocities, 75)
        accent_positions = [positions[i] for i, v in enumerate(velocities) if v > accent_threshold]
        
        # Timing-Velocity korelacija
        if len(velocities) > 2:
            # Da li kasnije note imaju tendenciju biti tiše/glasnije?
            time_diffs = np.diff(positions)
            vel_diffs = np.diff(velocities)
            if len(time_diffs) > 1 and len(vel_diffs) > 1 and np.std(time_diffs) > 0 and np.std(vel_diffs) > 0:
                corr = np.corrcoef(time_diffs[:len(vel_diffs)], vel_diffs)[0, 1]
                if np.isnan(corr):
                    corr = 0.0
            else:
                corr = 0.0
        else:
            corr = 0.0
            
        self.gold_profiles[profile_name] = {
            'phrase_arc': [start_avg, mid_avg, end_avg],
            'ghost_positions': ghost_positions,
            'accent_positions': accent_positions,
            'mean_velocity': np.mean(velocities),
            'std_deviation': np.std(velocities),
            'timing_velocity_corr': corr,
            'reference_count': len(reference_notes)
        }
        
    def apply_phrase_contour(self, note: NoteEvent, profile_name: str, 
                             phrase_position: float) -> ProcessedNoteData:
        """
        Primjenjuje phrase contour iz Gold profila na notu.
        phrase_position: 0.0 (početak fraze) do 1.0 (kraj fraze)
        """
        if profile_name not in self.gold_profiles:
            # Fallback na factory processing ako profil ne postoji
            return None
            
        profile = self.gold_profiles[profile_name]
        arc = profile['phrase_arc']
        
        # Interpolacija željenog velocity-a baziranog na poziciji u frazi
        if phrase_position < 0.33:
            target_vel = arc[0]
        elif phrase_position < 0.66:
            target_vel = arc[1]
        else:
            target_vel = arc[2]
            
        # Blago prilagođavanje originalnog velocity-a ka target-u (30% uticaja)
        original_vel = note.velocity
        adjusted_vel = int(original_vel * 0.7 + target_vel * 0.3)
        adjusted_vel = max(1, min(127, adjusted_vel))
        
        # Određivanje artikulacije bazirane na Gold pattern-u
        # Ako je pozicija blizu ghost position u referenci, označi kao ghost
        is_ghost = False
        is_accent = False
        
        ref_start_tick = 0  # Pojednostavljenje - u stvarnosti bi se mapiralo
        current_tick_in_phrase = phrase_position * 1000  # Skalirano
        
        for ghost_pos in profile['ghost_positions']:
            if abs(current_tick_in_phrase - ghost_pos) < 100:  # Tolerancija od 100 tickova
                is_ghost = True
                break
                
        for accent_pos in profile['accent_positions']:
            if abs(current_tick_in_phrase - accent_pos) < 100:
                is_accent = True
                break
        
        if is_ghost:
            articulation = ArticulationType.GHOST
            # Ghost note trebaju biti tiše
            adjusted_vel = min(adjusted_vel, 50)
        elif is_accent:
            articulation = ArticulationType.ACCENT
            # Accent note trebaju biti glasnije
            adjusted_vel = max(adjusted_vel, 90)
        else:
            articulation = ArticulationType.NORMAL
            
        context = VelocityContext(
            position_in_phrase=phrase_position,
            position_in_measure=0.0,  # Popuniti iz analyzer-a
            beat_strength=1.0,
            is_chord_tone=True,
            is_passing_tone=False,
            surrounding_density=0,
            previous_velocity=original_vel,
            next_velocity=original_vel
        )
        
        is_modified = (adjusted_vel != original_vel)
        reason = ""
        if is_modified:
            reason = f"Gold phrase contour adjustment ({profile_name})"
            
        return ProcessedNoteData(
            original_velocity=original_vel,
            processed_velocity=adjusted_vel,
            release_velocity=max(0, adjusted_vel - 40),  # Gold release estimation
            articulation=articulation,
            confidence=0.85,  # Malo niža od Factory jer je stilski bazirana
            context=context,
            is_modified=is_modified,
            modification_reason=reason
        )
        
    def transfer_groove_velocity(self, source_profile: str, target_note: NoteEvent,
                                 source_position_ratio: float) -> ProcessedNoteData:
        """
        Transferuje velocity feel iz jednog profila u drugi.
        Koristi se za primjenu "Balkan feel" na bilo koji track.
        """
        if source_profile not in self.gold_profiles:
            return None
            
        profile = self.gold_profiles[source_profile]
        
        # Mapiranje pozicije target note na source profil
        # Ovo je pojednostavljeno - u stvarnosti bi koristilo kompleksnije mapiranje
        mean_vel = profile['mean_velocity']
        std_dev = profile['std_deviation']
        
        # Generiši velocity baziran na statistici profila uz dodavanje varijance
        base_vel = mean_vel
        variation = np.random.normal(0, std_dev * 0.5)
        new_vel = int(base_vel + variation)
        new_vel = max(1, min(127, new_vel))
        
        # Zadrži originalnu artikulaciju ako je već detektovana
        original_vel = target_note.velocity
        articulation = ArticulationType.NORMAL  # Default
        
        # Detekcija na osnovu novog velocity-a
        if new_vel < 45:
            articulation = ArticulationType.GHOST
        elif new_vel > 95:
            articulation = ArticulationType.ACCENT
            
        context = VelocityContext(
            position_in_phrase=source_position_ratio,
            position_in_measure=0.0,
            beat_strength=1.0,
            is_chord_tone=True,
            is_passing_tone=False,
            surrounding_density=0,
            previous_velocity=original_vel,
            next_velocity=original_vel
        )
        
        is_modified = (new_vel != original_vel)
        
        return ProcessedNoteData(
            original_velocity=original_vel,
            processed_velocity=new_vel,
            release_velocity=max(0, new_vel - 40),
            articulation=articulation,
            confidence=0.80,
            context=context,
            is_modified=is_modified,
            modification_reason=f"Groove transfer from {source_profile}"
        )
        
    def blend_factory_and_gold(self, factory_data: ProcessedNoteData, 
                               gold_data: ProcessedNoteData,
                               blend_ratio: float = 0.5) -> ProcessedNoteData:
        """
        Kombinuje Factory (tehnički) i Gold (muzički) processing.
        blend_ratio: 0.0 = 100% Factory, 1.0 = 100% Gold
        """
        if factory_data is None and gold_data is None:
            return None
            
        if factory_data is None:
            return gold_data
        if gold_data is None:
            return factory_data
            
        # Blendovanje velocity-a
        blended_vel = int(
            factory_data.processed_velocity * (1 - blend_ratio) + 
            gold_data.processed_velocity * blend_ratio
        )
        blended_vel = max(1, min(127, blended_vel))
        
        # Blendovanje release velocity-a
        blended_rel = int(
            factory_data.release_velocity * (1 - blend_ratio) + 
            gold_data.release_velocity * blend_ratio
        )
        blended_rel = max(0, min(127, blended_rel))
        
        # Odabir artikulacije (Gold ima prioritet za muzičke odluke)
        if blend_ratio > 0.5:
            articulation = gold_data.articulation
            confidence = gold_data.confidence
            reason = gold_data.modification_reason
        else:
            articulation = factory_data.articulation
            confidence = factory_data.confidence
            reason = factory_data.modification_reason
            
        # Ako su različiti, označi kao hibrid
        if factory_data.articulation != gold_data.articulation:
            articulation = gold_data.articulation if blend_ratio > 0.5 else factory_data.articulation
            reason = f"Blended: {factory_data.modification_reason} + {gold_data.modification_reason}"
            
        return ProcessedNoteData(
            original_velocity=factory_data.original_velocity,
            processed_velocity=blended_vel,
            release_velocity=blended_rel,
            articulation=articulation,
            confidence=confidence * 0.95,  # Malo smanji confidence za blend
            context=factory_data.context,  # Koristi factory kontekst kao bazu
            is_modified=True,
            modification_reason=reason
        )
