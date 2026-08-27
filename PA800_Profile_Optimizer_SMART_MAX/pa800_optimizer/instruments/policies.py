"""Runtime mutation policy by normalized instrument family.

Missing/heterogeneous families deliberately fall back to velocity-only.  SFX
and UNKNOWN never receive generic note shaping.
"""

POLICIES={
    'DRUM_KIT': {'velocity':True,'timing':True,'gate':False,'per_key':True},
    'PERCUSSION': {'velocity':True,'timing':True,'gate':False,'per_key':True},
    'PERCUSSIVE': {'velocity':True,'timing':True,'gate':False},
    'BASS': {'velocity':True,'timing':True,'gate':True,'per_key':False},
    'GUITAR': {'velocity':True,'timing':True,'gate':True,'per_key':False,'protect_special_pitch':True},
    'PIANO': {'velocity':True,'timing':True,'gate':True,'protect_cc64':True},
    'ACCORDION': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True},
    'HARMONICA': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True},
    'STRINGS': {'velocity':True,'timing':True,'gate':True,'articulation_split':True,'phrase_first':True},
    'ENSEMBLE': {'velocity':True,'timing':True,'gate':True,'phrase_first':True},
    'CHOIR_VOICE': {'velocity':True,'timing':False,'gate':True,'phrase_first':True},
    'BRASS': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True},
    'REED': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True},
    'PIPE': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True},
    'ORGAN': {'velocity':True,'timing':True,'gate':True,'velocity_limited':True},
    'SYNTH_PAD': {'velocity':True,'timing':False,'gate':True,'phrase_first':True},
    'SYNTH_LEAD': {'velocity':True,'timing':True,'gate':True,'protect_pb_cc1':True,'exact_only':True},
    'CHROMATIC_PERC': {'velocity':True,'timing':True,'gate':False,'exact_only':True,'transient':True},
    'MALLET': {'velocity':True,'timing':True,'gate':False,'exact_only':True,'transient':True},
    'PLUCK': {'velocity':True,'timing':True,'gate':False,'exact_only':True,'transient':True},
    'ETHNIC': {'velocity':True,'timing':False,'gate':False,'exact_only':True},
    'OTHER_ACC': {'velocity':True,'timing':False,'gate':False,'exact_only':True},
    'OTHER': {'velocity':True,'timing':False,'gate':False,'exact_only':True},
    'SFX': {'velocity':False,'timing':False,'gate':False,'protected':True},
    'SYNTH_FX': {'velocity':False,'timing':False,'gate':False,'protected':True},
    'UNKNOWN': {'velocity':False,'timing':False,'gate':False,'protected':True},
}

ALIASES={'PAD':'SYNTH_PAD','WOODWIND':'REED','ACCORDION_REED':'ACCORDION'}
DEFAULT_POLICY={'velocity':True,'timing':False,'gate':False,'fallback':True}

