from pathlib import Path

import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.neural.event_contract import encode_neural_contract
from pa800_optimizer.neural.self_supervised_encoder import finalize_encoder_acceptance,save_encoder_model,train_self_supervised_encoder
from pa800_optimizer.optimizer import Optimizer
from tools.run_neural_dataset_certification import certify


def _voice_events(path):
    return [(message.type,getattr(message,'control',None),getattr(message,'value',None),getattr(message,'program',None)) for track in mido.MidiFile(path).tracks for message in track if message.type=='program_change' or (message.type=='control_change' and message.control in (0,32,80,81))]


def _velocities(path):
    return [message.velocity for track in mido.MidiFile(path).tracks for message in track if message.type=='note_on' and message.velocity>0]


def _neural_only_cfg(model):
    cfg=OptimizeConfig.for_mode('natural');cfg.content_type='song';cfg.autopilot=False;cfg.enable_velocity=False;cfg.enable_velocity_conductor=False;cfg.enable_gate=False;cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False;cfg.enable_articulation_director=False;cfg.enable_performance_director=True;cfg.apply_performance_director=False;cfg.enable_mix_fx_director=False;cfg.enable_timing=True;cfg.timing_strength=1.0;cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_model_path=str(model);cfg.trained_rhythm_only=True
    return cfg


def test_low_confidence_accepted_model_falls_back_without_neural_mutation(tmp_path):
    certify(tmp_path/'dataset');sources=sorted((tmp_path/'dataset'/'sources').glob('*.mid'));contracts=[encode_neural_contract(path,include_source_bytes=False) for path in sources]
    trained=train_self_supervised_encoder(contracts,epochs=40);trained,acceptance,_evaluation=finalize_encoder_acceptance(contracts,trained);assert acceptance['pass'] and acceptance['confidence']<.45
    model=save_encoder_model(trained,tmp_path/'encoder.json');source=next(path for path in sources if path.name=='GTR-001_positive.mid');output=tmp_path/'fallback.mid'
    report=Optimizer(_neural_only_cfg(model)).optimize(source,output)
    runtime=report.workstation['trained_rhythm_application']['runtime_admission']
    assert runtime['mode']=='REJECT_TO_FACTORY_GOLD' and not runtime['proposal_allowed']
    assert not any(change.kind in ('timing','gate') for change in report.changes)
    assert _velocities(source)==_velocities(output) and _voice_events(source)==_voice_events(output)
    assert report.verifier['pass'] and report.quality_gate['pass']


def test_promoted_encoder_applies_timing_gate_proposals_but_preserves_factory_authority(tmp_path):
    certify(tmp_path/'dataset');source=tmp_path/'dataset'/'sources'/'GTR-001_positive.mid';output=tmp_path/'applied.mid'
    model=Path(__file__).resolve().parents[1]/'models'/'encoder.json'
    report=Optimizer(_neural_only_cfg(model)).optimize(source,output)
    assert report.verifier['pass'] and report.quality_gate['pass'] and report.quality_gate['neural_factory_boundary']['pass']
    assert any(change.kind=='timing' for change in report.changes) and any(change.kind=='gate' for change in report.changes)
    assert _velocities(source)==_velocities(output) and _voice_events(source)==_voice_events(output)
    summary=report.workstation['trained_rhythm_application'];runtime=summary['runtime_admission']
    assert runtime['mode']=='ALLOW_WITH_FACTORY_VERIFY' and runtime['confidence']==.696373
    assert runtime['mutation_authority'] is False and runtime['factory_gold_verifier_required']
    assert summary['velocity_features_applied']==0 and summary['pitch_features_applied']==0 and summary['voice_settings_applied']==0
    assert summary['model_acceptance']['pass']
    assert 'MODEL' not in summary['authority_selection']
