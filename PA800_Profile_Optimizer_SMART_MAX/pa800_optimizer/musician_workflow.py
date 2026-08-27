"""Musician-facing workflow, presets and dashboard cards.

This layer composes existing evidence-backed modules.  It may select a safe
configuration, but it never invents creative MIDI mutations or upgrades an E1
musical interpretation into mutation authority.
"""
from __future__ import annotations

from collections import Counter


MUSICAL_PRESETS={
    'custom':{'label':'Custom / technical controls','base_mode':'auto'},
    'original_preserve':{'label':'Original — samo razumij i sačuvaj','base_mode':'preserve'},
    'natural_band':{'label':'Natural Band — blaga ansambl obrada','base_mode':'natural'},
    'groove_first':{'label':'Groove First — čuvaj pocket','base_mode':'natural'},
    'vocal_backing':{'label':'Vocal Friendly — prostor za pjevača','base_mode':'natural'},
    'live_stage':{'label':'Live Stage — stabilno za nastup','base_mode':'live'},
    'creative_preview':{'label':'Creative Lab — prijedlozi bez primjene','base_mode':'gentle'},
}


def configure_musical_preset(config,name):
    """Apply bounded policy differences after a base mode was constructed."""
    name=(name or 'custom').lower()
    if name not in MUSICAL_PRESETS:raise ValueError('Unknown musical preset: %s' % name)
    config.musical_preset=name
    config.creative_policy='preview' if name=='creative_preview' else 'off'
    config.vocal_friendly_mode=name=='vocal_backing'
    config.live_performance_mode=name=='live_stage'
    if name=='groove_first':
        config.timing_strength=min(config.timing_strength,.12);config.gate_strength=min(config.gate_strength,.18)
        config.velocity_random_strength=min(config.velocity_random_strength,.20)
    if name=='vocal_backing':
        config.timing_strength=min(config.timing_strength,.12);config.gate_strength=min(config.gate_strength,.18)
        config.velocity_strength=min(config.velocity_strength,.28);config.velocity_random_strength=min(config.velocity_random_strength,.12)
        config.apply_performance_director=False;config.mix_fx_policy='shadow';config.apply_mix_fx_director=False
    if name=='live_stage':
        config.velocity_conductor_max_delta=min(config.velocity_conductor_max_delta,24)
        config.apply_high_confidence_sound_changes=False;config.apply_existing_fx_sends=False
        config.apply_articulation_triggers=False;config.apply_mix_fx_director=False
        config.smart_policy_override='suggest';config.mix_fx_policy='shadow';config.preserve_controllers=True
    if name=='creative_preview':
        config.apply_high_confidence_sound_changes=False;config.apply_existing_fx_sends=False
        config.apply_articulation_triggers=False;config.apply_performance_director=False;config.apply_mix_fx_director=False
        config.smart_policy_override='suggest';config.mix_fx_policy='shadow'
    return config


def vocal_protected_keys(musical_context,enabled):
    if not enabled:return set()
    return {(int(row['track']),int(row['channel'])-1) for row in musical_context.get('track_functions',[]) if row.get('function') in ('LEAD','COUNTER_LINE')}


