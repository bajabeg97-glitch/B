# core/history.py

import copy
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class EditType(Enum):
    CREATE = "create"
    DELETE = "delete"
    MODIFY = "modify"
    BATCH = "batch"

@dataclass
class EventDelta:
    """Predstavlja minimalnu promjenu na jednom eventu."""
    event_id: int
    track_index: int
    edit_type: EditType
    field_name: Optional[str] = None  # Npr. "velocity", "absolute_tick"
    old_value: Any = None
    new_value: Any = None
    event_data: Optional[Dict] = None  # Za CREATE/DELETE čuvamo cijeli event dict

@dataclass
class UndoSnapshot:
    """Snapshot koji sadrži samo listu promjena (Delta), a ne cijeli projekt."""
    description: str
    timestamp: float
    deltas: List[EventDelta] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        return len(self.deltas) == 0

class HistoryManager:
    """
    Upravlja Undo/Redo stackom koristeći Delta pristup.
    Umjesto čuvanja cijelog MidiProject objekta (što troši RAM),
    čuvamo samo listu izmjena (EventDelta).
    """
    
    def __init__(self, max_depth: int = 100):
        self.undo_stack: List[UndoSnapshot] = []
        self.redo_stack: List[UndoSnapshot] = []
        self.max_depth = max_depth
        self.current_batch_deltas: List[EventDelta] = []
        self.batch_mode = False
        self._batch_description: str = ""

    def start_batch(self, description: str):
        """Počinje grupisanje više operacija u jedan Undo korak."""
        self.batch_mode = True
        self.current_batch_deltas = []
        self._batch_description = description

    def end_batch(self):
        """Završava batch i sprema snapshot."""
        if not self.batch_mode:
            return
        
        self.batch_mode = False
        if self.current_batch_deltas:
            snapshot = UndoSnapshot(
                description=self._batch_description,
                timestamp=0.0,
                deltas=self.current_batch_deltas
            )
            self._push_snapshot(snapshot)
        self.current_batch_deltas = []
        self._batch_description = ""

    def record_create(self, track_index: int, event_data: Dict, event_id: int):
        delta = EventDelta(
            event_id=event_id,
            track_index=track_index,
            edit_type=EditType.CREATE,
            event_data=event_data
        )
        self._record_delta(delta)

    def record_delete(self, track_index: int, event_id: int, event_data: Dict):
        delta = EventDelta(
            event_id=event_id,
            track_index=track_index,
            edit_type=EditType.DELETE,
            event_data=event_data
        )
        self._record_delta(delta)

    def record_modify(self, track_index: int, event_id: int, field_name: str, old_val: Any, new_val: Any):
        if old_val == new_val:
            return
        delta = EventDelta(
            event_id=event_id,
            track_index=track_index,
            edit_type=EditType.MODIFY,
            field_name=field_name,
            old_value=old_val,
            new_value=new_val
        )
        self._record_delta(delta)

    def _record_delta(self, delta: EventDelta):
        if self.batch_mode:
            self.current_batch_deltas.append(delta)
        else:
            snapshot = UndoSnapshot(
                description=f"Modify {delta.field_name}",
                timestamp=0.0,
                deltas=[delta]
            )
            self._push_snapshot(snapshot)

    def _push_snapshot(self, snapshot: UndoSnapshot):
        if snapshot.is_empty():
            return
        
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()
        
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)

    def undo(self, project) -> Optional[str]:
        if not self.undo_stack:
            return None
        
        snapshot = self.undo_stack.pop()
        self._apply_snapshot(project, snapshot, is_undo=True)
        self.redo_stack.append(snapshot)
        return snapshot.description

    def redo(self, project) -> Optional[str]:
        if not self.redo_stack:
            return None
        
        snapshot = self.redo_stack.pop()
        self._apply_snapshot(project, snapshot, is_undo=False)
        self.undo_stack.append(snapshot)
        return snapshot.description

    def _apply_snapshot(self, project, snapshot: UndoSnapshot, is_undo: bool):
        """Prima snapshot i primjenjuje inverzne operacije na projekt."""
        # Projekt ima 'document' koji sadrži 'tracks'
        if not hasattr(project, 'document') or not project.document:
            return
            
        doc = project.document
        deltas = reversed(snapshot.deltas) if is_undo else snapshot.deltas
        
        for delta in deltas:
            if delta.track_index >= len(doc.tracks):
                continue
            track = doc.tracks[delta.track_index]
            
            if delta.edit_type == EditType.CREATE:
                if is_undo:
                    track.remove_event_by_id(delta.event_id)
                else:
                    from core.models import MidiEvent
                    new_event = MidiEvent.from_dict(delta.event_data)
                    new_event.event_id = delta.event_id
                    track.add_event(new_event)

            elif delta.edit_type == EditType.DELETE:
                if is_undo:
                    restored_event = MidiEvent.from_dict(delta.event_data)
                    restored_event.event_id = delta.event_id
                    track.add_event(restored_event)
                else:
                    track.remove_event_by_id(delta.event_id)

            elif delta.edit_type == EditType.MODIFY:
                event = track.get_event_by_id(delta.event_id)
                if event and delta.field_name:
                    value = delta.old_value if is_undo else delta.new_value
                    setattr(event, delta.field_name, value)
        
        if hasattr(project, 'on_modified'):
            project.on_modified()

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_batch_deltas = []
        self._batch_description = ""
