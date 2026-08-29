"""
MIDI Velocity Optimizer & Auto Audio Engineer
Aplikacija za obrada MIDI fajlova sa naprednim auto-optimizacijom zvuka
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass, asdict
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QLineEdit, QTextEdit, QProgressBar,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QScrollArea, QStatusBar, QSplitter, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QIcon, QColor, QFont

import mido
from mido import MidiFile, MidiTrack, Message
import numpy as np
from dataclasses import field


class InstrumentType(Enum):
    """Tipovi instrumenata za detekciju"""
    BASS = "bass"
    GUITAR = "guitar"
    DRUMS = "drums"
    VOCAL = "vocal"
    STRINGS = "strings"
    KEYS = "keys"
    UNKNOWN = "unknown"


@dataclass
class VelocityPreset:
    """Preset za brzinu"""
    min_vel: int = 30
    max_vel: int = 110
    default_vel: int = 80


@dataclass
class InstrumentConfig:
    """Konfiguracija za instrument"""
    name: str
    instrument_type: InstrumentType
    program_change: int
    min_vel: int = 40
    max_vel: int = 110
    key_range: Tuple[int, int] = (0, 127)
    articulations: List[str] = field(default_factory=list)
    use_rx_enhancement: bool = True
    use_dnc: bool = True
    delay_type: Optional[str] = None
    delay_amount: float = 0.0
    background_reduction: float = 35.0
    is_solo: bool = False
    is_delay_track: bool = False


@dataclass
class TrackAnalysis:
    """Analiza trakta"""
    track_num: int
    track_name: str
    instrument_type: InstrumentType
    program_change: Optional[int]
    note_range: Tuple[int, int]
    velocity_range: Tuple[int, int]
    has_solo_section: bool
    solo_sections: List[Tuple[int, int]]
    has_delay: bool
    delay_start: Optional[int]
    total_notes: int
    duration_ticks: int
    is_third_of_solo: bool


class MIDIAnalyzer:
    """Analizira MIDI fajlove"""
    
    # Mapiranje Program Change -> Tip instrumenta
    PC_TO_INSTRUMENT = {
        # Bass
        range(32, 40): InstrumentType.BASS,
        # Guitar
        range(24, 32): InstrumentType.GUITAR,
        # Drums (obicno na kanalu 10)
        range(0, 128): InstrumentType.DRUMS,
        # Strings
        range(48, 56): InstrumentType.STRINGS,
        # Keys
        range(0, 8): InstrumentType.KEYS,
    }
    
    # Kljucne reci za detekciju
    INSTRUMENT_KEYWORDS = {
        InstrumentType.BASS: ["bass", "b1", "b2"],
        InstrumentType.GUITAR: ["guitar", "gtr", "g1", "g2", "rhythm"],
        InstrumentType.DRUMS: ["drum", "kit", "perc", "percussion"],
        InstrumentType.VOCAL: ["vocal", "voice", "lead", "choir"],
        InstrumentType.STRINGS: ["string", "violin", "cello"],
    }
    
    SOLO_KEYWORDS = ["solo", "lead", "fill"]
    DELAY_KEYWORDS = ["delay", "echo", "reverb"]
    
    def __init__(self):
        self.midi_file: Optional[MidiFile] = None
        self.analyses: Dict[int, TrackAnalysis] = {}
        
    def load_midi(self, filepath: str) -> bool:
        """Ucitaj MIDI fajl"""
        try:
            self.midi_file = MidiFile(filepath)
            return True
        except Exception as e:
            print(f"Greska pri ucitavanju: {e}")
            return False
    
    def detect_program_change(self, track: MidiTrack) -> Optional[int]:
        """Detektuj program change na pocetku ili blizu pocetka"""
        for msg in track:
            if msg.type == 'program_change':
                return msg.program
            if msg.type == 'note_on' and msg.time > 1000:
                # Prestani pretragu posle prvog note_on
                break
        return None
    
    def analyze_track(self, track_idx: int) -> TrackAnalysis:
        """Detaljno analiziraj jedan trak"""
        if self.midi_file is None:
            raise ValueError("MIDI fajl nije ucitan")
        
        track = self.midi_file.tracks[track_idx]
        
        # Osnovne informacije
        track_name = track.name if hasattr(track, 'name') else f"Track {track_idx}"
        program_change = self.detect_program_change(track)
        
        # Analiza nota
        note_range = [127, 0]
        velocity_range = [127, 0]
        notes = []
        solo_sections = []
        total_duration = 0
        total_notes = 0
        
        current_time = 0
        for msg in track:
            current_time += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                total_notes += 1
                notes.append(msg.note)
                note_range[0] = min(note_range[0], msg.note)
                note_range[1] = max(note_range[1], msg.note)
                velocity_range[0] = min(velocity_range[0], msg.velocity)
                velocity_range[1] = max(velocity_range[1], msg.velocity)
        
        total_duration = current_time
        
        # Detekcija instrumenta
        instrument_type = self._detect_instrument(track_name, program_change, track)
        
        # Detekcija solo sekcija
        has_solo = any(kw in track_name.lower() for kw in self.SOLO_KEYWORDS)
        has_delay = any(kw in track_name.lower() for kw in self.DELAY_KEYWORDS)
        
        analysis = TrackAnalysis(
            track_num=track_idx,
            track_name=track_name,
            instrument_type=instrument_type,
            program_change=program_change,
            note_range=tuple(note_range),
            velocity_range=tuple(velocity_range),
            has_solo_section=has_solo,
            solo_sections=solo_sections,
            has_delay=has_delay,
            delay_start=None,
            total_notes=total_notes,
            duration_ticks=total_duration,
            is_third_of_solo=False
        )
        
        self.analyses[track_idx] = analysis
        return analysis
    
    def _detect_instrument(self, track_name: str, program_change: Optional[int], 
                          track: MidiTrack) -> InstrumentType:
        """Detektuj tip instrumenta"""
        track_lower = track_name.lower()
        
        # Prvo proveri kljucne reci
        for inst_type, keywords in self.INSTRUMENT_KEYWORDS.items():
            if any(kw in track_lower for kw in keywords):
                return inst_type
        
        # Ako je kanal 10 (MIDI drums)
        for msg in track:
            if msg.type == 'note_on' and msg.channel == 9:
                return InstrumentType.DRUMS
        
        # Proveri program change
        if program_change is not None:
            if 32 <= program_change < 40:
                return InstrumentType.BASS
            elif 24 <= program_change < 32:
                return InstrumentType.GUITAR
            elif 48 <= program_change < 56:
                return InstrumentType.STRINGS
            elif 0 <= program_change < 8:
                return InstrumentType.KEYS
        
        return InstrumentType.UNKNOWN
    
    def analyze_all_tracks(self) -> Dict[int, TrackAnalysis]:
        """Analiziraj sve trakove"""
        if self.midi_file is None:
            return {}
        
        for i in range(len(self.midi_file.tracks)):
            self.analyze_track(i)
        
        # Detektuj trece trakove
        self._detect_third_tracks()
        
        return self.analyses
    
    def _detect_third_tracks(self):
        """Detektuj trakove koji su terce od solo trakova"""
        solo_analyses = [a for a in self.analyses.values() if a.has_solo_section]
        
        for solo in solo_analyses:
            for other_idx, other_analysis in self.analyses.items():
                if other_idx != solo.track_num:
                    # Proveri da li je tercija
                    if self._is_third(solo.note_range, other_analysis.note_range):
                        other_analysis.is_third_of_solo = True
    
    def _is_third(self, note_range1: Tuple[int, int], 
                  note_range2: Tuple[int, int]) -> bool:
        """Proveri da li je nota tercija"""
        center1 = (note_range1[0] + note_range1[1]) / 2
        center2 = (note_range2[0] + note_range2[1]) / 2
        
        # Tercija je oko 4 semitona
        diff = abs(center1 - center2)
        return 3 <= diff <= 5


class BassEngine:
    """Engine za optimizaciju Bass zvuka"""
    
    def __init__(self):
        self.config = InstrumentConfig(
            name="Bass",
            instrument_type=InstrumentType.BASS,
            program_change=33,
            min_vel=50,
            max_vel=110,
            key_range=(24, 60),
            articulations=["sustain", "accent", "muted", "slap"],
            use_rx_enhancement=True,
            use_dnc=True
        )
    
    def optimize(self, track: MidiTrack) -> MidiTrack:
        """Optimizuj bass track"""
        optimized = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # Prilagodi brzinu
                msg.velocity = self._optimize_velocity(msg.velocity)
                
                # Proveri kljucni opseg
                if self.config.key_range[0] <= msg.note <= self.config.key_range[1]:
                    # Dodaj subtle akcentuaciju
                    if msg.velocity > 90:
                        msg.velocity = min(110, msg.velocity + 5)
            
            optimized.append(msg)
        
        return optimized
    
    def _optimize_velocity(self, velocity: int) -> int:
        """Normalizuj brzinu u bass opsegu"""
        if velocity < self.config.min_vel:
            return self.config.min_vel
        elif velocity > self.config.max_vel:
            return self.config.max_vel
        return velocity


class GuitarEngine:
    """Engine za optimizaciju Guitar zvuka"""
    
    def __init__(self):
        self.config = InstrumentConfig(
            name="Guitar",
            instrument_type=InstrumentType.GUITAR,
            program_change=25,
            min_vel=40,
            max_vel=110,
            key_range=(40, 84),
            articulations=["pick", "muted", "palm_mute", "harmonic", "bend"],
            use_rx_enhancement=True,
            use_dnc=True
        )
    
    def add_strumming_pattern(self, track: MidiTrack) -> MidiTrack:
        """Dodaj Chak Chak Strummer efekat"""
        optimized = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                msg.velocity = self._optimize_velocity(msg.velocity)
                
                # Simuliraj strumming sa varijacijom
                if msg.velocity > 80:
                    msg.velocity = min(110, msg.velocity + 3)
            
            optimized.append(msg)
        
        return optimized
    
    def _optimize_velocity(self, velocity: int) -> int:
        """Normalizuj brzinu u guitar opsegu"""
        if velocity < self.config.min_vel:
            return self.config.min_vel
        elif velocity > self.config.max_vel:
            return self.config.max_vel
        return velocity


class DrumKitEngine:
    """Engine za optimizaciju Drum zvuka"""
    
    # Mapiranje drum nota
    DRUM_MAP = {
        36: ("Kick", (50, 110)),
        38: ("Snare", (60, 110)),
        42: ("Closed HH", (40, 90)),
        46: ("Open HH", (50, 100)),
        49: ("Crash", (70, 110)),
        51: ("Ride", (50, 100)),
    }
    
    def __init__(self):
        self.config = InstrumentConfig(
            name="Drums",
            instrument_type=InstrumentType.DRUMS,
            program_change=0,
            min_vel=30,
            max_vel=110,
            key_range=(35, 81),
            articulations=["kick", "snare", "hihat", "crash"],
            use_rx_enhancement=True,
            use_dnc=True
        )
    
    def optimize_drum_track(self, track: MidiTrack) -> MidiTrack:
        """Optimizuj drum track sa individualne vel opsege"""
        optimized = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # Pronadi tip bubnja i primeni opseg
                if msg.note in self.DRUM_MAP:
                    drum_name, (min_vel, max_vel) = self.DRUM_MAP[msg.note]
                    msg.velocity = self._constrain_velocity(msg.velocity, min_vel, max_vel)
                else:
                    msg.velocity = self._constrain_velocity(msg.velocity, 
                                                           self.config.min_vel,
                                                           self.config.max_vel)
            
            optimized.append(msg)
        
        return optimized
    
    def _constrain_velocity(self, velocity: int, min_vel: int, max_vel: int) -> int:
        """Ogranici brzinu u dozvoljenom opsegu"""
        return max(min_vel, min(max_vel, velocity))


class MIDIEnhancer:
    """MIDI poboljsanja i RX/DNC obrada"""
    
    def __init__(self):
        pass
    
    def apply_rx_enhancement(self, track: MidiTrack, strength: float = 0.5) -> MidiTrack:
        """Primeni RX enhancement (smanjenje suma)"""
        enhanced = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # Lagano podesi off-key note na blize note
                msg = self._quantize_note(msg, strength)
            
            enhanced.append(msg)
        
        return enhanced
    
    def apply_dnc(self, track: MidiTrack, sensitivity: float = 0.5) -> MidiTrack:
        """Primeni DNC (Dynamic Noise Control)"""
        enhanced = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # Ukloni vrlo tihe note (buka)
                if msg.velocity < int(30 * sensitivity):
                    continue
            
            enhanced.append(msg)
        
        return enhanced
    
    def apply_rx_delay(self, track: MidiTrack, delay_amount: float = 20) -> MidiTrack:
        """Primeni RX delay za smooth-anja solo"""
        delayed = MidiTrack()
        
        for msg in track:
            if msg.type == 'note_on':
                # Dodaj maleni delay za smoothing
                msg.time = int(msg.time + delay_amount)
            
            delayed.append(msg)
        
        return delayed
    
    def _quantize_note(self, msg: Message, strength: float) -> Message:
        """Kvantizuj notu"""
        # U osnovnoj verziji samo vratimo istu notu
        return msg


class AutoEngineer:
    """Glavni auto engineering engine"""
    
    def __init__(self, midi_file: MidiFile):
        self.midi_file = midi_file
        self.analyzer = MIDIAnalyzer()
        self.bass_engine = BassEngine()
        self.guitar_engine = GuitarEngine()
        self.drum_engine = DrumKitEngine()
        self.enhancer = MIDIEnhancer()
        self.analyses: Dict[int, TrackAnalysis] = {}
        
    def auto_process(self) -> Tuple[MidiFile, List[str]]:
        """Automatski obradi MIDI fajl"""
        self.analyzer.midi_file = self.midi_file
        self.analyses = self.analyzer.analyze_all_tracks()
        
        logs = []
        processed_midi = MidiFile()
        processed_midi.ticks_per_beat = self.midi_file.ticks_per_beat
        
        # Obradi svaki trak
        for track_idx, track in enumerate(self.midi_file.tracks):
            if track_idx not in self.analyses:
                processed_midi.tracks.append(track)
                continue
            
            analysis = self.analyses[track_idx]
            logs.append(f"Obrada trakta {track_idx}: {analysis.track_name} ({analysis.instrument_type.value})")
            
            processed_track = self._process_track(track, analysis, logs)
            processed_midi.tracks.append(processed_track)
        
        return processed_midi, logs
    
    def _process_track(self, track: MidiTrack, analysis: TrackAnalysis, 
                      logs: List[str]) -> MidiTrack:
        """Obradi pojedinacni trak"""
        processed = MidiTrack()
        processed.name = track.name
        
        if analysis.instrument_type == InstrumentType.BASS:
            processed = self.bass_engine.optimize(track)
            logs.append(f"  OK Bass optimizacija: vel {self.bass_engine.config.min_vel}-{self.bass_engine.config.max_vel}")
        
        elif analysis.instrument_type == InstrumentType.GUITAR:
            processed = self.guitar_engine.add_strumming_pattern(track)
            logs.append(f"  OK Guitar strumming & optimizacija")
        
        elif analysis.instrument_type == InstrumentType.DRUMS:
            processed = self.drum_engine.optimize_drum_track(track)
            logs.append(f"  OK Drum kit optimizacija sa per-drum opsezima")
        
        # Primeni RX/DNC ako je potrebno
        if analysis.has_solo_section:
            processed = self.enhancer.apply_rx_delay(processed, delay_amount=15)
            logs.append(f"  OK RX Delay za solo sekciju")
        
        if analysis.is_third_of_solo:
            # Smanji trece
            processed = self._reduce_background(processed, reduction=35)
            logs.append(f"  OK Smanjenje trece za -35%")
        
        return processed
    
    def _reduce_background(self, track: MidiTrack, reduction: float = 35.0) -> MidiTrack:
        """Smanji background velocity"""
        reduced = MidiTrack()
        
        factor = (100 - reduction) / 100
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                msg.velocity = int(msg.velocity * factor)
                msg.velocity = max(30, msg.velocity)  # Minimum
            
            reduced.append(msg)
        
        return reduced


class ProcessingThread(QThread):
    """Thread za obradu bez blokiranja GUI"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, list)  # processed_midi, logs
    error = pyqtSignal(str)
    
    def __init__(self, midi_file: MidiFile):
        super().__init__()
        self.midi_file = midi_file
    
    def run(self):
        try:
            engineer = AutoEngineer(self.midi_file)
            processed_midi, logs = engineer.auto_process()
            self.finished.emit(processed_midi, logs)
        except Exception as e:
            self.error.emit(str(e))


