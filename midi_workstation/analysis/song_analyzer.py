"""
Song Intelligence Model - Temelj za Autonomous Rebuilder
Analizira cijelu pjesmu prije bilo kakve izmjene
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ChordSegment:
    """Detektovani akord sa vremenskim granicama"""
    start_tick: int
    end_tick: int
    root: str
    quality: str
    inversion: Optional[int] = None
    confidence: float = 0.0
    bass_note: Optional[int] = None
    

@dataclass
class SectionInfo:
    """Informacije o sekciji pjesme"""
    name: str
    start_tick: int
    end_tick: int
    start_measure: int
    end_measure: int
    chord_progression: List[ChordSegment] = field(default_factory=list)
    density: float = 0.0
    instruments: List[str] = field(default_factory=list)
    

@dataclass
class PhraseInfo:
    """Informacije o frazi"""
    start_tick: int
    end_tick: int
    phrase_type: str
    motif_signature: Optional[str] = None
    

@dataclass 
class SongMap:
    """Kompletna mapa pjesme"""
    tempo_map: Dict[int, float] = field(default_factory=dict)
    meter_map: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    key_estimate: Optional[str] = None
    chords: List[ChordSegment] = field(default_factory=list)
    sections: List[SectionInfo] = field(default_factory=list)
    phrases: List[PhraseInfo] = field(default_factory=list)
    harmonic_rhythm: float = 0.0
    has_pickup: bool = False
    modulation_points: List[int] = field(default_factory=list)


class ChordInferenceEngine:
    """
    Napredni engine za detekciju akorda
    Koristi note simultaneity, bass note, context
    """
    
    CHORD_QUALITIES = [
        'major', 'minor', 'dominant7', 'major7', 'minor7',
        'diminished', 'augmented', 'sus2', 'sus4', 
        'sixth', 'minor6', 'major9', 'minor9', 'dominant9'
    ]
    
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def __init__(self):
        self.chroma_profiles = self._build_chroma_profiles()
        
    def _build_chroma_profiles(self) -> Dict[str, List[int]]:
        """Gradi profile za različite tipove akorda"""
        profiles = {}
        profiles['C_major'] = [0, 4, 7]
        profiles['C_minor'] = [0, 3, 7]
        profiles['C_dominant7'] = [0, 4, 7, 10]
        profiles['C_major7'] = [0, 4, 7, 11]
        profiles['C_minor7'] = [0, 3, 7, 10]
        profiles['C_diminished'] = [0, 3, 6]
        profiles['C_augmented'] = [0, 4, 8]
        profiles['C_sus2'] = [0, 2, 7]
        profiles['C_sus4'] = [0, 5, 7]
        profiles['C_sixth'] = [0, 4, 7, 9]
        profiles['C_minor6'] = [0, 3, 7, 9]
        return profiles
        
    def midi_to_pitch_class(self, midi_note: int) -> int:
        return midi_note % 12
        
    def detect_chord_from_notes(self, notes: List[Dict], 
                                 bass_note: Optional[int] = None) -> Optional[ChordSegment]:
        if not notes:
            return None
            
        pitch_classes = defaultdict(int)
        for note in notes:
            pc = self.midi_to_pitch_class(note['pitch'])
            pitch_classes[pc] += 1
            
        active_pcs = sorted(pitch_classes.keys())
        if len(active_pcs) < 2:
            return None
            
        best_match = None
        best_score = 0.0
        
        for root_pc in range(12):
            for quality, intervals in self.chroma_profiles.items():
                transposed = [(root_pc + interval) % 12 for interval in intervals]
                match_count = sum(1 for pc in transposed if pc in active_pcs)
                mismatch_count = sum(1 for pc in active_pcs if pc not in transposed)
                
                score = match_count / len(transposed) if transposed else 0
                score -= mismatch_count * 0.1
                
                if score > best_score and score > 0.6:
                    best_score = score
                    quality_name = quality.replace('C_', '')
                    root_name = self.NOTE_NAMES[root_pc]
                    best_match = (root_name, quality_name, score)
                    
        if best_match:
            root, quality, confidence = best_match
            inversion = None
            if bass_note is not None:
                bass_pc = self.midi_to_pitch_class(bass_note)
                try:
                    root_pc = self.NOTE_NAMES.index(root)
                    if bass_pc != root_pc:
                        if quality in ['major', 'minor']:
                            thirds = {0: 0, 1: 4 if quality == 'major' else 3, 2: 7}
                            for inv, interval in thirds.items():
                                if bass_pc == (root_pc + interval) % 12:
                                    inversion = inv
                                    break
                except ValueError:
                    pass
                    
            return ChordSegment(
                start_tick=min(n['start_tick'] for n in notes),
                end_tick=max(n['end_tick'] for n in notes),
                root=root,
                quality=quality,
                inversion=inversion,
                confidence=confidence,
                bass_note=bass_note
            )
            
        return None


class SectionAnalyzer:
    """Automatska detekcija sekcija pjesme"""
    
    SECTION_PATTERNS = {
        'Intro': {'density_range': (0.0, 0.6), 'typical_length_bars': (4, 8)},
        'Verse': {'density_range': (0.4, 0.7), 'typical_length_bars': (8, 16)},
        'Pre-Chorus': {'density_range': (0.5, 0.8), 'typical_length_bars': (4, 8)},
        'Chorus': {'density_range': (0.7, 1.0), 'typical_length_bars': (8, 16)},
        'Bridge': {'density_range': (0.5, 0.8), 'typical_length_bars': (8, 16)},
        'Solo': {'density_range': (0.6, 0.9), 'typical_length_bars': (8, 16)},
        'Outro': {'density_range': (0.0, 0.6), 'typical_length_bars': (4, 8)},
    }
    
    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat
        self.ticks_per_bar = ticks_per_beat * 4
        
    def calculate_density(self, events: List[Dict], 
                         start_tick: int, end_tick: int) -> float:
        if start_tick >= end_tick:
            return 0.0
        note_count = sum(1 for e in events 
                        if e.get('type') == 'note_on' 
                        and start_tick <= e.get('tick', 0) < end_tick)
        duration_bars = (end_tick - start_tick) / self.ticks_per_bar
        if duration_bars <= 0:
            return 0.0
        return min(1.0, note_count / (duration_bars * 16))
        
    def detect_repetition(self, events: List[Dict], 
                         segment1_start: int, segment1_end: int,
                         segment2_start: int, segment2_end: int) -> float:
        seg1_notes = [e for e in events 
                     if e.get('type') == 'note_on' 
                     and segment1_start <= e.get('tick', 0) < segment1_end]
        seg2_notes = [e for e in events 
                     if e.get('type') == 'note_on' 
                     and segment2_start <= e.get('tick', 0) < segment2_end]
        
        if not seg1_notes or not seg2_notes:
            return 0.0
            
        def get_pattern(notes, start_tick):
            pattern = []
            for note in notes:
                relative_tick = (note['tick'] - start_tick) % self.ticks_per_bar
                relative_pitch = note['pitch'] % 12
                pattern.append((relative_tick // 120, relative_pitch))
            return sorted(pattern)
            
        pattern1 = get_pattern(seg1_notes, segment1_start)
        pattern2 = get_pattern(seg2_notes, segment2_start)
        
        common = len(set(pattern1) & set(pattern2))
        total = len(set(pattern1) | set(pattern2))
        
        return common / total if total > 0 else 0.0
        
    def analyze_sections(self, events: List[Dict], 
                        total_ticks: int) -> List[SectionInfo]:
        sections = []
        segment_size = self.ticks_per_bar * 8
        num_segments = max(1, int(total_ticks / segment_size))
        
        segment_densities = []
        for i in range(num_segments):
            start = i * segment_size
            end = min((i + 1) * segment_size, total_ticks)
            density = self.calculate_density(events, start, end)
            segment_densities.append(density)
            
        section_boundaries = [0]
        for i in range(1, len(segment_densities)):
            if abs(segment_densities[i] - segment_densities[i-1]) > 0.3:
                section_boundaries.append(i * segment_size)
        section_boundaries.append(total_ticks)
        
        for i in range(len(section_boundaries) - 1):
            start = section_boundaries[i]
            end = section_boundaries[i + 1]
            
            if end <= start:
                continue
                
            density = self.calculate_density(events, start, end)
            start_measure = int(start / self.ticks_per_bar) + 1
            end_measure = int(end / self.ticks_per_bar) + 1
            
            section_type = 'Verse'
            
            if i == 0 and density < 0.5:
                section_type = 'Intro'
            elif i == len(section_boundaries) - 2 and density < 0.5:
                section_type = 'Outro'
            elif density > 0.75:
                section_type = 'Chorus'
            elif density > 0.6 and i > 0:
                if i > 0 and self.detect_repetition(events, 
                                                    section_boundaries[i-1], section_boundaries[i],
                                                    start, end) > 0.7:
                    section_type = 'Chorus'
                else:
                    section_type = 'Pre-Chorus'
                    
            sections.append(SectionInfo(
                name=section_type,
                start_tick=start,
                end_tick=end,
                start_measure=start_measure,
                end_measure=end_measure,
                density=density
            ))
            
        return sections


class SongAnalyzer:
    """Glavni analyzer koji koordinira sve pod-analizere"""
    
    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat
        self.chord_engine = ChordInferenceEngine()
        self.section_analyzer = SectionAnalyzer(ticks_per_beat)
        
    def extract_tempo_map(self, events: List[Dict]) -> Dict[int, float]:
        tempo_map = {}
        for event in sorted(events, key=lambda x: x.get('tick', 0)):
            if event.get('type') == 'set_tempo':
                tick = event.get('tick', 0)
                microseconds_per_beat = event.get('tempo', 500000)
                bpm = 60000000 / microseconds_per_beat
                tempo_map[tick] = round(bpm, 2)
        if not tempo_map:
            tempo_map[0] = 120.0
        return tempo_map
        
    def extract_meter_map(self, events: List[Dict]) -> Dict[int, Tuple[int, int]]:
        meter_map = {}
        for event in sorted(events, key=lambda x: x.get('tick', 0)):
            if event.get('type') == 'time_signature':
                tick = event.get('tick', 0)
                numerator = event.get('numerator', 4)
                denominator = event.get('denominator', 4)
                meter_map[tick] = (numerator, denominator)
        if not meter_map:
            meter_map[0] = (4, 4)
        return meter_map
        
    def estimate_key(self, events: List[Dict]) -> Optional[str]:
        pitch_histogram = defaultdict(float)
        for event in events:
            if event.get('type') == 'note_on':
                pitch = event.get('pitch', 0)
                duration = event.get('duration', 0)
                pc = pitch % 12
                pitch_histogram[pc] += duration + 1
        
        if not pitch_histogram:
            return None
            
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        
        best_key = None
        best_score = -1
        
        for root in range(12):
            rotated_major = [major_profile[(i - root) % 12] for i in range(12)]
            rotated_minor = [minor_profile[(i - root) % 12] for i in range(12)]
            
            hist_values = [pitch_histogram.get(i, 0) for i in range(12)]
            
            major_corr = sum(h * p for h, p in zip(hist_values, rotated_major))
            minor_corr = sum(h * p for h, p in zip(hist_values, rotated_minor))
            
            if major_corr > best_score:
                best_score = major_corr
                best_key = f"{self.chord_engine.NOTE_NAMES[root]} major"
                
            if minor_corr > best_score:
                best_score = minor_corr
                best_key = f"{self.chord_engine.NOTE_NAMES[root]} minor"
                
        return best_key
        
    def analyze(self, midi_events: List[Dict], total_ticks: int) -> SongMap:
        sorted_events = sorted(midi_events, key=lambda x: x.get('tick', 0))
        
        tempo_map = self.extract_tempo_map(sorted_events)
        meter_map = self.extract_meter_map(sorted_events)
        key_estimate = self.estimate_key(sorted_events)
        
        chords = []
        window_size = self.ticks_per_beat * 2
        
        for start in range(0, total_ticks, window_size):
            end = min(start + window_size, total_ticks)
            
            window_notes = []
            for event in sorted_events:
                if event.get('type') == 'note_on':
                    tick = event.get('tick', 0)
                    if start <= tick < end:
                        window_notes.append({
                            'pitch': event.get('pitch', 0),
                            'start_tick': tick,
                            'end_tick': tick + event.get('duration', 0)
                        })
                        
            if len(window_notes) >= 2:
                chord = self.chord_engine.detect_chord_from_notes(window_notes)
                if chord:
                    chord.start_tick = start
                    chord.end_tick = end
                    chords.append(chord)
                    
        sections = self.section_analyzer.analyze_sections(sorted_events, total_ticks)
        
        harmonic_rhythm = 0.0
        if len(chords) > 1 and len(sections) > 0:
            total_bars = total_ticks / (self.ticks_per_beat * 4)
            harmonic_rhythm = len(chords) / max(1, total_bars)
            
        has_pickup = False
        if chords and chords[0].start_tick > 0:
            first_bar_ticks = self.ticks_per_beat * 4
            if chords[0].start_tick < first_bar_ticks * 0.5:
                has_pickup = True
                
        return SongMap(
            tempo_map=tempo_map,
            meter_map=meter_map,
            key_estimate=key_estimate,
            chords=chords,
            sections=sections,
            harmonic_rhythm=harmonic_rhythm,
            has_pickup=has_pickup
        )


def test_song_analyzer():
    test_events = [
        {'type': 'time_signature', 'tick': 0, 'numerator': 4, 'denominator': 4},
        {'type': 'set_tempo', 'tick': 0, 'tempo': 500000},
        {'type': 'note_on', 'tick': 0, 'pitch': 60, 'duration': 480},
        {'type': 'note_on', 'tick': 0, 'pitch': 64, 'duration': 480},
        {'type': 'note_on', 'tick': 0, 'pitch': 67, 'duration': 480},
        {'type': 'note_on', 'tick': 480, 'pitch': 60, 'duration': 480},
        {'type': 'note_on', 'tick': 960, 'pitch': 62, 'duration': 480},
        {'type': 'note_on', 'tick': 960, 'pitch': 65, 'duration': 480},
        {'type': 'note_on', 'tick': 960, 'pitch': 69, 'duration': 480},
    ]
    
    analyzer = SongAnalyzer(ticks_per_beat=480)
    song_map = analyzer.analyze(test_events, total_ticks=1920)
    
    print("=== SONG ANALYSIS TEST ===")
    print(f"Tonalitet: {song_map.key_estimate}")
    print(f"Tempo map: {song_map.tempo_map}")
    print(f"Meter map: {song_map.meter_map}")
    print(f"Detektovani akordi: {len(song_map.chords)}")
    for chord in song_map.chords:
        print(f"  - {chord.root}{chord.quality} (confidence: {chord.confidence:.2f})")
    print(f"Sekcije: {len(song_map.sections)}")
    for section in song_map.sections:
        print(f"  - {section.name} (bars {section.start_measure}-{section.end_measure}, density: {section.density:.2f})")
    print(f"Harmonic rhythm: {song_map.harmonic_rhythm:.2f} chords/bar")
    print(f"Has pickup: {song_map.has_pickup}")
    
    return song_map


if __name__ == "__main__":
    test_song_analyzer()