# Detailed behavior consumed by the existing velocity/timing/gate/performance
# engines. These are bounded modifiers, never generic replacement presets.
APPLICATION_DETAILS={
    'DRUM_KIT':{'timing_scale':1.00,'gate_scale':0.0,'timing_mode':'PER_KEY_GROOVE','gate_mode':'ONE_SHOT_PRESERVE','group_mode':'KIT_KEY','authority_head':'DRUM_PATTERN','controllers':'PRESERVE'},
    'PERCUSSION':{'timing_scale':.90,'gate_scale':0.0,'timing_mode':'PER_KEY_POCKET','gate_mode':'ONE_SHOT_PRESERVE','group_mode':'KIT_KEY','authority_head':'DRUM_PATTERN','controllers':'PRESERVE'},
    'PERCUSSIVE':{'timing_scale':.85,'gate_scale':0.0,'timing_mode':'TRANSIENT_POCKET','gate_mode':'TRANSIENT_PRESERVE','group_mode':'REPEATED_HIT','authority_head':'DRUM_PATTERN','controllers':'PRESERVE'},
    'BASS':{'timing_scale':.90,'gate_scale':.95,'timing_mode':'DRUM_ANCHORED_LINE','gate_mode':'NEXT_ONSET_ARTICULATION','group_mode':'MONO_LINE','authority_head':'BASS_PATTERN','controllers':'PRESERVE'},
    'GUITAR':{'timing_scale':.75,'gate_scale':.72,'timing_mode':'COHERENT_STRUM_OR_RIFF','gate_mode':'STRUM_RELEASE','group_mode':'NEAR_ONSET_CHORD','authority_head':'GUITAR_STRUM','controllers':'RX_DNC_PRESERVE'},
    'PIANO':{'timing_scale':.52,'gate_scale':.68,'timing_mode':'COHERENT_CHORD_OR_LINE','gate_mode':'PEDAL_AWARE_RELEASE','group_mode':'EXACT_CHORD','authority_head':'FACTORY_PROFILE','controllers':'CC64_PRESERVE'},
    'ACCORDION':{'timing_scale':.52,'gate_scale':.72,'timing_mode':'BELLOWS_PHRASE','gate_mode':'LEGATO_BELLOWS','group_mode':'PHRASE','authority_head':'SOLO_PHRASE','controllers':'CC1_CC2_PB_PRESERVE'},
    'HARMONICA':{'timing_scale':.48,'gate_scale':.66,'timing_mode':'BREATH_PHRASE','gate_mode':'BREATH_LEGATO','group_mode':'PHRASE','authority_head':'SOLO_PHRASE','controllers':'CC1_CC2_PB_PRESERVE'},
    'STRINGS':{'timing_scale':.32,'gate_scale':.35,'timing_mode':'SECTION_CHORD_PRESERVE','gate_mode':'SUSTAIN_TAIL_PRESERVE','group_mode':'EXACT_CHORD','authority_head':'STRINGS_PAD_PATTERN','controllers':'SUSTAIN_PRESERVE'},
    'ENSEMBLE':{'timing_scale':.35,'gate_scale':.38,'timing_mode':'COHERENT_ENSEMBLE','gate_mode':'VOICE_LEADING_SUSTAIN','group_mode':'EXACT_CHORD_AND_PHRASE','authority_head':'STRINGS_PAD_PATTERN','controllers':'SUSTAIN_PRESERVE'},
    'CHOIR_VOICE':{'timing_scale':0.0,'gate_scale':.30,'timing_mode':'PHRASE_ONSET_PRESERVE','gate_mode':'BREATH_AND_TAIL','group_mode':'PHRASE','authority_head':'STRINGS_PAD_PATTERN','controllers':'EXPRESSION_PRESERVE'},
    'BRASS':{'timing_scale':.58,'gate_scale':.62,'timing_mode':'STAB_OR_BREATH_PHRASE','gate_mode':'STAB_VS_SUSTAIN','group_mode':'CHORD_OR_PHRASE','authority_head':'BRASS_PATTERN','controllers':'CC1_PB_AT_PRESERVE'},
    'REED':{'timing_scale':.52,'gate_scale':.68,'timing_mode':'BREATH_SOLO_PHRASE','gate_mode':'LEGATO_BREATH','group_mode':'PHRASE_OR_ORNAMENT','authority_head':'SOLO_PHRASE','controllers':'CC1_CC2_PB_PRESERVE'},
    'PIPE':{'timing_scale':.48,'gate_scale':.66,'timing_mode':'AIR_SOLO_PHRASE','gate_mode':'BREATH_GAP','group_mode':'PHRASE_OR_ORNAMENT','authority_head':'SOLO_PHRASE','controllers':'CC1_CC2_PB_PRESERVE'},
    'ORGAN':{'timing_scale':.28,'gate_scale':.28,'timing_mode':'LEGATO_OR_STAB','gate_mode':'LEGATO_STATE_PRESERVE','group_mode':'CHORD_OR_LINE','authority_head':'FACTORY_PROFILE','controllers':'DRAWBAR_STATE_PRESERVE'},
    'SYNTH_PAD':{'timing_scale':0.0,'gate_scale':.25,'timing_mode':'ONSET_PRESERVE','gate_mode':'LONG_TAIL_PRESERVE','group_mode':'SUSTAIN_LAYER','authority_head':'STRINGS_PAD_PATTERN','controllers':'STATE_PRESERVE'},
    'SYNTH_LEAD':{'timing_scale':.48,'gate_scale':.62,'timing_mode':'EXPRESSIVE_SOLO','gate_mode':'LEGATO_ORNAMENT','group_mode':'PHRASE_OR_ORNAMENT','authority_head':'SOLO_PHRASE','controllers':'CC1_PB_AT_PRESERVE'},
    'CHROMATIC_PERC':{'timing_scale':.72,'gate_scale':0.0,'timing_mode':'PITCHED_TRANSIENT','gate_mode':'TRANSIENT_TAIL_PRESERVE','group_mode':'HIT_PATTERN','authority_head':'FACTORY_PROFILE','controllers':'PRESERVE'},
    'MALLET':{'timing_scale':.68,'gate_scale':0.0,'timing_mode':'MALLET_TRANSIENT','gate_mode':'NATURAL_DECAY_PRESERVE','group_mode':'HIT_PATTERN','authority_head':'FACTORY_PROFILE','controllers':'PRESERVE'},
    'PLUCK':{'timing_scale':.65,'gate_scale':0.0,'timing_mode':'PLUCK_TRANSIENT','gate_mode':'NATURAL_DECAY_PRESERVE','group_mode':'LINE_OR_ARPEGGIO','authority_head':'FACTORY_PROFILE','controllers':'PRESERVE'},
    'ETHNIC':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'EXACT_EVIDENCE_ONLY','gate_mode':'CULTURAL_ARTICULATION_PRESERVE','group_mode':'PHRASE','authority_head':'SOLO_PHRASE','controllers':'SPECIAL_PITCH_PRESERVE'},
    'OTHER_ACC':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'PRESERVE_UNKNOWN_TECHNIQUE','gate_mode':'PRESERVE','group_mode':'UNKNOWN','authority_head':'NO_EVIDENCE','controllers':'PRESERVE'},
    'OTHER':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'PRESERVE_UNKNOWN_TECHNIQUE','gate_mode':'PRESERVE','group_mode':'UNKNOWN','authority_head':'NO_EVIDENCE','controllers':'PRESERVE'},
    'SFX':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'PERMANENT_PRESERVE','gate_mode':'PERMANENT_PRESERVE','group_mode':'RAW_EVENT','authority_head':'NO_EVIDENCE','controllers':'RAW_EVENT_PRESERVE'},
    'SYNTH_FX':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'PERMANENT_PRESERVE','gate_mode':'PERMANENT_PRESERVE','group_mode':'RAW_EVENT','authority_head':'NO_EVIDENCE','controllers':'RAW_EVENT_PRESERVE'},
    'UNKNOWN':{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'PERMANENT_PRESERVE','gate_mode':'PERMANENT_PRESERVE','group_mode':'UNKNOWN','authority_head':'NO_EVIDENCE','controllers':'RAW_EVENT_PRESERVE'},
}
FAMILY_CUMULATIVE_VELOCITY_CAP={
    'PIANO':40,'BASS':24,'GUITAR':28,'BRASS':18,'REED':16,'PIPE':16,
    'HARMONICA':14,'ACCORDION':14,'SYNTH_LEAD':16,'STRINGS':16,
    'ENSEMBLE':16,'SYNTH_PAD':14,'CHOIR_VOICE':14,'ORGAN':12,
    'DRUM_KIT':18,'PERCUSSION':18,'PERCUSSIVE':18,
}


def policy_for(family):
    requested=str(family or 'UNKNOWN').upper();normalized=ALIASES.get(requested,requested)
    policy=dict(POLICIES.get(normalized,DEFAULT_POLICY));policy.update(APPLICATION_DETAILS.get(normalized,{'timing_scale':0.0,'gate_scale':0.0,'timing_mode':'FALLBACK_PRESERVE','gate_mode':'FALLBACK_PRESERVE','group_mode':'UNKNOWN','authority_head':'NO_EVIDENCE','controllers':'PRESERVE'}));policy['requested_family']=requested;policy['policy_family']=normalized if normalized in POLICIES else 'DEFAULT'
    return policy


def normalized_family(family):
    return policy_for(family)['policy_family']


def profile_evidence_allows_mutation(policy,profile):
    if not policy.get('exact_only'):return True
    if not profile or profile.get('_velocity_basis')=='FACTORY_FAMILY_AGGREGATE':return False
    support=profile.get('support') or {};grade=str(support.get('grade','UNKNOWN')).upper();stability=str(profile.get('_profile_stability','UNKNOWN')).upper()
    return grade in ('STRONG','GOOD') and stability in ('STABLE','MODERATE')