def build_musician_workflow(config,musical_context,understanding,agent_mesh=None,song_map=None,phrase_doctor=None,repair_previews=None):
    functions=Counter(row.get('function','UNKNOWN') for row in musical_context.get('track_functions',[]))
    groove=understanding.get('groove',{}).get('relationships',[])
    sections=understanding.get('arrangement',{}).get('sections',[])
    interactions=understanding.get('interaction',{}).get('relationships',[])
    harmony=understanding.get('harmony',{})
    vocal_keys=vocal_protected_keys(musical_context,getattr(config,'vocal_friendly_mode',False))
    drum_tracks=[row for row in musical_context.get('track_functions',[]) if row.get('function') in ('FOUNDATION_DRUM','FOUNDATION_PERC')]
    creative=[]
    if getattr(config,'creative_policy','off')=='preview':
        if any(row.get('relationship')=='CALL_RESPONSE_CANDIDATE' for row in interactions):creative.append({'tool':'CALL_RESPONSE_SPACE','proposal':'Preserve the exchange; audition a response mute/answer variant.','apply_authority':False})
        if len(sections)>=2:creative.append({'tool':'SECTION_CONTRAST','proposal':'Audition density contrast between stable and build sections.','apply_authority':False})
        if harmony.get('voice_leading'):creative.append({'tool':'HARMONIC_REVOICE','proposal':'Preview smoother common-tone voicing; do not rewrite pitches automatically.','apply_authority':False})
        creative.append({'tool':'GROOVE_VARIATION','proposal':'Preview velocity-only variation while preserving measured Drum/Bass offsets.','apply_authority':False})
    cards={
        'groove_preserver':{'status':'ACTIVE' if groove else 'UNKNOWN','relationships':len(groove),'policy':'preserve measured Drum/Bass and grouped-onset fingerprints'},
        'instrument_roles':{'status':'ACTIVE' if functions else 'UNKNOWN','counts':dict(functions),'policy':'role is context, not automatic authority'},
        'section_awareness':{'status':'ACTIVE' if sections else 'UNKNOWN','sections':len(sections),'trajectory':[row.get('trajectory_from_previous') for row in sections]},
        'vocal_friendly':{'status':'ACTIVE' if getattr(config,'vocal_friendly_mode',False) else 'OFF','protected_foreground_contexts':len(vocal_keys),'policy':'LEAD/COUNTER notes bypass velocity, timing and gate shaping'},
        'drum_intelligence':{'status':'ACTIVE' if drum_tracks else 'N/A','tracks':len(drum_tracks),'policy':'Pa800 Kit+Key evidence and special-pitch protection'},
        'harmonic_context':{'status':'ACTIVE' if harmony.get('chord_count') else 'UNKNOWN','chords':harmony.get('chord_count',0),'voice_leading_transitions':len(harmony.get('voice_leading',[])),'tonal_center':harmony.get('tonal_center',{}).get('name') or 'UNKNOWN'},
        'live_performance':{'status':'ACTIVE' if getattr(config,'live_performance_mode',False) else 'OFF','policy':'bounded dynamics, controller preserve, suggest-only Sound/FX/articulation'},
        'creative_tools':{'status':'PREVIEW' if creative else 'OFF','proposals':creative,'applied_mutations':0},
    }
    if agent_mesh:
        proposals={row.get('agent_id'):row for row in agent_mesh.get('proposals',[])}
        cards['codex_audit']={'status':proposals.get('codex_song_auditor',{}).get('requested_action','UNAVAILABLE'),'proposal':proposals.get('codex_song_auditor',{}).get('proposal_id'),'apply_authority':False}
        cards['chatgpt_music_review']={'status':proposals.get('chatgpt_musical_critic',{}).get('requested_action','UNAVAILABLE'),'proposal':proposals.get('chatgpt_musical_critic',{}).get('proposal_id'),'apply_authority':False}
        cards['agent_consensus']={'status':agent_mesh.get('consensus','UNAVAILABLE'),'mesh_digest':agent_mesh.get('mesh_digest'),'applied_mutations':0,'apply_authority':False}
    if song_map:
        summary=song_map.get('summary',{})
        cards['song_map']={'status':'ACTIVE' if summary.get('sections') else 'UNKNOWN','bars':summary.get('bars',0),'sections':summary.get('sections',0),'phrases':summary.get('phrases',0),'dependencies':summary.get('dependencies',0),'apply_authority':False}
    if phrase_doctor:
        summary=phrase_doctor.get('summary',{})
        cards['phrase_doctor']={'status':'SHADOW','phrases':summary.get('phrases_considered',0),'findings':summary.get('findings',0),'apply_authority':False,'applied_mutations':0}
    if repair_previews:
        summary=repair_previews.get('summary',{})
        cards['repair_previews']={'status':'AUDITION','previews':summary.get('previews',0),'candidates':summary.get('candidates',0),'apply_authority':False,'applied_mutations':0}
    return {'schema':'PA800_MUSICIAN_WORKFLOW_V1','preset':getattr(config,'musical_preset','custom'),'preset_label':MUSICAL_PRESETS.get(getattr(config,'musical_preset','custom'),MUSICAL_PRESETS['custom'])['label'],'analyzer_only':True,'authority_granted':False,'creative_mutations':0,'vocal_protected_keys':[{'track':key[0],'channel':key[1]+1} for key in sorted(vocal_keys)],'cards':cards,'dashboard_order':list(cards),'limits':['Section and role labels remain E1 until ground-truth validation.','Creative proposals are audition ideas, not MIDI mutation commands.']}


def render_dashboard(workflow):
    lines=[workflow.get('preset_label','Musician Workflow'),'-'*72]
    for name in workflow.get('dashboard_order',[]):
        card=workflow.get('cards',{}).get(name,{})
        lines.append(f"{name.replace('_',' ').title()}: {card.get('status','UNKNOWN')}")
        for key,value in card.items():
            if key not in ('status','proposals'):lines.append(f"  {key}: {value}")
        for proposal in card.get('proposals',[]):lines.append(f"  PREVIEW {proposal['tool']}: {proposal['proposal']}")
    lines.append('')
    lines.extend('LIMIT: '+item for item in workflow.get('limits',[]))
    return '\n'.join(lines)+'\n'