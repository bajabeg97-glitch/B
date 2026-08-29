"""
UNIFIED VELOCITY ENGINE
=======================
Glavni orchestrator koji objedinjuje Factory i Gold engine.
Određuje kada koristiti tehničku (Factory) a kada muzičku (Gold) obradu,
te omogućava hibridne modeove sa podesivim blendanjem.
"""

from typing import List, Dict, Optional, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.velocity_models import (
    ArticulationType, VelocityProfile, ProcessedNoteData, 
    VelocityContext, ArticulationMap
)
from core.models import MidiTrack, NoteEvent
from engine.factory_velocity_engine import FactoryVelocityEngine
from engine.gold_velocity_engine import GoldVelocityEngine

class UnifiedVelocityEngine:
    """
    Centralni engine za sve operacije vezane uz velocity.
    """
    
    def __init__(self):
        self.factory_engine = FactoryVelocityEngine()
        self.gold_engine = GoldVelocityEngine()
        
        # Konfiguracija mode-a
        self.current_mode = "BALANCED"  # FACTORY_ONLY, GOLD_ONLY, BALANCED, CUSTOM
        self.blend_ratio = 0.5  # 0.0 = 100% Factory, 1.0 = 100% Gold
        
    def set_mode(self, mode: str, blend_ratio: Optional[float] = None):
        """Postavi režim obrade"""
        valid_modes = ["FACTORY_ONLY", "GOLD_ONLY", "BALANCED", "CUSTOM"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode. Choose from: {valid_modes}")
            
        self.current_mode = mode
        
        if blend_ratio is not None:
            self.blend_ratio = max(0.0, min(1.0, blend_ratio))
        elif mode == "FACTORY_ONLY":
            self.blend_ratio = 0.0
        elif mode == "GOLD_ONLY":
            self.blend_ratio = 1.0
        elif mode == "BALANCED":
            self.blend_ratio = 0.5
            
    def load_gold_reference(self, profile_name: str, reference_track: MidiTrack):
        """Učitaj Gold referencu iz MIDI tracka"""
        notes = [e for e in reference_track.events if isinstance(e, NoteEvent)]
        self.gold_engine.load_gold_profile(profile_name, notes)
        
    def analyze_track(self, track: MidiTrack, instrument_type: str = "piano") -> VelocityProfile:
        """Analiziraj track i vrati profil"""
        notes = [e for e in track.events if isinstance(e, NoteEvent)]
        return self.factory_engine.analyze_track_profile(notes, instrument_type)
        
    def process_track(self, track: MidiTrack, instrument_type: str = "piano",
                     gold_profile_name: Optional[str] = None) -> List[ProcessedNoteData]:
        """
        Procesuiraj cijeli track kroz odabrani mode.
        Vraća listu ProcessedNoteData objekata sa svim informacijama o promjenama.
        """
        notes = [e for e in track.events if isinstance(e, NoteEvent)]
        results = []
        
        # Kreiraj Factory artikulacijsku mapu
        factory_art_map = self.factory_engine.create_articulation_map(instrument_type, 0)
        
        # Učitaj Gold profil ako je dostupan
        has_gold = gold_profile_name and gold_profile_name in self.gold_engine.gold_profiles
        
        for i, note in enumerate(notes):
            # 1. Factory processing (uvijek se radi kao baza)
            factory_data = self.factory_engine.process_note(note, factory_art_map)
            
            # 2. Gold processing (ako je dostupno i potrebno)
            gold_data = None
            if has_gold and self.current_mode != "FACTORY_ONLY":
                # Izračunaj poziciju u frazi (pojednostavljeno)
                phrase_pos = i / max(1, len(notes) - 1)
                gold_data = self.gold_engine.apply_phrase_contour(
                    note, gold_profile_name, phrase_pos
                )
                
            # 3. Blendovanje prema mode-u
            if self.current_mode == "FACTORY_ONLY":
                final_data = factory_data
            elif self.current_mode == "GOLD_ONLY" and gold_data:
                final_data = gold_data
            elif self.current_mode == "GOLD_ONLY" and not gold_data:
                final_data = factory_data  # Fallback
            else:  # BALANCED ili CUSTOM
                if gold_data:
                    final_data = self.gold_engine.blend_factory_and_gold(
                        factory_data, gold_data, self.blend_ratio
                    )
                else:
                    final_data = factory_data
                    
            results.append(final_data)
            
        return results
        
    def apply_processing_to_track(self, track: MidiTrack, processed_data: List[ProcessedNoteData]):
        """
        Primjeni rezultate processinga na stvarne MIDI evente u tracku.
        Ovo modificira originalne evente!
        """
        notes_in_track = [e for e in track.events if isinstance(e, NoteEvent)]
        
        if len(notes_in_track) != len(processed_data):
            raise ValueError("Mismatch between notes and processed data count")
            
        modifications_count = 0
        
        for note, data in zip(notes_in_track, processed_data):
            if data.is_modified:
                # Sačuvaj originalni velocity u metadata (za undo)
                if not hasattr(note, 'metadata'):
                    note.metadata = {}
                note.metadata['original_velocity'] = data.original_velocity
                note.metadata['articulation'] = data.articulation.value
                note.metadata['modification_reason'] = data.modification_reason
                
                # Aplikuj novi velocity
                note.velocity = data.processed_velocity
                
                # Aplikuj release velocity (ako model podržava)
                if hasattr(note, 'release_velocity'):
                    note.release_velocity = data.release_velocity
                    
                modifications_count += 1
                
        return modifications_count
        
    def generate_velocity_report(self, processed_data: List[ProcessedNoteData]) -> Dict:
        """
        Generiši detaljan izvještaj o izvršenim promjenama.
        """
        total_notes = len(processed_data)
        modified_notes = sum(1 for d in processed_data if d.is_modified)
        
        # Brojanje po artikulacijama
        articulation_counts = {}
        for data in processed_data:
            art = data.articulation.value
            articulation_counts[art] = articulation_counts.get(art, 0) + 1
            
        # Statistika promjena
        velocity_changes = []
        for data in processed_data:
            if data.is_modified:
                diff = data.processed_velocity - data.original_velocity
                velocity_changes.append(diff)
                
        avg_change = sum(velocity_changes) / len(velocity_changes) if velocity_changes else 0
        max_increase = max(velocity_changes) if velocity_changes else 0
        max_decrease = min(velocity_changes) if velocity_changes else 0
        
        return {
            'total_notes': total_notes,
            'modified_notes': modified_notes,
            'modification_percentage': (modified_notes / total_notes * 100) if total_notes > 0 else 0,
            'average_velocity_change': round(avg_change, 2),
            'max_velocity_increase': max_increase,
            'max_velocity_decrease': max_decrease,
            'articulation_distribution': articulation_counts,
            'mode_used': self.current_mode,
            'blend_ratio': self.blend_ratio
        }
