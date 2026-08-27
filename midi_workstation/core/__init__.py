"""
ULTIMATE MIDI WORKSTATION - CORE PACKAGE

Lossless MIDI Core sa parserom, writerom i modelima
"""

from .models import (
    # Enums
    EventType,
    ProcessingMode,
    ChangeIntent,
    TrackRole,
    
    # Data classes
    ArticulationMap,
    PerformanceIntent,
    MicrotonalPitch,
    RpnData,
    NrpnData,
    MidiEvent,
    MidiTrack,
    TempoMap,
    MeterMap,
    ChordEvent,
    Phrase,
    MidiDocument,
    MidiProject,
    VoiceLeadingConstraint,
    GrooveTemplate,
    NeuralModelConfig,
)

from .io import MidiParser, MidiWriter

__all__ = [
    # Enums
    'EventType',
    'ProcessingMode',
    'ChangeIntent',
    'TrackRole',
    
    # Data classes
    'ArticulationMap',
    'PerformanceIntent',
    'MicrotonalPitch',
    'RpnData',
    'NrpnData',
    'MidiEvent',
    'MidiTrack',
    'TempoMap',
    'MeterMap',
    'ChordEvent',
    'Phrase',
    'MidiDocument',
    'MidiProject',
    'VoiceLeadingConstraint',
    'GrooveTemplate',
    'NeuralModelConfig',
    
    # IO
    'MidiParser',
    'MidiWriter',
]

__version__ = "1.0.0"
