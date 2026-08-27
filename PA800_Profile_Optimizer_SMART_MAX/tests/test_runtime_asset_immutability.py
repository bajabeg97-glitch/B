import os

import pytest

from pa800_optimizer.gui_state import _activate_model_candidate,build_training_command
from pa800_optimizer.runtime_assets import _RuntimeAssetGuard


def test_runtime_asset_guard_detects_canonical_json_change(tmp_path):
    data=tmp_path/'data';data.mkdir();profile=data/'factory.json';profile.write_text('{}',encoding='utf-8');model=tmp_path/'encoder.json';model.write_text('{"v":1}',encoding='utf-8');guard=_RuntimeAssetGuard(data,model)
    profile.write_text('{"changed":true}',encoding='utf-8');os.utime(profile,None)
    with pytest.raises(RuntimeError,match='IMMUTABILITY'):guard.assert_unchanged()
    assert profile.read_text(encoding='utf-8')=='{}'


def test_runtime_asset_guard_rolls_back_active_model_deletion(tmp_path):
    data=tmp_path/'data';data.mkdir();model=tmp_path/'encoder.json';model.write_text('{"accepted":true}',encoding='utf-8');guard=_RuntimeAssetGuard(data,model)
    model.unlink()
    with pytest.raises(RuntimeError,match='restored='):guard.assert_unchanged()
    assert model.read_text(encoding='utf-8')=='{"accepted":true}'


def test_training_targets_candidate_and_activation_is_explicit(tmp_path):
    folder=tmp_path/'midi';folder.mkdir();command=build_training_command(tmp_path,folder,epochs=5,stamp='FIXED');candidate=tmp_path/'models'/'candidates'/'encoder_FIXED.json'
    assert command[command.index('--output')+1]==str(candidate)
    candidate.parent.mkdir(parents=True);candidate.write_text('candidate',encoding='utf-8');active=tmp_path/'models'/'encoder.json';active.write_text('active',encoding='utf-8');assert active.read_text()=='active'
    _activate_model_candidate(candidate,active);assert active.read_text()=='candidate'