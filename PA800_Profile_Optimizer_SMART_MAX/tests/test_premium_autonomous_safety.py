from types import SimpleNamespace
from pa800_optimizer.models import SoundIdentity, TrackContext, NoteEvent
from pa800_optimizer.musical_brain import build_musical_decision_plan
from pa800_optimizer.premium_control import audit_performance_budget, recovery_record


def _ctx(conflict=False):
    return TrackContext(1,0,'BASS',SoundIdentity(121,16,33,'Bass','BASS',conflict=conflict),family='BASS')


def test_brain_marks_unknown_as_hard_preserve_with_zero_budget():
    plan=build_musical_decision_plan({(1,0):_ctx()}, {(1,0):None}, {}, ticks_per_beat=192)
    row=plan['tracks'][0]
    assert row['ood_status']=='HARD_PRESERVE'
    assert row['action']=='PRESERVE'
    assert row['mutation_budget']['velocity_delta']==0
    assert row['confidence_calibrated'] is False


def test_supported_track_gets_bounded_budget_not_pitch_authority():
    profile={'support':{'grade':'STRONG','styles':12,'notes':3000}}
    intent={'track_intents':[{'track':1,'channel':1,'label':'ROOT','confidence':.95}]}
    plan=build_musical_decision_plan({(1,0):_ctx()}, {(1,0):profile}, intent, ticks_per_beat=192)
    row=plan['tracks'][0]
    assert row['ood_status']=='NORMAL'
    assert row['mutation_budget']['velocity_delta']>0
    assert row['mutation_budget']['timing_delta_ticks']>0
    assert row['pitch_harmony_authority'] is False


def test_budget_audit_fails_closed_on_excessive_timing():
    profile={'support':{'grade':'GOOD','styles':8,'notes':1000}}
    plan=build_musical_decision_plan({(1,0):_ctx()}, {(1,0):profile}, {}, ticks_per_beat=192)
    key=(1,0,48,0)
    before={'notes':{key:{'onset':100,'off':160,'velocity':80,'pitch':48}}}
    note=NoteEvent(1,0,48,80,200,260,0,1,0)
    audit=audit_performance_budget(before,[note],plan)
    assert audit['pass'] is False
    assert audit['violations_by_dimension']['timing']>=1


def test_recovery_record_is_bounded_and_machine_readable():
    rec=recovery_record(stage='TIMING',reason='neural_inference_failure',action='FACTORY_FALLBACK',error=RuntimeError('x'*800),changes_rolled_back=3)
    assert rec['pass'] is True
    assert rec['changes_rolled_back']==3
    assert len(rec['error'])<600


def test_effective_budget_uses_most_restrictive_phrase_scope():
    from pa800_optimizer.premium_control import effective_mutation_budget
    row={'mutation_budget':{'velocity_delta':20,'timing_delta_ticks':12,'gate_duration_delta_ticks':48},
         'section_mutation_budgets':[{'start_tick':0,'end_tick':800,'mutation_budget':{'velocity_delta':15,'timing_delta_ticks':9,'gate_duration_delta_ticks':36}}],
         'phrase_mutation_budgets':[{'start_tick':100,'end_tick':300,'mutation_budget':{'velocity_delta':10,'timing_delta_ticks':6,'gate_duration_delta_ticks':24}}]}
    assert effective_mutation_budget(row,200)['velocity_delta']==10
    assert effective_mutation_budget(row,600)['velocity_delta']==15
