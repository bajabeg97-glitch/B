from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

@dataclass
class SoundIdentity:
    msb: Optional[int]
    lsb: Optional[int]
    program: Optional[int]
    name: Optional[str] = None
    family: str = 'UNKNOWN'
    rx_named: bool = False
    dnc_named: bool = False
    conflict: bool = False

    def address(self):
        return (self.msb, self.lsb, self.program)

@dataclass
class TrackContext:
    track_index: int
    channel: int
    role: str
    identity: SoundIdentity
    element: Optional[str] = None
    cv: Optional[int] = None
    family: str = 'UNKNOWN'
    track_name: str = ''
    content_type: str = 'song'
    resolution_status: str = ''

@dataclass
class NoteEvent:
    track_index: int
    channel: int
    note: int
    velocity: int
    onset: int
    off: int
    on_index: int
    off_index: int
    occurrence: int = 0
    intent: str = 'NORMAL'
    protected: bool = False

    @property
    def duration(self): return max(0, self.off-self.onset)

@dataclass
class Change:
    track: int
    event_index: int
    kind: str
    old: int
    new: int
    reason: str
    profile: str = ''
    channel: Optional[int] = None
    note: Optional[int] = None
    occurrence: Optional[int] = None
    protected: Optional[bool] = None

@dataclass
class OptimizationReport:
    input_file: str
    output_file: str
    changes: List[Change] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    contexts: List[Dict] = field(default_factory=list)
    verifier: Dict = field(default_factory=dict)
    intelligence: List[Dict] = field(default_factory=list)
    content_type: str = 'auto'
    factory_usage: List[Dict] = field(default_factory=list)
    content_detection: Dict = field(default_factory=dict)
    automation_decision: Dict = field(default_factory=dict)
    midi_repair: Dict = field(default_factory=dict)
    velocity_conductor: Dict = field(default_factory=dict)
    change_summary: Dict = field(default_factory=dict)
    articulations: Dict = field(default_factory=dict)
    musical_context: Dict = field(default_factory=dict)
    musical_understanding: Dict = field(default_factory=dict)
    section_narrative: Dict = field(default_factory=dict)
    family_intent: Dict = field(default_factory=dict)
    instrument_intent: Dict = field(default_factory=dict)
    pattern_advisor: Dict = field(default_factory=dict)
    musician_workflow: Dict = field(default_factory=dict)
    performance_director: Dict = field(default_factory=dict)
    hardware_evidence: Dict = field(default_factory=dict)
    audition_queue: Dict = field(default_factory=dict)
    mix_fx_director: Dict = field(default_factory=dict)
    compatibility: Dict = field(default_factory=dict)
    workstation: Dict = field(default_factory=dict)
    authority_ledger: Dict = field(default_factory=dict)
    quality_gate: Dict = field(default_factory=dict)
    mutation_ledger: List[Dict] = field(default_factory=list)
    factory_usage_meter: Dict = field(default_factory=dict)
    instrument_director: Dict = field(default_factory=dict)
    style_import_contract: Dict = field(default_factory=dict)
    agent_mesh: Dict = field(default_factory=dict)
    song_map: Dict = field(default_factory=dict)
    phrase_doctor: Dict = field(default_factory=dict)
    repair_previews: Dict = field(default_factory=dict)
    musical_decision_plan: Dict = field(default_factory=dict)
    mutation_arbitration: Dict = field(default_factory=dict)
    quality_delta: Dict = field(default_factory=dict)
