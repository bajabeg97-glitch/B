import sys
from pathlib import Path

from pa800_optimizer.gui_state import build_training_audit_command,build_training_command


def test_gui_training_command_uses_selected_folder_and_project_outputs(tmp_path):
    folder=tmp_path/'MIDI folder';folder.mkdir()
    command=build_training_command(tmp_path,folder,epochs=25)
    assert command[0]==sys.executable
    assert command[1]==str(tmp_path/'tools'/'train_neural_encoder.py')
    assert str(folder) in command
    assert str(tmp_path/'models'/'candidates') in command[command.index('--output')+1]
    assert str(tmp_path/'training_logs') in command
    assert command[command.index('--epochs')+1]=='25'


def test_gui_training_audit_command_is_read_only_scan(tmp_path):
    folder=tmp_path/'corpus';folder.mkdir();command=build_training_audit_command(tmp_path,folder)
    assert str(folder) in command and '--audit-only' in command
    assert command[command.index('--output')+1]==str(tmp_path/'models'/'candidates'/'AUDIT_ONLY.json')