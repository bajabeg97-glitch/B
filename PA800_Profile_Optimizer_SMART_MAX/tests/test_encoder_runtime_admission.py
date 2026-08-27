import copy
from pathlib import Path

from pa800_optimizer.neural.self_supervised_encoder import (
    encoder_runtime_admission,
    load_encoder_model,
)


def _model(confidence, accepted=True):
    return {
        'acceptance': {'pass': accepted, 'confidence': confidence},
        'authority_granted': False,
    }


def test_runtime_admission_high_confidence_is_proposal_only_with_factory_verify():
    status=encoder_runtime_admission(_model(.696373))
    assert status['mode']=='ALLOW_WITH_FACTORY_VERIFY'
    assert status['model_validated'] and status['inference_ready'] and status['proposal_allowed']
    assert status['mutation_authority'] is False and status['authority_granted'] is False
    assert status['factory_gold_verifier_required'] is True
    assert status['allowed_outputs']==['timing','gate']
    assert 'velocity' in status['forbidden_outputs'] and 'pitch' in status['forbidden_outputs']


def test_runtime_admission_mid_confidence_is_advisor_only():
    status=encoder_runtime_admission(_model(.55))
    assert status['mode']=='ADVISOR_ONLY'
    assert status['proposal_allowed'] and status['mutation_authority'] is False


def test_runtime_admission_low_or_unaccepted_falls_back():
    assert encoder_runtime_admission(_model(.44))['mode']=='REJECT_TO_FACTORY_GOLD'
    assert not encoder_runtime_admission(_model(.44))['proposal_allowed']
    assert not encoder_runtime_admission(_model(.90,accepted=False))['proposal_allowed']


def test_promoted_encoder_is_digest_valid_and_admitted():
    path=Path(__file__).resolve().parents[1]/'models'/'encoder.json'
    model=load_encoder_model(path,require_accepted=True)
    status=encoder_runtime_admission(model)
    assert model['model_digest']=='13f5ab0f446212e6a745a452352c70894080c2d3f49d082adce4dd5e3692b28f'
    assert status['mode']=='ALLOW_WITH_FACTORY_VERIFY'
    assert status['confidence']==.696373
    assert status['mutation_authority'] is False
