"""
SONG SKELETON ENGINE
--------------------
Analizira MIDI dokument i gradi hijerarhijsku strukturu:
Song -> Section -> Phrase -> Motif -> Note.
Detektuje sekcije, fraze, akorde i energiju pjesme.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from midi_workstation.core.skeleton_models import (
    SongSkeleton, Section, Phrase, Motif, MusicalNote, 
    SectionType, InstrumentRole, TrackAnalysis
)
from midi_workstation.core.models import MidiProject, MidiDocument, MidiTrack, NoteEvent

class SongSkeletonEngine:
    """Glavni engine za izgradnju Song Skeleton-a."""
    
    def __init__(self, ppqn: int = 480):
        self.ppqn = ppqn
        
    def build_skeleton(self, project: MidiProject) -> SongSkeleton:
        """Gradi kompletnu strukturu pjesme iz MIDI projekta."""
        doc = project.document
        self.ppqn = getattr(doc, "ppqn", 480)
        
        # 1. Ekstrakcija Tempo i Time Signature mapa
        tempo_map = self._extract_tempo_map(doc)
        time_sig_map = self._extract_time_sig_map(doc)
        
        # 2. Detekcija Sekcija (Intro, Verse, Chorus...)
        sections = self._detect_sections(doc, tempo_map, time_sig_map)
        
        # 3. Popunjavanje Fraza unutar Sekcija
        for section in sections:
            section.phrases = self._detect_phrases(section, doc, tempo_map)
            section.avg_energy = self._calculate_section_energy(section)
            
        # 4. Izračun trajanja
        total_ticks = max([track.get_absolute_tick_max() for track in doc.tracks]) if doc.tracks else 0
        duration_sec = self._ticks_to_seconds(total_ticks, tempo_map)
        
        return SongSkeleton(
            sections=sections,
            tempo_map=tempo_map,
            time_sig_map=time_sig_map,
            total_ticks=total_ticks,
            duration_seconds=duration_sec
        )
    
    def _extract_tempo_map(self, doc: MidiDocument) -> Dict[int, float]:
        """Ekstrahuje promjene tempa (tick -> BPM)."""
        tempo_map = {}
        current_bpm = 120.0
        
        # Pretraži sve trackove za Tempo evente
        for track in doc.tracks:
            for event in track.events:
                etype = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
                if etype in ("tempo", "set_tempo"):
                    if getattr(event, "tempo_bpm", None):
                        current_bpm = event.tempo_bpm
                    elif getattr(event, "tempo", None):
                        current_bpm = 60000000 / event.tempo
                    tempo_map[event.absolute_tick] = current_bpm
                    
        if not tempo_map:
            tempo_map[0] = 120.0
            
        return tempo_map
    
    def _extract_time_sig_map(self, doc: MidiDocument) -> Dict[int, Tuple[int, int]]:
        """Ekstrahuje promjene metra (tick -> (numerator, denominator))."""
        time_sig_map = {}
        
        for track in doc.tracks:
            for event in track.events:
                etype = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
                if etype in ("time_signature",):
                    if hasattr(event, 'numerator') and hasattr(event, 'denominator'):
                        time_sig_map[event.absolute_tick] = (event.numerator, event.denominator)
                        
        if not time_sig_map:
            time_sig_map[0] = (4, 4)
            
        return time_sig_map
    
    def _detect_sections(self, doc: MidiDocument, tempo_map: Dict, time_sig_map: Dict) -> List[Section]:
        """
        Detektuje sekcije pjesme na osnovu:
        - Promjena u gustini nota (density)
        - Promjena u instrumentaciji
        - Marker eventa (ako postoje)
        - Repetitivnih patterna
        """
        sections = []
        total_ticks = max([track.get_absolute_tick_max() for track in doc.tracks]) if doc.tracks else 0
        
        # Heuristika: Dijelimo pjesmu na segmente od 8 taktova i tražimo promjene
        # Ovo je pojednostavljeno - prava implementacija koristi ML ili složeniju analizu
        beats_per_bar = 4  # Default, treba čitati iz time_sig_map
        ticks_per_beat = self.ppqn
        ticks_per_bar = beats_per_bar * ticks_per_beat
        
        current_pos = 0
        section_id = 0
        
        # Ako postoje markeri, koristimo njih
        markers = self._extract_markers(doc)
        
        if markers:
            # Kreiraj sekcije bazirane na markerima
            for i, marker in enumerate(markers):
                start_tick = marker['tick']
                end_tick = markers[i+1]['tick'] if i+1 < len(markers) else total_ticks
                
                sec_type = self._marker_to_section_type(marker['name'])
                sections.append(Section(
                    type=sec_type,
                    phrases=[],
                    start_tick=start_tick,
                    end_tick=end_tick
                ))
        else:
            # Fallback: Automatska detekcija bazirana na energiji/gustini
            # Grupišemo u blokove od 16 taktova
            block_size = 16 * ticks_per_bar
            
            while current_pos < total_ticks:
                end_pos = min(current_pos + block_size, total_ticks)
                
                # Analiza energije u ovom bloku
                energy = self._calculate_block_energy(doc, current_pos, end_pos)
                
                # Jednostavna logika za primjer
                if section_id == 0:
                    sec_type = SectionType.INTRO if energy < 0.4 else SectionType.VERSE
                elif section_id % 4 == 0:
                    sec_type = SectionType.CHORUS
                elif section_id % 4 == 2:
                    sec_type = SectionType.VERSE
                else:
                    sec_type = SectionType.UNKNOWN
                
                sections.append(Section(
                    type=sec_type,
                    phrases=[],
                    start_tick=current_pos,
                    end_tick=end_pos,
                    avg_energy=energy
                ))
                
                current_pos = end_pos
                section_id += 1
                
        return sections
    
    def _extract_markers(self, doc: MidiDocument) -> List[Dict]:
        """Vadi marker evente iz MIDI-a."""
        markers = []
        for track in doc.tracks:
            for event in track.events:
                if hasattr(event, 'event_type') and event.event_type == 'marker':
                    if hasattr(event, 'text'):
                        markers.append({
                            'tick': event.absolute_tick,
                            'name': event.text
                        })
        return sorted(markers, key=lambda x: x['tick'])
    
    def _marker_to_section_type(self, name: str) -> SectionType:
        """Mapira ime markera u tip sekcije."""
        name_upper = name.upper()
        if "INTRO" in name_upper: return SectionType.INTRO
        if "VERSE" in name_upper: return SectionType.VERSE
        if "CHORUS" in name_upper or "REFREN" in name_upper: return SectionType.CHORUS
        if "BRIDGE" in name_upper: return SectionType.BRIDGE
        if "SOLO" in name_upper: return SectionType.SOLO
        if "OUTRO" in name_upper or "END" in name_upper: return SectionType.OUTRO
        if "FILL" in name_upper: return SectionType.FILL
        return SectionType.UNKNOWN
    
    def _detect_phrases(self, section: Section, doc: MidiDocument, tempo_map: Dict) -> List[Phrase]:
        """Dijeli sekciju na fraze (obično 4 takta)."""
        phrases = []
        ticks_per_bar = 4 * self.ppqn  # Pojednostavljeno za 4/4
        phrase_length = 4 * ticks_per_bar  # 4 takta po frazi
        
        current_pos = section.start_tick
        while current_pos < section.end_tick:
            end_pos = min(current_pos + phrase_length, section.end_tick)
            
            # Ekstrahuj note u ovoj frazi iz svih trackova
            all_notes = self._extract_notes_in_range(doc, current_pos, end_pos)
            
            if all_notes:
                # Podijeli na motive (1 takt)
                motifs = self._create_motifs(all_notes, current_pos, ticks_per_bar)
                
                density = len(all_notes) / (phrase_length / (self.ppqn * 4)) # note po beatu
                energy = self._calculate_phrase_energy(all_notes)
                
                phrases.append(Phrase(
                    motifs=motifs,
                    start_tick=current_pos,
                    end_tick=end_pos,
                    density=density,
                    energy=energy
                ))
            
            current_pos = end_pos
            
        return phrases
    
    def _create_motifs(self, notes: List[MusicalNote], start_tick: int, bar_length: int) -> List[Motif]:
        """Grupiše note u motive (1 takt)."""
        motifs = []
        current_bar_start = start_tick
        
        # Grupiši note po taktovima
        bar_notes = {}
        for note in notes:
            bar_idx = int((note.start_tick - start_tick) / bar_length)
            if bar_idx not in bar_notes:
                bar_notes[bar_idx] = []
            bar_notes[bar_idx].append(note)
            
        for bar_idx in sorted(bar_notes.keys()):
            bar_start = start_tick + (bar_idx * bar_length)
            bar_end = bar_start + bar_length
            bar_note_list = bar_notes[bar_idx]
            
            if bar_note_list:
                motifs.append(Motif(
                    notes=bar_note_list,
                    start_tick=bar_start,
                    end_tick=bar_end,
                    fingerprint="" # TODO: Implementirati fingerprinting
                ))
                
        return motifs
    
    def _extract_notes_in_range(self, doc: MidiDocument, start_tick: int, end_tick: int) -> List[MusicalNote]:
        """Vraća sve note u određenom opsegu tickova."""
        notes = []
        for track_idx, track in enumerate(doc.tracks):
            for event in track.events:
                etype = event.event_type.value if hasattr(event.event_type, "value") else str(getattr(event, "event_type", ""))
                is_note = etype in ("note_on",) or (isinstance(event, NoteEvent) and etype != "note_off")
                if is_note and getattr(event, "note", None) is not None:
                    if start_tick <= event.absolute_tick < end_tick:
                        notes.append(MusicalNote(
                            pitch=event.note if event.note is not None else getattr(event, "pitch", 0),
                            velocity=event.velocity,
                            start_tick=event.absolute_tick,
                            duration_ticks=getattr(event, "duration_ticks", None) or getattr(event, "duration", 0) or 0,
                            channel=event.channel,
                            track_index=track_idx
                        ))
        return notes
    
    def _calculate_block_energy(self, doc: MidiDocument, start: int, end: int) -> float:
        """Računa prosječnu energiju (velocity * density) u bloku."""
        notes = self._extract_notes_in_range(doc, start, end)
        if not notes:
            return 0.0
        avg_vel = sum(n.velocity for n in notes) / len(notes)
        density = min(1.0, len(notes) / ((end - start) / (self.ppqn * 4))) # Normalizovano
        return (avg_vel / 127.0) * density
    
    def _calculate_phrase_energy(self, notes: List[MusicalNote]) -> float:
        """Računa energiju fraze."""
        if not notes:
            return 0.0
        avg_vel = sum(n.velocity for n in notes) / len(notes)
        return avg_vel / 127.0
    
    def _calculate_section_energy(self, section: Section) -> float:
        """Prosječna energija sekcije bazirana na frazama."""
        if not section.phrases:
            return 0.0
        return sum(p.energy for p in section.phrases) / len(section.phrases)
    
    def _ticks_to_seconds(self, ticks: int, tempo_map: Dict[int, float]) -> float:
        """Konvertuje tickove u sekunde koristeći tempo mapu."""
        # Pojednostavljena konverzija (pretpostavlja konstantan tempo ako nema promjena)
        bpm = list(tempo_map.values())[0] if tempo_map else 120.0
        seconds_per_tick = (60.0 / bpm) / self.ppqn
        return ticks * seconds_per_tick
