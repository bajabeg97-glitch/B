"""Central evidence and safety rules for every mutation class."""
from __future__ import annotations

from dataclasses import asdict,dataclass


EVIDENCE_RANK={'E0':0,'E1':1,'E2':2,'E3':3}
RULES={
    'STRUCTURAL_REPAIR':{'min':'E2','sensitive':True,'preserve':True},
    'VELOCITY_PROFILE':{'min':'E1','sensitive':False,'preserve':True},
    'TIMING_PROFILE':{'min':'E2','sensitive':False,'preserve':True},
    'GATE_PROFILE':{'min':'E2','sensitive':False,'preserve':True},
    'NEURAL_TIMING_EXPLICIT':{'min':'E2','sensitive':False,'preserve':False},
    'NEURAL_GATE_EXPLICIT':{'min':'E2','sensitive':False,'preserve':False},
    'PERFORMANCE_SECTION':{'min':'E2','sensitive':False,'preserve':False},
    'EXPRESSION_EXISTING_CC11':{'min':'E2','sensitive':False,'preserve':False},
    'SOUND_SAFE_GM':{'min':'E2','sensitive':False,'preserve':False},
    'SOUND_BROAD':{'min':'E3','sensitive':False,'preserve':False},
    'FX_DRY_GUARD':{'min':'E1','sensitive':False,'preserve':False},
    'FX_SECTION_DEPTH':{'min':'E3','sensitive':False,'preserve':False},
    'ARTICULATION_DOCUMENTED':{'min':'E2','sensitive':True,'preserve':False},
    'ARTICULATION_EXPRESSIVE':{'min':'E3','sensitive':True,'preserve':False},
    'INSERT_MASTER_FX':{'min':'E3','sensitive':False,'preserve':False,'never_auto':True},
}

NEURAL_ALLOWED_NOTE_KINDS={'timing','gate'}
FACTORY_ONLY_NOTE_KINDS={'velocity','velocity_conductor','velocity_budget','performance_velocity'}


def audit_neural_factory_boundary(report,config):
    """Fail closed if an explicit neural pass crosses into Factory authority."""
    applicable=bool(getattr(config,'apply_trained_rhythm_model',False));changes=list(getattr(report,'changes',[]) or []);verifier=getattr(report,'verifier',{}) or {};summary=(getattr(report,'workstation',{}) or {}).get('trained_rhythm_application',{})
    if not applicable:return {'schema':'PA800_NEURAL_FACTORY_AUTHORITY_V1','applicable':False,'pass':True,'checks':{},'violations':[]}
    neural_changes=[change for change in changes if str(getattr(change,'reason','')).startswith('explicit_trained_')]
    # In trained_rhythm_only mode the whole mutation pass is a neural timing/gate
    # sandbox: any velocity/performance mutation or sound rewrite is a boundary
    # violation, even if a buggy caller forgot the explicit_trained_ reason prefix.
    scoped_changes=changes if bool(getattr(config,'trained_rhythm_only',False)) else neural_changes
    forbidden_note=[change for change in scoped_changes if getattr(change,'kind',None) not in NEURAL_ALLOWED_NOTE_KINDS]
    velocity_unchanged=not any(getattr(change,'kind',None) in FACTORY_ONLY_NOTE_KINDS or getattr(change,'kind',None)=='baja_percussion_40pct' for change in scoped_changes) and int(summary.get('velocity_features_applied',-1))==0
    sound_rewrites=sum(str(row.get('sound_apply_status','')).startswith('applied') for row in (getattr(report,'intelligence',[]) or []))
    no_sound_rewrite=(sound_rewrites==0 and int(verifier.get('authorized_sound_channels',0))==0 and int(summary.get('sound_kit_features_applied',0))==0)
    checks={
        'only_timing_and_gate_note_changes':not forbidden_note,
        'factory_velocity_unchanged':velocity_unchanged,
        'factory_velocity_not_written_by_neural':velocity_unchanged,
        'pitch_harmony_unchanged':int(summary.get('pitch_features_applied',-1))==0,
        'voice_model_output_unused':int(summary.get('voice_settings_applied',-1))==0,
        'no_sound_or_kit_rewrite':no_sound_rewrite,
        'neural_sound_or_kit_output_unused':int(summary.get('sound_kit_features_applied',0))==0,
        'neural_voice_articulation_output_unused':int(summary.get('articulation_features_applied',0))==0,
        'neural_fx_expression_output_unused':int(summary.get('fx_features_applied',0))==0 and int(summary.get('expression_features_applied',0))==0,
        'explicit_user_authority_recorded':summary.get('explicit_user_authority') is True,
    }
    violations=[name for name,value in checks.items() if not value]
    return {'schema':'PA800_NEURAL_FACTORY_AUTHORITY_V1','applicable':True,'pass':not violations,'checks':checks,'violations':violations,'allowed_note_kinds':sorted(NEURAL_ALLOWED_NOTE_KINDS),'factory_only_note_kinds':sorted(FACTORY_ONLY_NOTE_KINDS)}


@dataclass
class AuthorityDecision:
    mutation: str
    evidence_level: str
    applied: bool
    allowed: bool
    reason: str
    track: int | None = None
    channel: int | None = None
    count: int = 0
    source: str = ''

    def to_dict(self):return asdict(self)


