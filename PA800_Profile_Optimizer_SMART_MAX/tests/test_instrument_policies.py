from pa800_optimizer.instruments.policies import policy_for,profile_evidence_allows_mutation


def test_rhythmic_and_tonal_families_have_explicit_policies():
    assert policy_for('DRUM_KIT')['per_key']
    assert policy_for('BASS')['gate']
    assert policy_for('GUITAR')['protect_special_pitch']
    assert policy_for('PIANO')['protect_cc64']
    assert policy_for('BRASS')['protect_pb_cc1']
    assert policy_for('CHOIR_VOICE')['phrase_first']


def test_aliases_and_safe_fallbacks_are_deterministic():
    assert policy_for('PAD')['policy_family']=='SYNTH_PAD'
    assert policy_for('WOODWIND')['policy_family']=='REED'
    assert policy_for('ACCORDION_REED')['policy_family']=='ACCORDION'
    fallback=policy_for('unlisted_family')
    assert {key:fallback[key] for key in ('velocity','timing','gate','fallback','requested_family','policy_family')}=={
        'velocity':True,'timing':False,'gate':False,'fallback':True,
        'requested_family':'UNLISTED_FAMILY','policy_family':'DEFAULT'}
    assert fallback['timing_scale']==0.0 and fallback['gate_scale']==0.0


def test_every_explicit_family_has_detailed_application_contract():
    required={'timing_scale','gate_scale','timing_mode','gate_mode','group_mode','authority_head','controllers'}
    families=('DRUM_KIT','PERCUSSION','PERCUSSIVE','BASS','GUITAR','PIANO','ACCORDION','HARMONICA','STRINGS','ENSEMBLE','CHOIR_VOICE','BRASS','REED','PIPE','ORGAN','SYNTH_PAD','SYNTH_LEAD','CHROMATIC_PERC','MALLET','PLUCK','ETHNIC','OTHER_ACC','OTHER','SFX','SYNTH_FX','UNKNOWN')
    for family in families:
        policy=policy_for(family)
        assert required<=set(policy),family
        assert 0.0<=policy['timing_scale']<=1.0
        assert 0.0<=policy['gate_scale']<=1.0


def test_unknown_and_effect_families_block_generic_note_shaping():
    for family in ('UNKNOWN','SFX','SYNTH_FX'):
        policy=policy_for(family)
        assert not policy['velocity'] and not policy['timing'] and not policy['gate']
        assert policy['protected']


def test_rare_families_require_strong_or_good_stable_exact_profile():
    policy=policy_for('ETHNIC');assert policy['exact_only']
    assert not profile_evidence_allows_mutation(policy,{'support':{'grade':'FALLBACK'},'_profile_stability':'STABLE'})
    assert not profile_evidence_allows_mutation(policy,{'support':{'grade':'GOOD'},'_profile_stability':'CONTEXT_DEPENDENT'})
    assert profile_evidence_allows_mutation(policy,{'support':{'grade':'GOOD'},'_profile_stability':'MODERATE'})
