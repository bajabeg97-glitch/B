from pa800_optimizer.config import OptimizeConfig


def test_smart_mutation_is_not_default():
    cfg=OptimizeConfig.for_mode('max')
    assert cfg.enable_sound_kit_selector is True
    assert cfg.apply_high_confidence_sound_changes is False
    assert cfg.apply_existing_fx_sends is False


def test_preserve_never_enables_smart_mutation():
    cfg=OptimizeConfig.for_mode('preserve')
    assert cfg.apply_high_confidence_sound_changes is False
    assert cfg.apply_existing_fx_sends is False
    assert cfg.enable_midi_repair is False
    assert cfg.enable_velocity is False
    assert cfg.enable_timing is False
    assert cfg.enable_gate is False
    assert cfg.enable_velocity_conductor is False
    assert cfg.velocity_strength==cfg.timing_strength==cfg.gate_strength==0


def test_gentle_retains_the_old_low_strength_profile_pass():
    cfg=OptimizeConfig.for_mode('gentle')
    assert cfg.enable_velocity and cfg.enable_timing and cfg.enable_gate
    assert (cfg.velocity_strength,cfg.timing_strength,cfg.gate_strength)==(.10,.05,.05)


def test_auto_mode_enables_single_pass_autopilot():
    cfg=OptimizeConfig.for_mode('auto')
    assert cfg.autopilot is True
    assert cfg.mode=='auto'


def test_explicit_full_optimization_test_enables_all_non_destructive_apply_paths():
    cfg=OptimizeConfig.for_mode('preserve').enable_full_optimization_test()
    assert cfg.test_full_optimization and cfg.mode=='max' and cfg.export_preset=='auto'
    assert cfg.apply_high_confidence_sound_changes and cfg.apply_existing_fx_sends and cfg.apply_articulation_triggers
    assert cfg.apply_performance_director and cfg.apply_mix_fx_director and not cfg.preserve_controllers
    assert cfg.protect_rx_low_velocity and cfg.protect_rx_special_pitch


def test_velocity_is_exact_factory_data_only_by_default_and_trill_correction_is_enabled():
    cfg=OptimizeConfig.for_mode('live')
    assert cfg.velocity_factory_data_only and cfg.enable_rhythm_trill_correction
    assert not cfg.apply_trained_rhythm_model and cfg.trained_rhythm_model_path is None

def test_autonomous_baja_max_keeps_full_authority_but_enables_autopilot():
    cfg=OptimizeConfig.for_mode('preserve').enable_autonomous_baja_max()
    assert cfg.autopilot and cfg.factory_gold_max and cfg.apply_baja_stage_profile
    assert cfg.test_full_optimization and cfg.ai_resource_policy=='auto'

def test_autonomous_baja_max_enables_bundled_neural_advisor_without_granting_neural_only_mode():
    cfg=OptimizeConfig.for_mode('live').enable_autonomous_baja_max()
    assert cfg.apply_trained_rhythm_model is True
    assert cfg.trained_rhythm_only is False
    # Path is resolved by Optimizer so config remains portable across installs.
    assert cfg.trained_rhythm_model_path is None
