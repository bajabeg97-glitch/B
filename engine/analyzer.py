"""
MINIMAL ANALYZER - Stvarna detekcija uloga i akorda.
Bez lažnih obećanja. Samo matematika na MIDI eventima.
"""

from core.models import MidiProject, MidiTrack, NoteEvent, ControllerEvent
from typing import List, Dict, Tuple, Optional
import math
from collections import Counter

class ChordAnalyzer:
    """Detektuje akorde iz nota."""
    
    # Definicije akorda (intervali od roota)
    CHORD_SHAPES = {
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        '7': [0, 4, 7, 10],
        'maj7': [0, 4, 7, 11],
        'm7': [0, 3, 7, 10],
        'dim': [0, 3, 6],
        'aug': [0, 4, 8],
        'sus4': [0, 5, 7],
        'sus2': [0, 2, 7],
    }
    
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def extract_chords_from_tracks(self, tracks: List[MidiTrack]) -> List[Dict]:
        """Izvlači akorde iz više trackova analizom simultanih nota."""
        if not tracks:
            return []
            
        # Sakupi sve note sa svih trackova
        all_notes = []
        for track in tracks:
            for event in track.events:
                if isinstance(event, NoteEvent) and event.is_note_on:
                    all_notes.append({
                        'tick': event.absolute_tick,
                        'pitch': event.note,
                        'duration': event.duration,
                        'end_tick': event.absolute_tick + event.duration
                    })
        
        if not all_notes:
            return []
            
        # Sortiraj po vremenu
        all_notes.sort(key=lambda x: x['tick'])
        
        chords = []
        current_chord_notes = []
        last_tick = 0
        
        # Jednostavna detekcija: grupiši note koje se preklapaju
        for note in all_notes:
            if note['tick'] - last_tick > 480:  # Više od jednog takta razmake -> novi akord
                if current_chord_notes:
                    chord = self._identify_chord(current_chord_notes)
                    if chord:
                        chords.append(chord)
                current_chord_notes = []
            
            # Dodaj notu ako je aktivna
            current_chord_notes.append(note)
            
            # Ukloni note koje su završile
            current_chord_notes = [n for n in current_chord_notes if n['end_tick'] > note['tick']]
            last_tick = note['tick']
        
        # Posljednji akord
        if current_chord_notes:
            chord = self._identify_chord(current_chord_notes)
            if chord:
                chords.append(chord)
                
        return chords
    
    def _identify_chord(self, notes: List[Dict]) -> Optional[Dict]:
        """Identifikuje akord iz liste nota."""
        if len(notes) < 2:
            return None
            
        pitches = list(set([n['pitch'] for n in notes]))
        if len(pitches) < 2:
            return None
            
        # Nađi najnižu notu (potential root)
        root_pitch = min(pitches)
        root_name = self.NOTE_NAMES[root_pitch % 12]
        
        # Izračunaj intervale od roota
        intervals = sorted([(p - root_pitch) % 12 for p in pitches])
        
        # Poredaj sa poznatim oblicima
        best_match = None
        best_score = 0
        
        for chord_name, shape in self.CHORD_SHAPES.items():
            matched = sum(1 for interval in shape if interval in intervals)
            score = matched / len(shape)
            
            if score > best_score:
                best_score = score
                best_match = chord_name
        
        if best_score < 0.6:  # Premalo poklapanja
            return None
            
        return {
            'root': root_name,
            'quality': best_match,
            'confidence': best_score,
            'notes': pitches
        }
    
    def parse_chord_track(self, chord_track: MidiTrack) -> List[Dict]:
        """Parsira eksplicitni chord track (ako postoji)."""
        # Za sada jednostavno vrati praznu listu - implementacija zavisi od formata
        return []


class RoleDetector:
    """Detektuje ulogu instrumenta iz MIDI podataka."""
    
    def detect_role(self, track: MidiTrack) -> Dict:
        """Analizira track i vraća vjerovatnoće uloga."""
        if track.is_empty():
            return {'primary_role': 'empty', 'confidence': 0.0}
        
        # Ekstrakcija featurea
        notes = [e for e in track.events if isinstance(e, NoteEvent) and e.is_note_on]
        if not notes:
            return {'primary_role': 'control_track', 'confidence': 0.5}
        
        # 1. Pitch range
        pitches = [n.note for n in notes]
        min_pitch = min(pitches)
        max_pitch = max(pitches)
        pitch_range = max_pitch - min_pitch
        
        # 2. Polyphony (prosjek istovremenih nota)
        polyphony = self._calculate_avg_polyphony(notes)
        
        # 3. Rhythmic density (note po taktu)
        density = self._calculate_density(notes, track)
        
        # 4. Velocity stats
        velocities = [n.velocity for n in notes]
        avg_vel = sum(velocities) / len(velocities) if velocities else 0
        
        # Program change (ako postoji)
        program = track.get_program_change()
        
        # Pravila za detekciju
        roles = {}
        
        # BUBNJEVI: Channel 10 ili visoka percusivnost
        if track.channel == 9 or (min_pitch >= 35 and max_pitch <= 81 and polyphony < 3):
            roles['drums'] = 0.9
            
        # BAS: Niske note, mala gustina, monofon
        if max_pitch <= 55 and polyphony < 2.5 and density < 6:
            roles['bass'] = 0.85
            
        # SOLO/MELODIJA: Srednje-visoke note, monofon, umjerena gustina
        if min_pitch >= 48 and polyphony < 2.0 and 2 < density < 8:
            roles['solo'] = 0.75
            roles['melody'] = 0.70
            
        # PIANO/KEYS: Širok raspon, polifonija 3-6
        if pitch_range > 24 and 2.5 < polyphony < 7:
            roles['piano'] = 0.80
            roles['keys'] = 0.75
            
        # GITARA (ritam): Srednji raspon, polifonija 3-6, specifični programi
        if 40 <= min_pitch <= 70 and 2.5 < polyphony < 7 and program in [24, 25, 26, 27]:
            roles['guitar_rhythm'] = 0.85
            
        # GUDALA/PAD: Duge note, visoka polifonija, spor ritam
        if density < 3 and polyphony > 3 and pitch_range > 12:
            roles['strings_pad'] = 0.70
            
        # Nađi najbolju ulogu
        if roles:
            best_role = max(roles, key=roles.get)
            return {'primary_role': best_role, 'confidence': roles[best_role], 'all_roles': roles}
        
        return {'primary_role': 'unknown', 'confidence': 0.3}
    
    def _calculate_avg_polyphony(self, notes: List[NoteEvent]) -> float:
        """Računa prosječan broj istovremenih nota."""
        if not notes:
            return 0.0
            
        events = []
        for n in notes:
            events.append((n.absolute_tick, 1))  # Note On
            events.append((n.absolute_tick + n.duration, -1))  # Note Off
        
        events.sort(key=lambda x: x[0])
        
        max_poly = 0
        current_poly = 0
        
        for _, delta in events:
            current_poly += delta
            max_poly = max(max_poly, current_poly)
        
        return max_poly
    
    def _calculate_density(self, notes: List[NoteEvent], track: MidiTrack) -> float:
        """Računa note po taktu."""
        if not notes or not track:
            return 0.0
            
        duration_bars = max(1, track.get_duration_bars())
        return len(notes) / duration_bars
