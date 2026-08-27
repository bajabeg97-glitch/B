from pa800_optimizer.ai_brain import AIResourceBrain, ResourceSnapshot, govern_config
from pa800_optimizer.config import OptimizeConfig


def snap(cpus=8,total=16384,avail=12000,ratio=.73):
    return ResourceSnapshot(cpus,total,avail,ratio,'TestOS','test')


def test_auto_performance_machine_admits_neural_and_caps_threads():
    d=AIResourceBrain('auto').decide(note_count=4000,context_count=16,neural_requested=True,snapshot=snap())
    assert d.tier=='performance'
    assert d.neural_allowed is True
    assert 1 <= d.max_cpu_threads <= 4


def test_memory_pressure_defers_neural_without_disabling_factory_engines():
    low=ResourceSnapshot(4,4096,700,.17,'TestOS','test')
    d=AIResourceBrain('auto').decide(note_count=25000,context_count=16,neural_requested=True,snapshot=low)
    cfg=OptimizeConfig.for_mode('max');cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_only=True
    governed=govern_config(cfg,d)
    assert d.neural_allowed is False
    assert governed.apply_trained_rhythm_model is False
    assert governed.trained_rhythm_only is False
    assert governed.enable_velocity is True
    assert governed.enable_timing is True
    assert governed.enable_gate is True


def test_explicit_eco_is_one_thread_one_worker():
    d=AIResourceBrain('eco').decide(note_count=100,neural_requested=False,snapshot=snap())
    assert d.tier=='eco'
    assert d.max_cpu_threads==1
    assert d.max_batch_workers==1
    assert d.advisory_level=='essential'


def test_resource_brain_does_not_change_musical_strengths_when_neural_admitted():
    cfg=OptimizeConfig.for_mode('max');cfg.apply_trained_rhythm_model=True
    d=AIResourceBrain('performance').decide(note_count=1000,neural_requested=True,snapshot=snap())
    governed=govern_config(cfg,d)
    assert governed.velocity_strength==cfg.velocity_strength
    assert governed.timing_strength==cfg.timing_strength
    assert governed.gate_strength==cfg.gate_strength
    assert governed.apply_trained_rhythm_model is True
