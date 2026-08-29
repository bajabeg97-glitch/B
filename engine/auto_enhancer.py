"""
AUTO ENHANCER ENGINE - "Magic Arranger"
Automatski dodaje missing instrumente, harmonije, gitare, gudala i ornamente.
Koristi Factory/Gold pravila za donošenje odluka.
"""

from core.models import MidiProject, MidiTrack, MidiEvent, NoteEvent
from engine.analyzer import ChordAnalyzer, RoleDetector
from engine.generators.bass_generator import BassGenerator
from engine.generators.guitar_generator import RhythmGuitarGenerator
from engine.generators.solo_harmony import HarmonyGenerator
from engine.generators.fill_generator import FillGenerator
from engine.generators.strings_pad import StringsPadGenerator
from typing import List, Dict, Any
import random

class AutoEnhancer:
    def __init__(self, project: MidiProject):
        self.project = project
        self.document = project.active_document
        self.chord_analyzer = ChordAnalyzer()
        self.role_detector = RoleDetector()
        
        # Detektovani elementi
        self.existing_roles = {}  # {role: track}
        self.chord_progression = []
        self.missing_elements = []
        
    def analyze(self):
        """Analizira projekt i utvrđuje šta fali."""
        print("🔍 Analiza postojećeg aranžmana...")
        
        # 1. Detekcija uloga postojećih trackova
        for track in self.document.tracks:
            if track.is_empty():
                continue
            role_info = self.role_detector.detect_role(track)
            primary_role = role_info['primary_role']
            confidence = role_info['confidence']
            
            if confidence > 0.7:
                self.existing_roles[primary_role] = track
                print(f"   ✅ Nađen: {primary_role} (Track {track.track_index})")
        
        # 2. Ekstrakcija akordske progresije (ako nema Chord Tracka, izvuci iz basa/klavira)
        if 'chord_track' not in self.existing_roles:
            print("   🎹 Rekonstrukcija akordske progresije iz postojećih instrumenata...")
            self.chord_progression = self.chord_analyzer.extract_chords_from_tracks(
                list(self.existing_roles.values())
            )
        else:
            self.chord_progression = self.chord_analyzer.parse_chord_track(
                self.existing_roles['chord_track']
            )
            
        # 3. Identifikacija missing elemenata
        self._identify_missing_elements()
        
        return {
            "found": list(self.existing_roles.keys()),
            "missing": self.missing_elements,
            "chords_detected": len(self.chord_progression) > 0
        }
    
    def _identify_missing_elements(self):
        """Logika odlučivanja šta dodati."""
        has_drums = 'drums' in self.existing_roles
        has_bass = 'bass' in self.existing_roles
        has_solo = 'solo' in self.existing_roles or 'melody' in self.existing_roles
        has_chords = 'piano' in self.existing_roles or 'guitar_rhythm' in self.existing_roles
        
        # Pravilo 1: Ako ima sola, a nema harmonije -> Dodaj tercu/sextu
        if has_solo and 'harmony' not in self.existing_roles:
            self.missing_elements.append('harmony_voice')
            print("   💡 Odluka: Solo nema harmoniju. Dodajem Tercu/Sextu.")
            
        # Pravilo 2: Ako ima ritma (piano), a nema gitare -> Dodaj Rhythm Guitar (Clean/Palm)
        if has_chords and 'guitar_rhythm' not in self.existing_roles:
            self.missing_elements.append('rhythm_guitar')
            print("   💡 Odluka: Fali ritam gitara. Dodajem Clean/Palm Guitar.")
            
        # Pravilo 3: Ako nema gudala/pada za popunu -> Dodaj Strings Pad
        if len(self.existing_roles) < 5 and 'strings_pad' not in self.existing_roles:
            self.missing_elements.append('strings_pad')
            print("   💡 Odluka: Aranžman je previše tanak. Dodajem Strings Pad.")
            
        # Pravilo 4: Ako nema fill-ova između sekcija -> Dodaj Fill track
        if has_drums and 'fills' not in self.existing_roles:
            self.missing_elements.append('drum_fills')
            print("   💡 Odluka: Fale prelazi (fill-ovi). Dodajem Drum Fills.")
            
        # Pravilo 5: Ako bas previše jednostavan -> Predloži обогаћивање (opciono)
        if has_bass:
            bass_track = self.existing_roles['bass']
            if self._is_bass_too_simple(bass_track):
                self.missing_elements.append('bass_embellishment')
                print("   💡 Odluka: Bas je previše statičan. Dodajem passing note/ornamente.")

    def _is_bass_too_simple(self, track: MidiTrack) -> bool:
        # Prosta heuristika: ako ima manje od X nota po taktu u prosjeku
        total_notes = sum(1 for e in track.events if isinstance(e, NoteEvent) and e.is_note_on)
        duration_bars = max(1, track.get_duration_bars())
        density = total_notes / duration_bars
        return density < 4.0  # Manje od 4 note po taktu = jednostavno

    def enhance(self) -> MidiProject:
        """Izvršava dodavanje missing elemenata."""
        if not self.missing_elements:
            print("✅ Aranžman je već potpun. Ništa nije dodato.")
            return self.project
            
        print(f"\n🚀 Počinjem enhancement sa {len(self.missing_elements)} novih elemenata...")
        
        for element in self.missing_elements:
            new_track = self._generate_element(element)
            if new_track:
                self.document.add_track(new_track)
                print(f"   ✅ Dodan track: {new_track.name}")
                
        return self.project

    def _generate_element(self, element_type: str) -> MidiTrack:
        """Generiše konkretni track na osnovu tipa."""
        
        if element_type == 'harmony_voice':
            # Nađi solo track
            solo_track = self.existing_roles.get('solo') or self.existing_roles.get('melody')
            if not solo_track:
                return None
            gen = HarmonyGenerator(self.chord_progression)
            return gen.generate_harmony_track(solo_track, interval='third', style='pop')
            
        elif element_type == 'rhythm_guitar':
            gen = RhythmGuitarGenerator(self.chord_progression)
            # Odaberi stil sviranja na osnovu tempa
            tempo = self.document.get_tempo()
            style = 'strumming_acoustic' if tempo < 120 else 'palm_mute_electric'
            return gen.generate_pattern(style=style)
            
        elif element_type == 'strings_pad':
            gen = StringsPadGenerator(self.chord_progression)
            return gen.generate_pad_layer(voicing='wide', dynamics='crescendo')
            
        elif element_type == 'drum_fills':
            gen = FillGenerator()
            return gen.generate_fills_for_project(self.project, intensity='medium')
            
        elif element_type == 'bass_embellishment':
            bass_track = self.existing_roles['bass']
            # Ovo ne kreira novi track, već modifikuje postojeći (return None jer je inplace)
            # Ali za potrebe enhancera, možemo kreirati "Bass Decor" layer ako želimo non-destructive
            # Ovdje ćemo vratiti None i obraditi inplace u drugom koraku ili kreirati duplikat
            # Za sada: kreiramo ornament track koji svira samo ukrase
            gen = BassGenerator(self.chord_progression)
            return gen.generate_ornament_layer(base_track=bass_track)
            
        return None

def run_auto_enhance(midi_file_path: str, output_path: str):
    """Glavna funkcija za korisnika: Učitaj -> Enhance -> Sačuvaj."""
    print(f"⏳ Učitavam: {midi_file_path}")
    project = MidiProject.load(midi_file_path)
    
    enhancer = AutoEnhancer(project)
    analysis = enhancer.analyze()
    
    print("\n--- STATUS ARANŽMANA ---")
    print(f"Pronađeno: {', '.join(analysis['found'])}")
    print(f"Fali: {', '.join(analysis['missing']) if analysis['missing'] else 'Ništa'}")
    
    if analysis['missing']:
        enhancer.enhance()
        print("\n✨ Enhancement završen!")
    else:
        print("\n✨ Nije bilo potrebe za enhancementom.")
        
    project.save(output_path)
    print(f"💾 Sačuvano kao: {output_path}")
    print("Gotovo! Tvoj MIDI sada zvuči kao pun bend.")

if __name__ == "__main__":
    # Primjer upotrebe
    # run_auto_enhance("input_simple.mid", "output_full_band.mid")
    pass
