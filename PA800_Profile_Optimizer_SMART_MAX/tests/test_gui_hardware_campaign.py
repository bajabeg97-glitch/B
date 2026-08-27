import sys

from pa800_optimizer.gui_state import _hardware_create_command,_hardware_evaluate_commands


def test_gui_hardware_commands_use_selected_campaign_folder(tmp_path):
    folder=tmp_path/'PA800_HARDWARE_CAMPAIGN';create=_hardware_create_command(tmp_path,folder)
    assert create[0]==sys.executable and str(folder) in create and create[1].endswith('create_hardware_campaign.py')
    evaluate,gate,evaluation_path,gate_path=_hardware_evaluate_commands(tmp_path,folder)
    assert str(folder/'CAMPAIGN.json') in evaluate and str(folder/'RESULTS.csv') in evaluate
    assert str(evaluation_path) in gate and gate_path==folder/'FINAL_RELEASE_GATE.json'