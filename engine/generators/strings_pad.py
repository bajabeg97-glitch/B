"""
STRINGS PAD GENERATOR - Dodaje pozadinske gudala/padove.
"""

from core.models import MidiTrack, MidiDocument
from typing import List, Dict

class StringsPadGenerator:
    def __init__(self, chord_progression: List[Dict]):
        self.chords = chord_progression
        
    def generate_pad_layer(self, voicing: str = 'wide', dynamics: str = 'crescendo') -> MidiTrack:
        """Generiše pad layer."""
        
        doc = MidiDocument()
        pad_track = doc.add_track(name="Strings Pad")
        pad_track.program_change(0, 48)  # String Ensemble
        
        # Ako nema akorda, kreiraj jednostavne dugote note
        if not self.chords:
            self._generate_simple_pad(pad_track)
            
        return pad_track
    
    def _generate_simple_pad(self, track: MidiTrack):
        """Jednostavan pad: dugi akordi svaka 2 takta."""
        tick = 0
        ppq = 480
        
        # C - G - Am - F progression (svaki po 2 takta)
        chords = [
            [48, 52, 55, 60],  # C
            [43, 47, 50, 55],  # G
            [45, 49, 52, 57],  # Am
            [48, 52, 55, 59],  # F
        ]
        
        for chord in chords:
            velocity = 60 if dynamics == 'crescendo' else 70
            for note in chord:
                track.add_note(tick, ppq * 8, note, velocity)  # Duga nota (2 takta)
            tick += ppq * 8
