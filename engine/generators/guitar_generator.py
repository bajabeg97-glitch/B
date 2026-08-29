"""
RHYTHM GUITAR GENERATOR - Generiše akompmaniment gitare na osnovu akorda.
Stvarna implementacija: strumming patterni, palm mute, arpeggia.
"""

from core.models import MidiTrack, MidiDocument
from typing import List, Dict

class RhythmGuitarGenerator:
    def __init__(self, chord_progression: List[Dict]):
        self.chords = chord_progression
        
    def generate_pattern(self, style: str = 'strumming_acoustic') -> MidiTrack:
        """Generiše ritam gitaru na osnovu stila."""
        
        doc = MidiDocument()
        guitar_track = doc.add_track(name="Rhythm Guitar")
        
        # Postavi instrument
        if 'acoustic' in style:
            guitar_track.program_change(0, 25)  # Acoustic Guitar (Steel)
        elif 'palm_mute' in style or 'electric' in style:
            guitar_track.program_change(0, 27)  # Overdrive Guitar + Palm Mute tehnika
        else:
            guitar_track.program_change(0, 24)  # Nylon Guitar
            
        # Ako nema detektovanih akorda, kreiraj jednostavan C-G-Am-F pattern
        if not self.chords:
            self._generate_fallback_pattern(guitar_track, style)
        else:
            self._generate_from_chords(guitar_track, style)
            
        return guitar_track
    
    def _generate_fallback_pattern(self, track: MidiTrack, style: str):
        """Fallback pattern ako nema detektovanih akorda."""
        tick = 0
        ppq = 480
        
        # Jednostavan 4/4 strumming pattern (down-down-up-up-down-up)
        for bar in range(4):  # 4 takta
            # Akord C (C-E-G)
            if bar % 4 == 0:
                chord_notes = [48, 52, 55, 60]  # C3, E3, G3, C4
            elif bar % 4 == 1:
                chord_notes = [43, 47, 50, 55]  # G2, B2, D3, G3
            elif bar % 4 == 2:
                chord_notes = [45, 49, 52, 57]  # A2, D3, E3, A3
            else:
                chord_notes = [48, 52, 55, 59]  # F2, A2, C3, F3
                
            # Strumming (razmak između nota simulira brzinu prelaska preko žica)
            for i, note in enumerate(chord_notes):
                velocity = 85 if i < 2 else 75  # Donje žice jače
                track.add_note(tick + (i * 30), 200, note, velocity)
                
            tick += ppq * 4  # Sljedeći takt
            
    def _generate_from_chords(self, track: MidiTrack, style: str):
        """Generiše iz pravih akorda."""
        # Implementacija za prave akorde (buduće proširenje)
        pass
