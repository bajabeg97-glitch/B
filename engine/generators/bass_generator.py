"""
BASS GENERATOR + ORNAMENT LAYER
Dodaje passing note, slide i ghost note na postojeći bas.
"""

from core.models import MidiTrack, MidiDocument, NoteEvent
from typing import List, Dict

class BassGenerator:
    def __init__(self, chord_progression: List[Dict]):
        self.chords = chord_progression
        
    def generate_ornament_layer(self, base_track: MidiTrack) -> MidiTrack:
        """Kreira dodatni track samo sa ornamentima (ghost notes, slides)."""
        
        doc = base_track.document if hasattr(base_track, 'document') else MidiDocument()
        ornament_track = doc.add_track(name="Bass Ornaments")
        ornament_track.program_change(0, 38)  # Synth Bass (ili isti kao original)
        
        # Analiziraj originalni bas i dodaj ukrase
        prev_note = None
        
        for event in base_track.events:
            if isinstance(event, NoteEvent) and event.is_note_on:
                current_note = event.note
                
                # Dodaj ghost note prije glavne note ako je interval > 4
                if prev_note and abs(current_note - prev_note) > 4:
                    ghost_pitch = prev_note + (1 if current_note > prev_note else -1)
                    ornament_track.add_note(
                        tick=event.absolute_tick - 60,  # Malo prije
                        duration=30,
                        pitch=ghost_pitch,
                        velocity=40  # Vrlo tiho
                    )
                
                prev_note = current_note
                
        return ornament_track
