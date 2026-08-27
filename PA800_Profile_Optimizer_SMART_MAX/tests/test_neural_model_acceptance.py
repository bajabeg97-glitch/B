import pytest

from pa800_optimizer.neural.self_supervised_encoder import load_encoder_model,save_encoder_model,train_self_supervised_encoder
from tools.run_neural_dataset_certification import certify
from pa800_optimizer.neural.event_contract import encode_neural_contract


def test_unaccepted_encoder_is_rejected_for_application(tmp_path):
    certify(tmp_path/'dataset');sources=sorted((tmp_path/'dataset'/'sources').glob('*.mid'));contracts=[encode_neural_contract(path,include_source_bytes=False) for path in sources]
    path=save_encoder_model(train_self_supervised_encoder(contracts,epochs=2),tmp_path/'encoder.json')
    assert load_encoder_model(path)
    with pytest.raises(ValueError,match='not accepted'):load_encoder_model(path,require_accepted=True)