class MIDIVelocityOptimizer(QMainWindow):
    """Glavna GUI aplikacija"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Velocity Optimizer & Auto Engineer")
        self.setGeometry(100, 100, 1400, 900)
        
        self.midi_file: Optional[MidiFile] = None
        self.current_filepath: Optional[str] = None
        self.processed_midi: Optional[MidiFile] = None
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Postavi UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        
        # Top bar - File operations
        top_layout = QHBoxLayout()
        
        btn_load = QPushButton("Ucitaj MIDI")
        btn_load.clicked.connect(self.load_midi_file)
        top_layout.addWidget(btn_load)
        
        btn_auto_optimize = QPushButton("Auto Optimize")
        btn_auto_optimize.clicked.connect(self.auto_optimize)
        btn_auto_optimize.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        top_layout.addWidget(btn_auto_optimize)
        
        btn_batch = QPushButton("Batch Folder")
        btn_batch.clicked.connect(self.batch_process_folder)
        top_layout.addWidget(btn_batch)
        
        btn_save = QPushButton("Spremi MIDI")
        btn_save.clicked.connect(self.save_midi_file)
        top_layout.addWidget(btn_save)
        
        top_layout.addStretch()
        
        main_layout.addLayout(top_layout)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Tab 1: Track List
        self.tab_tracks = self._create_tracks_tab()
        tabs.addTab(self.tab_tracks, "Trakovi (16)")
        
        # Tab 2: Engines
        self.tab_engines = self._create_engines_tab()
        tabs.addTab(self.tab_engines, "Engines")
        
        # Tab 3: Analysis
        self.tab_analysis = self._create_analysis_tab()
        tabs.addTab(self.tab_analysis, "Analiza")
        
        # Tab 4: Batch Settings
        self.tab_batch = self._create_batch_tab()
        tabs.addTab(self.tab_batch, "Batch Postavke")
        
        main_layout.addWidget(tabs)
        
        # Logs
        log_label = QLabel("Obrada Log:")
        main_layout.addWidget(log_label)
        
        self.text_logs = QTextEdit()
        self.text_logs.setReadOnly(True)
        self.text_logs.setMaximumHeight(120)
        main_layout.addWidget(self.text_logs)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        central_widget.setLayout(main_layout)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Spreman...")
    
    def _create_tracks_tab(self) -> QWidget:
        """Kreiraj tab sa trakovima"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Track list
        self.tree_tracks = QTreeWidget()
        self.tree_tracks.setHeaderLabels([
            "Trak", "Tip", "Brzina", "Opseg", "Note", "Solo?", "Akcija"
        ])
        layout.addWidget(self.tree_tracks)
        
        widget.setLayout(layout)
        return widget
    
    def _create_engines_tab(self) -> QWidget:
        """Kreiraj tab za engines"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Bass Engine
        bass_group = self._create_engine_group("Bass Engine", {
            "Min Velocity": (30, 127),
            "Max Velocity": (30, 127),
            "Key Range Min": (0, 127),
            "Key Range Max": (0, 127),
            "RX Enhancement": None,
            "DNC": None,
        })
        scroll_layout.addWidget(bass_group)
        
        # Guitar Engine
        guitar_group = self._create_engine_group("Guitar Engine", {
            "Min Velocity": (30, 127),
            "Max Velocity": (30, 127),
            "Strummer Intensity": (0, 100),
            "RX Enhancement": None,
            "DNC": None,
        })
        scroll_layout.addWidget(guitar_group)
        
        # Drum Kit Engine
        drums_group = self._create_engine_group("Drum Kit Engine", {
            "Kick Vel Min-Max": (20, 127),
            "Snare Vel Min-Max": (40, 127),
            "HiHat Vel Min-Max": (30, 127),
            "Crash Vel Min-Max": (50, 127),
            "RX Enhancement": None,
        })
        scroll_layout.addWidget(drums_group)
        
        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        
        layout.addWidget(scroll)
        widget.setLayout(layout)
        return widget
    
    def _create_engine_group(self, title: str, params: dict) -> QGroupBox:
        """Kreiraj grupu za engine"""
        group = QGroupBox(title)
        form = QFormLayout()
        
        for param_name, param_range in params.items():
            if param_range is None:
                widget = QCheckBox("Ukljuci")
            else:
                spin = QSpinBox()
                spin.setRange(param_range[0], param_range[1])
                spin.setValue((param_range[0] + param_range[1]) // 2)
                widget = spin
            
            form.addRow(param_name + ":", widget)
        
        group.setLayout(form)
        return group
    
    def _create_analysis_tab(self) -> QWidget:
        """Kreiraj tab za analizu"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Analysis table
        self.table_analysis = QTableWidget()
        self.table_analysis.setColumnCount(8)
        self.table_analysis.setHorizontalHeaderLabels([
            "Trak", "Tip", "Opseg", "Min-Max Vel", "Ukupno nota", 
            "Solo", "Tercija", "Delay"
        ])
        layout.addWidget(self.table_analysis)
        
        widget.setLayout(layout)
        return widget
    
    def _create_batch_tab(self) -> QWidget:
        """Kreiraj tab za batch"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        group = QGroupBox("Batch Auto Postavke")
        form = QFormLayout()
        
        self.check_auto_bass = QCheckBox("Primeni Bass Engine")
        self.check_auto_bass.setChecked(True)
        form.addRow("Bass:", self.check_auto_bass)
        
        self.check_auto_guitar = QCheckBox("Primeni Guitar Engine")
        self.check_auto_guitar.setChecked(True)
        form.addRow("Guitar:", self.check_auto_guitar)
        
        self.check_auto_drums = QCheckBox("Primeni Drum Kit Engine")
        self.check_auto_drums.setChecked(True)
        form.addRow("Drums:", self.check_auto_drums)
        
        self.spin_reduction = QSpinBox()
        self.spin_reduction.setRange(0, 100)
        self.spin_reduction.setValue(35)
        form.addRow("Background Reduction (%):", self.spin_reduction)
        
        self.check_rx = QCheckBox("RX Enhancement")
        self.check_rx.setChecked(True)
        form.addRow("Obrada:", self.check_rx)
        
        self.check_dnc = QCheckBox("DNC (Noise Control)")
        self.check_dnc.setChecked(True)
        form.addRow("", self.check_dnc)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def load_midi_file(self):
        """Ucitaj MIDI fajl"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Ucitaj MIDI", "", "MIDI Files (*.mid *.midi);;Svi Fajlovi (*)"
        )
        
        if not filepath:
            return
        
        try:
            self.midi_file = MidiFile(filepath)
            self.current_filepath = filepath
            self.statusBar.showMessage(f"Ucitan: {Path(filepath).name}")
            
            self.update_track_list()
            self.update_analysis()
            
            self.log(f"OK Ucitan: {filepath}")
            self.log(f"  Trakovi: {len(self.midi_file.tracks)}")
            self.log(f"  Tempo: {self.midi_file.ticks_per_beat} ticks/beat")
        
        except Exception as e:
            QMessageBox.critical(self, "Greska", f"Greska pri ucitavanju:\n{e}")
            self.log(f"ERROR Greska: {e}")
    
    def update_track_list(self):
        """Ažuriraj listu trakova"""
        if not self.midi_file:
            return
        
        self.tree_tracks.clear()
        analyzer = MIDIAnalyzer()
        analyzer.midi_file = self.midi_file
        analyses = analyzer.analyze_all_tracks()
        
        for idx, analysis in analyses.items():
            item = QTreeWidgetItem()
            item.setText(0, f"{idx}: {analysis.track_name}")
            item.setText(1, analysis.instrument_type.value)
            
            vel_min, vel_max = analysis.velocity_range
            item.setText(2, f"{vel_min}-{vel_max}")
            
            note_min, note_max = analysis.note_range
            item.setText(3, f"{note_min}-{note_max}")
            
            item.setText(4, str(analysis.total_notes))
            item.setText(5, "*" if analysis.has_solo_section else "")
            item.setText(6, "*" if analysis.is_third_of_solo else "")
            
            self.tree_tracks.addTopLevelItem(item)
    
    def update_analysis(self):
        """Ažuriraj analizu"""
        if not self.midi_file:
            return
        
        analyzer = MIDIAnalyzer()
        analyzer.midi_file = self.midi_file
        analyses = analyzer.analyze_all_tracks()
        
        self.table_analysis.setRowCount(len(analyses))
        
        for row, (idx, analysis) in enumerate(analyses.items()):
            self.table_analysis.setItem(row, 0, 
                                       QTableWidgetItem(f"{idx}: {analysis.track_name}"))
            self.table_analysis.setItem(row, 1, 
                                       QTableWidgetItem(analysis.instrument_type.value))
            
            note_min, note_max = analysis.note_range
            self.table_analysis.setItem(row, 2, 
                                       QTableWidgetItem(f"{note_min}-{note_max}"))
            
            vel_min, vel_max = analysis.velocity_range
            self.table_analysis.setItem(row, 3, 
                                       QTableWidgetItem(f"{vel_min}-{vel_max}"))
            
            self.table_analysis.setItem(row, 4, 
                                       QTableWidgetItem(str(analysis.total_notes)))
            self.table_analysis.setItem(row, 5, 
                                       QTableWidgetItem("*" if analysis.has_solo_section else ""))
            self.table_analysis.setItem(row, 6, 
                                       QTableWidgetItem("*" if analysis.is_third_of_solo else ""))
            self.table_analysis.setItem(row, 7, 
                                       QTableWidgetItem("*" if analysis.has_delay else ""))
    
    def auto_optimize(self):
        """Automatska optimizacija"""
        if not self.midi_file:
            QMessageBox.warning(self, "Upozorenje", "Prvo ucitaj MIDI fajl!")
            return
        
        self.text_logs.clear()
        self.log("Zapoeta auto optimizacija...")
        
        # Kreiraj processing thread
        self.thread = ProcessingThread(self.midi_file)
        self.thread.finished.connect(self.on_optimization_finished)
        self.thread.error.connect(self.on_optimization_error)
        self.thread.start()
        
        self.statusBar.showMessage("Obrada u tijeku...")
    
    def on_optimization_finished(self, processed_midi: MidiFile, logs: List[str]):
        """Gotova optimizacija"""
        self.processed_midi = processed_midi
        
        for log_entry in logs:
            self.log(log_entry)
        
        self.log("\nOK Obrada zavrsena!")
        self.statusBar.showMessage("Obrada zavrsena - spreman za spremanje")
    
    def on_optimization_error(self, error_msg: str):
        """Greška pri optimizaciji"""
        self.log(f"ERROR Greska: {error_msg}")
        QMessageBox.critical(self, "Greska pri obradi", error_msg)
        self.statusBar.showMessage("Greska pri obradi")
    
    def save_midi_file(self):
        """Spremi MIDI fajl"""
        if not self.processed_midi:
            QMessageBox.warning(self, "Upozorenje", 
                              "Prvo optimizuj MIDI fajl!")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Spremi MIDI", 
            f"{Path(self.current_filepath).stem}_optimized.mid",
            "MIDI Files (*.mid);;MIDI Files (*.midi)"
        )
        
        if not filename:
            return
        
        try:
            self.processed_midi.save(filename)
            self.log(f"OK Sprema: {filename}")
            QMessageBox.information(self, "Uspjeh", "MIDI fajl sprema!")
            self.statusBar.showMessage(f"Sprema: {Path(filename).name}")
        except Exception as e:
            QMessageBox.critical(self, "Greska", f"Greska pri spremanju:\n{e}")
            self.log(f"ERROR Greska pri spremanju: {e}")
    
    def batch_process_folder(self):
        """Batch obrada foldera"""
        folder = QFileDialog.getExistingDirectory(self, "Odaberi folder")
        
        if not folder:
            return
        
        self.text_logs.clear()
        self.log(f"Batch obrada: {folder}")
        
        midi_files = list(Path(folder).glob("*.mid")) + list(Path(folder).glob("*.midi"))
        
        if not midi_files:
            self.log("Nema MIDI fajlova u folderu!")
            return
        
        self.log(f"Pronađeno {len(midi_files)} MIDI fajlova")
        
        output_folder = Path(folder) / "optimized"
        output_folder.mkdir(exist_ok=True)
        
        for midi_file_path in midi_files:
            try:
                self.log(f"\nObrada: {midi_file_path.name}")
                
                midi = MidiFile(str(midi_file_path))
                engineer = AutoEngineer(midi)
                processed, logs = engineer.auto_process()
                
                for log_entry in logs:
                    self.log(f"  {log_entry}")
                
                output_path = output_folder / f"{midi_file_path.stem}_opt.mid"
                processed.save(str(output_path))
                
                self.log(f"  OK Sprema: {output_path.name}")
            
            except Exception as e:
                self.log(f"  ERROR Greska: {e}")
        
        self.log(f"\nOK Batch obrada zavrsena!")
        self.log(f"  Rezultati: {output_folder}")
    
    def log(self, message: str):
        """Dodaj poruku u log"""
        self.text_logs.append(message)
    
    def load_settings(self):
        """Ucitaj postavke"""
        settings = QSettings("MIDIOptimizer", "Settings")
        self.restoreGeometry(settings.value("geometry", b""))
    
    def closeEvent(self, event):
        """Spremi postavke pri zatvaranju"""
        settings = QSettings("MIDIOptimizer", "Settings")
        settings.setValue("geometry", self.saveGeometry())
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MIDIVelocityOptimizer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
