"""
FILL GENERATOR - Generiše bubanj fill-ove na prelazima.
"""

from core.models import MidiTrack, MidiDocument
from typing import List, Dict

class FillGenerator:
    def generate_fills_for_project(self, project, intensity: str = 'medium') -> MidiTrack:
        """Generiše fill-ove za cijeli projekt."""
        
        doc = project.active_document if hasattr(project, 'active_document') else MidiDocument()
        fill_track = doc.add_track(name="Drum Fills")
        fill_track.program_change(9, 0)  # Channel 10 (bubnjevi), Program 0
        
        # Generiši fill svakih 8 taktova
        ppq = doc.ppqn if hasattr(doc, 'ppqn') else 480
        ticks_per_bar = ppq * 4
        
        for bar in range(2, 16, 4):  # Fill na taktu 4, 8, 12...
            tick_start = (bar * ticks_per_bar) - ticks_per_bar  # Počni jedan takt ranije
            
            if intensity == 'light':
                self._add_light_fill(fill_track, tick_start, ppq)
            elif intensity == 'medium':
                self._add_medium_fill(fill_track, tick_start, ppq)
            else:
                self._add_heavy_fill(fill_track, tick_start, ppq)
                
        return fill_track
    
    def _add_light_fill(self, track: MidiTrack, tick: int, ppq: int):
        """Jednostavan snare roll."""
        # Snare na svaku osminu u zadnjem taktu
        for i in range(8):
            track.add_note(tick + (i * ppq // 2), ppq // 4, 38, 90)  # Snare
    
    def _add_medium_fill(self, track: MidiTrack, tick: int, ppq: int):
        """Tom fill sa rastućom brzinom."""
        toms = [50, 47, 45, 43]  # High, Mid, Low, Floor tom
        
        # Svaki tom dobija 4 note (16-e)
        for tom_idx, tom_note in enumerate(toms):
            for i in range(4):
                track.add_note(
                    tick + (tom_idx * ppq // 4) + (i * ppq // 16),
                    ppq // 8,
                    tom_note,
                    95 + (i * 5)  # Crescendo velocity
                )
    
    def _add_heavy_fill(self, track: MidiTrack, tick: int, ppq: int):
        """Težak fill sa crash-om na kraju."""
        self._add_medium_fill(track, tick, ppq)
        # Dodaj crash na početku sljedećeg takta
        track.add_note(tick + ppq, ppq // 2, 49, 110)  # Crash Cymbal
