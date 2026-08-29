"""
HARMONY GENERATOR - Dodaje tercu/sextu na solo melodiju.
Stvarna implementacija: uzima solo note i dodaje harmoniju po akordima.
"""

from core.models import MidiTrack, MidiDocument, NoteEvent
from typing import List, Dict, Optional

class HarmonyGenerator:
    def __init__(self, chord_progression: List[Dict]):
        self.chords = chord_progression
        
    def generate_harmony_track(self, solo_track: MidiTrack, interval: str = 'third', style: str = 'pop') -> MidiTrack:
        """Kreira novi track sa harmonijom za dato solo."""
        
        doc = getattr(solo_track, "document", None) or MidiDocument()
        harmony_track = doc.add_track(name=f"Solo Harmony ({interval})")
        
        # Postavi instrument (Strings ili Choir)
        harmony_track.program_change(0, 48 if style == 'pop' else 52)  # Strings/Choir
        
        # Definicija intervala
        intervals_map = {
            'third': 4,      # Velika terca
            'minor_third': 3,
            'sixth': 9,      # Velika sexta
            'octave': 12
        }
        interval_semitones = intervals_map.get(interval, 4)
        
        # Kopiraj solo note i dodaj harmoniju
        for event in solo_track.events:
            if isinstance(event, NoteEvent) and event.is_note_on:
                # Izračunaj harmonijsku notu
                harmony_pitch = event.note + interval_semitones
                
                # Provjeri da li je u opsegu (C3-C6)
                if 48 <= harmony_pitch <= 84:
                    # Dodaj harmonijsku notu
                    harmony_track.add_note(
                        tick=event.absolute_tick,
                        duration=event.duration,
                        pitch=harmony_pitch,
                        velocity=int(event.velocity * 0.7)  # Malo tiše od sola
                    )
        
        return harmony_track
