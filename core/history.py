"""
Delta-Based Undo/Redo System
Umjesto čuvanja cijelog stanja projekta, čuva samo promjene (deltu).
Ovo drastično smanjuje potrošnju memorije i omogućava gotovo neograničen Undo/Redo.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time

class EditType(Enum):
    NOTE_ADD = "note_add"
    NOTE_DELETE = "note_delete"
    NOTE_MOVE = "note_move"
    NOTE_RESIZE = "note_resize"
    VELOCITY_CHANGE = "velocity_change"
    CC_CHANGE = "cc_change"
    PROGRAM_CHANGE = "program_change"
    TRACK_ADD = "track_add"
    TRACK_DELETE = "track_delete"
    BATCH_OPERATION = "batch_operation"

@dataclass
class Delta:
    """Predstavlja minimalnu promjenu potrebnu za undo/redo."""
    edit_type: EditType
    track_id: int
    event_id: Optional[str] = None
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    batch_deltas: Optional[List['Delta']] = None

class DeltaUndoManager:
    """Upravlja historijom izmjena koristeći Delta pristup."""
    
    def __init__(self, max_depth: int = 100):
        self.undo_stack: List[Delta] = []
        self.redo_stack: List[Delta] = []
        self.max_depth = max_depth
        self.is_recording = True

    def push(self, delta: Delta):
        if self.is_recording:
            self.undo_stack.append(delta)
            self.redo_stack.clear()
            if len(self.undo_stack) > self.max_depth:
                self.undo_stack.pop(0)

    def undo(self) -> Optional[Delta]:
        if not self.undo_stack:
            return None
        delta = self.undo_stack.pop()
        self.redo_stack.append(delta)
        return delta

    def redo(self) -> Optional[Delta]:
        if not self.redo_stack:
            return None
        delta = self.redo_stack.pop()
        self.undo_stack.append(delta)
        return delta

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

def create_note_delta(edit_type: EditType, track_id: int, event_id: str, 
                      old_data: Optional[Dict] = None, 
                      new_data: Optional[Dict] = None, 
                      description: str = "") -> Delta:
    return Delta(
        edit_type=edit_type, track_id=track_id, event_id=event_id,
        old_data=old_data, new_data=new_data, description=description
    )
