from core.history import DeltaUndoManager, EditType, create_note_delta


def test_undo_redo_and_max_depth():
    manager = DeltaUndoManager(max_depth=3)
    assert not manager.can_undo()
    for i in range(4):
        manager.push(create_note_delta(EditType.NOTE_ADD, 0, f"e{i}", description=str(i)))
    assert len(manager.undo_stack) == 3
    first = manager.undo()
    assert first.description == "3"
    assert manager.can_redo()
    redone = manager.redo()
    assert redone.description == "3"
    manager.clear()
    assert not manager.can_undo()
    assert manager.undo() is None
    assert manager.redo() is None