def authorize(mutation,evidence_level,*,applied=False,conflict=False,sensitive=False,preserve_preset=False,track=None,channel=None,count=0,source=''):
    rule=RULES[mutation];evidence=str(evidence_level or 'E0').upper();allowed=True;reason='authority_granted'
    if rule.get('never_auto'):allowed=False;reason='serialization_or_hardware_schema_not_authorized'
    elif conflict:allowed=False;reason='identity_or_multi_program_conflict'
    elif sensitive and not rule.get('sensitive'):allowed=False;reason='rx_dnc_sensitive_context'
    elif preserve_preset and not rule.get('preserve'):allowed=False;reason='preserve_preset_blocks_creative_mutation'
    elif EVIDENCE_RANK.get(evidence,0)<EVIDENCE_RANK[rule['min']]:allowed=False;reason='requires_%s_or_higher'%rule['min']
    return AuthorityDecision(mutation,evidence,bool(applied),bool(allowed),reason,track,channel,int(count or 0),source)


def build_authority_ledger(report,config):
    preserve=str(getattr(config,'export_preset','auto'))=='preserve';decisions=[];contexts={(row.get('track'),row.get('channel')):row for row in report.contexts}
    repairs=(report.midi_repair or {}).get('repairs',[])
    if repairs:decisions.append(authorize('STRUCTURAL_REPAIR','E2',applied=True,count=len(repairs),source='midi_doctor'))
    note_change_counts={}
    for change in report.changes:
        trained=str(getattr(change,'reason','')).startswith('explicit_trained_')
        mutation='VELOCITY_PROFILE' if change.kind in ('velocity','velocity_conductor','velocity_budget') else 'NEURAL_TIMING_EXPLICIT' if trained and change.kind=='timing' else 'NEURAL_GATE_EXPLICIT' if trained and change.kind=='gate' else 'TIMING_PROFILE' if change.kind=='timing' else 'GATE_PROFILE' if change.kind=='gate' else 'PERFORMANCE_SECTION' if change.kind=='performance_velocity' else None
        if mutation:
            channel=None if change.channel is None else int(change.channel)+1
            protected=getattr(change,'protected',None)
            note_change_counts[(mutation,change.track,channel,change.profile or '',protected)]=note_change_counts.get((mutation,change.track,channel,change.profile or '',protected),0)+1
    for (mutation,track,channel,profile,protected),count in note_change_counts.items():
        context=contexts.get((track,channel)) if channel is not None else None
        if context is None:
            candidates=[row for row in report.contexts if row.get('track')==track]
            context=candidates[0] if len(candidates)==1 else {}
        evidence=str(context.get('evidence_level','E0'))
        conflict=bool(context.get('conflict')) or not context
        sensitive=protected is not False
        source=('explicit_user_neural_model' if mutation in ('NEURAL_TIMING_EXPLICIT','NEURAL_GATE_EXPLICIT') else 'performance_engines')+((':'+profile) if profile else '')
        decisions.append(authorize(mutation,evidence,applied=True,conflict=conflict,sensitive=sensitive,preserve_preset=preserve,track=track,channel=channel,count=count,source=source))
    for row in report.intelligence or []:
        status=str(row.get('sound_apply_status',''));applied=status.startswith('applied');action=row.get('action');mutation='SOUND_SAFE_GM' if action=='SAFE_GM_UPGRADE' else 'SOUND_BROAD'
        context=contexts.get((row.get('track'),row.get('channel')),{});decisions.append(authorize(mutation,row.get('evidence_level','E0'),applied=applied,conflict=bool(context.get('conflict')),sensitive=bool(row.get('current_sound') and ('RX' in str(row.get('current_sound')).upper() or 'DNC' in str(row.get('current_sound')).upper())),preserve_preset=preserve,track=row.get('track'),channel=row.get('channel'),count=1 if applied else 0,source='voice_director'))
        if int(row.get('fx_send_changes') or 0)>0 and not (report.mix_fx_director or {}).get('enabled'):
            decisions.append(authorize('FX_DRY_GUARD',row.get('evidence_level','E1'),applied=True,conflict=bool(context.get('conflict')),preserve_preset=preserve,track=row.get('track'),channel=row.get('channel'),count=row.get('fx_send_changes'),source='sound_fx_intelligence'))
    for row in (report.mix_fx_director or {}).get('contexts',[]):
        if not row.get('changes'):continue
        mutation='FX_SECTION_DEPTH' if row.get('apply_status')=='applied_e3_section_depth' else 'FX_DRY_GUARD';decisions.append(authorize(mutation,row.get('evidence_level','E0'),applied=True,preserve_preset=preserve,track=row.get('track'),channel=row.get('channel'),count=row.get('changes'),source='mix_fx_director'))
    for row in (report.performance_director or {}).get('solo_tracks',[]):
        if not row.get('expression_changes'):continue
        context=contexts.get((row.get('track'),row.get('channel')),{});decisions.append(authorize('EXPRESSION_EXISTING_CC11','E2',applied=True,conflict=bool(context.get('conflict')),preserve_preset=preserve,track=row.get('track'),channel=row.get('channel'),count=row.get('expression_changes'),source='gold_solo_expression_existing_cc11'))
    for context in (report.articulations or {}).get('contexts',[]):
        for row in context.get('suggestions',[]):
            if row.get('action')!='APPLY':continue
            documented=bool((row.get('control')==80 and 'slide' in str(row.get('semantic')).lower()) or (row.get('control')==81 and 'fall' in str(row.get('semantic')).lower()));mutation='ARTICULATION_DOCUMENTED' if documented else 'ARTICULATION_EXPRESSIVE';decisions.append(authorize(mutation,row.get('evidence_level','E0'),applied=True,sensitive=True,preserve_preset=preserve,track=row.get('track'),channel=row.get('channel'),count=2,source='articulation_director'))
    unauthorized=[row for row in decisions if row.applied and not row.allowed]
    return {'schema':'PA800_AUTHORITY_LEDGER_V1','rules':RULES,'decisions':[row.to_dict() for row in decisions],'applied_decisions':sum(row.applied for row in decisions),'unauthorized_applied':[row.to_dict() for row in unauthorized],'pass':not unauthorized}
