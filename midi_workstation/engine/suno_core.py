"""
Suno for MIDI Core Engine
Pretvara tekstualni prompt u kompletan MIDI aranžman.
"""

import random
import math
from midi_workstation.core.dual_representation import SongSkeleton, Section, Phrase, MusicalNote as NoteEvent
from midi_workstation.core.models import MidiProject, MidiDocument, MidiTrack
from midi_workstation.core.io import MidiWriter

class SunoMIDIEngine:
    def __init__(self):
        self.bpm = 120
        self.key = 'C'
        self.meter = '4/4'
        self.instruments = {}
        
    def generate_from_prompt(self, prompt: str, skeleton: SongSkeleton) -> bytes:
        """Glavna metoda: Prompt -> MIDI bytes"""
        print(f"Analiziram prompt: {prompt}")
        
        # 1. Parsiranje prompta (pojednostavljeno za demo)
        self._parse_prompt(prompt, skeleton)
        
        # 2. Generisanje strukture
        self._build_structure(skeleton)
        
        # 3. Generisanje instrumenata
        project = MidiProject()
        doc = MidiDocument(ppqn=480)
        project.document = doc
        
        # Dodajemo trackove
        self._add_drum_track(doc, skeleton)
        self._add_bass_track(doc, skeleton)
        self._add_chord_track(doc, skeleton) # Piano/Guitar
        self._add_melody_track(doc, skeleton) # Solo/Harmonika
        
        # 4. Export
        writer = MidiWriter()
        return writer.write(project)

    def _parse_prompt(self, prompt: str, skeleton: SongSkeleton):
        """Ekstrahuje BPM, tonalitet i stil iz teksta."""
        prompt_lower = prompt.lower()
        
        if '95 bpm' in prompt_lower:
            skeleton.bpm = 95
        elif '120 bpm' in prompt_lower:
            skeleton.bpm = 120
            
        if 'c minor' in prompt_lower or 'c-moll' in prompt_lower:
            skeleton.key = 'Cm'
        elif 'c major' in prompt_lower:
            skeleton.key = 'C'
            
        # Ovdje bi išla prava NLP analiza za stil
        skeleton.style = "Balkan Folk" if 'balkanska' in prompt_lower else "Pop"

    def _build_structure(self, skeleton: SongSkeleton):
        """Kreira Intro, Verse, Chorus sekcije."""
        if not skeleton.sections:
            # Intro (4 takta)
            intro = Section(name="Intro", start_bar=1, length=4, energy=0.4)
            skeleton.sections.append(intro)
            
            # Verse 1 (16 taktova)
            verse = Section(name="Verse 1", start_bar=5, length=16, energy=0.6)
            skeleton.sections.append(verse)
            
            # Chorus 1 (16 taktova)
            chorus = Section(name="Chorus", start_bar=21, length=16, energy=0.9)
            skeleton.sections.append(chorus)

    def _add_drum_track(self, doc: MidiDocument, skeleton: SongSkeleton):
        """Generiše drum pattern baziran na sekcijama."""
        track = MidiTrack(name="Drums", channel=9)
        doc.add_track(track)
        
        tick = 0
        ppqn = doc.ppqn
        beat_ticks = ppqn * 4  # Cijela nota
        
        # Jednostavan rock/pop pattern za demo
        # Kick na 1 i 3, Snare na 2 i 4, HH osmine
        for bar in range(40): # 40 taktova
            for beat in range(4):
                beat_start = tick + (beat * ppqn)
                
                # Kick (Beat 1 i 3)
                if beat % 2 == 0:
                    track.add_note(36, beat_start, 120, ppqn) # C1
                    
                # Snare (Beat 2 i 4)
                if beat % 2 != 0:
                    track.add_note(38, beat_start, 110, ppqn) # D1
                    
                # Hi-Hat (svaka osmina)
                track.add_note(42, beat_start, 90, ppqn // 2) # F#1
                track.add_note(42, beat_start + (ppqn // 2), 85, ppqn // 2)
                
            tick += beat_ticks

    def _add_bass_track(self, doc: MidiDocument, skeleton: SongSkeleton):
        """Generiše bass liniju prema akordima."""
        track = MidiTrack(name="Bass", channel=1, program=33) # Finger Bass
        doc.add_track(track)
        
        tick = 0
        ppqn = doc.ppqn
        beat_ticks = ppqn * 4
        
        # Root note za Cm je C1 (36)
        root_note = 36 
        
        for bar in range(40):
            # Jednostavan pattern: Root na 1, Fifth na 3
            track.add_note(root_note, tick, 100, ppqn) # C
            track.add_note(root_note + 7, tick + (2 * ppqn), 95, ppqn) # G
            
            # Osine između
            track.add_note(root_note, tick + ppqn, 80, ppqn // 2)
            track.add_note(root_note + 7, tick + (3 * ppqn), 80, ppqn // 2)
            
            tick += beat_ticks

    def _add_chord_track(self, doc: MidiDocument, skeleton: SongSkeleton):
        """Generiše pratnju (Piano/Guitar)."""
        track = MidiTrack(name="Accompaniment", channel=2, program=0) # Piano
        doc.add_track(track)
        
        tick = 0
        ppqn = doc.ppqn
        beat_ticks = ppqn * 4
        
        # Cm akord: C3, Eb3, G3
        chord_notes = [48, 51, 55] 
        
        for bar in range(40):
            # Blok akordi na svaku četvrtinu u refrenu, polovine u strofi
            # Za demo: sviramo cijele note ili polovine
            duration = beat_ticks # Cijeli takt
            
            # Arpeggio ili blok? Idemo na blok za sada
            for note in chord_notes:
                track.add_note(note, tick, 85, duration)
                
            tick += beat_ticks

    def _add_melody_track(self, doc: MidiDocument, skeleton: SongSkeleton):
        """Generiše jednostavnu melodiju (Harmonika/Solo)."""
        track = MidiTrack(name="Solo", channel=3, program=21) # Accordion
        doc.add_track(track)
        
        tick = 0
        ppqn = doc.ppqn
        
        # Jednostavna motivska melodija u C-molu
        # C, Eb, F, G, Ab, Bb
        melody_seq = [
            (48, 1), (51, 1), (53, 2), # C, Eb, F
            (55, 1), (56, 1), (58, 2), # G, Ab, Bb
            (60, 4) # C (visoki)
        ]
        
        # Ponavljamo motiv kroz 4 takta introa pa dalje
        current_tick = ppqn * 4 # Počinjemo nakon introa bubnjeva možda? Ne, od početka
        
        for repeat in range(10):
            for note, beats in melody_seq:
                duration = int(beats * ppqn)
                track.add_note(note, current_tick, 95 + (repeat * 2), duration)
                current_tick += duration
                
            # Pauza između fraza
            current_tick += ppqn 
