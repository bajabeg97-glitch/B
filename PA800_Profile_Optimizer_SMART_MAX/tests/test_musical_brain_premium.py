from types import SimpleNamespace
from pa800_optimizer.models import SoundIdentity, TrackContext, Change
from pa800_optimizer.musical_brain import build_musical_decision_plan
from pa800_optimizer.mutation_arbiter import audit_mutation_arbitration


def ctx(conflict=False):
    return TrackContext(1, 0, 'BASS', SoundIdentity(121,16,33,'Bass','BASS',conflict=conflict), family='BASS')


def test_decision_brain_preserves_unknown_profile():
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):None}, {})
    assert plan['tracks'][0]['action']=='PRESERVE'
    assert plan['tracks'][0]['pitch_harmony_authority'] is False


def test_decision_brain_allows_supported_profile_but_not_harmony():
    p={'support':{'grade':'STRONG','styles':12,'notes':3000}}
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):p}, {'track_intents':[{'track':1,'channel':1,'label':'ROOT','confidence':.95}]})
    row=plan['tracks'][0]
    assert row['action'] in ('NORMAL_CORRECT','STRONG_CORRECT')
    assert row['pitch_harmony_authority'] is False


def test_mutation_arbiter_accepts_velocity_stack_but_rejects_duplicate_timing():
    velocity=[Change(1,2,'velocity',50,60,'a',channel=0,note=48,occurrence=0),Change(1,2,'velocity_budget',60,58,'b',channel=0,note=48,occurrence=0)]
    assert audit_mutation_arbitration(velocity)['pass']
    timing=[Change(1,2,'timing',0,2,'a',channel=0,note=48,occurrence=0),Change(1,2,'timing',2,3,'b',channel=0,note=48,occurrence=0)]
    assert not audit_mutation_arbitration(timing)['pass']


def test_selective_budget_rollback_restores_only_violating_dimensions(tmp_path):
    import mido
    from pa800_optimizer.core.midi_io import extract_notes
    from pa800_optimizer.analysis.instrument_fingerprints import snapshot_instrument_state
    from pa800_optimizer.premium_control import apply_selective_budget_rollback, audit_performance_budget

    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.Message('note_on',channel=0,note=48,velocity=60,time=0))
    tr.append(mido.Message('note_off',channel=0,note=48,velocity=0,time=96))
    tr.append(mido.Message('note_on',channel=0,note=50,velocity=70,time=96))
    tr.append(mido.Message('note_off',channel=0,note=50,velocity=0,time=96))
    contexts={(0,0):TrackContext(0,0,'BASS',SoundIdentity(121,16,33,'Bass','BASS'),family='BASS')}
    before_notes=extract_notes(mid);baseline=snapshot_instrument_state(mid,before_notes,contexts)
    # First note violates velocity only; second violates timing and gate.
    ev=list(tr)
    ev[0]=ev[0].copy(velocity=100)
    # Absolute layout after edit: note2 starts much too late and is too long.
    ev[2]=ev[2].copy(time=180)
    ev[3]=ev[3].copy(time=180)
    tr[:]=ev
    plan={'tracks':[{'track':0,'channel':1,'mutation_budget':{'velocity_delta':8,'timing_delta_ticks':12,'gate_duration_delta_ticks':24}}]}
    audit=audit_performance_budget(baseline,extract_notes(mid),plan)
    assert not audit['pass']
    rep=apply_selective_budget_rollback(mid,baseline,plan)
    assert rep['rolled_notes']>=1
    after=extract_notes(mid)
    assert after[0].velocity==60
    assert audit_performance_budget(baseline,after,plan)['pass']


def test_phrase_and_section_budgets_only_tighten_track_budget():
    p={'support':{'grade':'STRONG','styles':12,'notes':3000}}
    song_map={'sections':[{'index':0,'label':'VERSE','start_tick':0,'end_tick':768,'evidence_level':'E1'}],
              'phrases':[{'id':'phrase:0','section_index':0,'track':1,'channel':1,'start_tick':0,'end_tick':384}]}
    phrase_doctor={'findings':[{'phrase_id':'phrase:0','kind':'VELOCITY_ANOMALY'}]}
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):p},
        {'track_intents':[{'track':1,'channel':1,'label':'ROOT','confidence':.95}]},
        song_map=song_map, phrase_doctor=phrase_doctor, ticks_per_beat=192)
    row=plan['tracks'][0]
    assert plan['schema']=='PA800_MUSICAL_DECISION_PLAN_V3'
    assert row['section_mutation_budgets'][0]['mutation_budget']['velocity_delta'] <= row['mutation_budget']['velocity_delta']
    assert row['phrase_mutation_budgets'][0]['mutation_budget']['velocity_delta'] <= row['section_mutation_budgets'][0]['mutation_budget']['velocity_delta']


def test_pre_apply_policy_forbids_neural_velocity_pitch_and_harmony():
    from pa800_optimizer.mutation_arbiter import build_pre_apply_mutation_policy
    p={'support':{'grade':'STRONG','styles':12,'notes':3000}}
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):p},
        {'track_intents':[{'track':1,'channel':1,'label':'ROOT','confidence':.95}]})
    policy=build_pre_apply_mutation_policy(plan, SimpleNamespace(apply_trained_rhythm_model=True))
    assert policy['pass']
    assert policy['neural_allowed_dimensions']==['timing','gate']
    assert 'velocity' in policy['neural_forbidden_dimensions']
    assert policy['tracks'][0]['dimensions']['pitch']['allowed'] is False
    assert policy['tracks'][0]['dimensions']['harmony']['allowed'] is False


def test_proposal_arbiter_v3_resolves_neural_to_timing_gate_only():
    from pa800_optimizer.mutation_arbiter import build_proposal_arbitration, filter_notes_by_proposal
    p={'support':{'grade':'STRONG','styles':12,'notes':3000}}
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):p},
        {'track_intents':[{'track':1,'channel':1,'label':'ROOT','confidence':.95}]})
    arb=build_proposal_arbitration(plan, SimpleNamespace(apply_trained_rhythm_model=True,enable_velocity=True,enable_timing=True,enable_gate=True))
    assert arb['schema']=='PA800_MUTATION_PROPOSAL_ARBITER_V3'
    assert arb['pass']
    row=arb['tracks'][0]
    assert row['resolved']['velocity']['winner']=='FACTORY_GOLD_DETERMINISTIC'
    assert row['resolved']['timing']['winner']=='NEURAL_ADVISOR'
    assert row['resolved']['gate']['winner']=='NEURAL_ADVISOR'
    assert row['execution_allowed']['pitch'] is False
    assert row['execution_allowed']['harmony'] is False


def test_proposal_arbiter_v3_hard_preserve_filters_every_mutable_dimension():
    from pa800_optimizer.mutation_arbiter import build_proposal_arbitration, filter_notes_by_proposal
    from pa800_optimizer.models import NoteEvent
    plan=build_musical_decision_plan({(1,0):ctx()}, {(1,0):None}, {})
    arb=build_proposal_arbitration(plan, SimpleNamespace(apply_trained_rhythm_model=True,enable_velocity=True,enable_timing=True,enable_gate=True))
    row=arb['tracks'][0]
    assert row['action']=='PRESERVE'
    assert not any(row['execution_allowed'][d] for d in ('velocity','timing','gate','pitch','harmony'))
    note=NoteEvent(1,0,48,80,0,96,0,1,0)
    assert filter_notes_by_proposal([note],arb,'velocity')==[]
    assert filter_notes_by_proposal([note],arb,'timing')==[]
    assert filter_notes_by_proposal([note],arb,'gate')==[]
