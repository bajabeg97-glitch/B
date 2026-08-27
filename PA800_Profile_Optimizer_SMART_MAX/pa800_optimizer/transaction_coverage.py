"""Runtime audit proving mutation-capable domains use bounded transaction paths."""
from __future__ import annotations


def audit_transaction_coverage(config, report):
    ws=getattr(report,'workstation',{}) or {}
    repair=getattr(report,'midi_repair',{}) or {}
    art=getattr(report,'articulations',{}) or {}
    rows=[]
    def add(domain, enabled, evidence, transactional=True):
        ok=(not enabled) or (bool(evidence) and bool(transactional))
        rows.append({'domain':domain,'enabled':bool(enabled),'transactional':bool(transactional),'evidence':bool(evidence),'pass':ok})
    add('MIDI_DOCTOR',getattr(config,'enable_midi_repair',False),repair.get('transaction',{}).get('commit_authorized',False) if getattr(config,'enable_midi_repair',False) else True)
    add('SOUND_ADDRESS',getattr(config,'enable_sound_kit_selector',False) or getattr(config,'apply_baja_stage_profile',False),ws.get('structural_sound_transaction') is not None)
    add('ARTICULATION_INSERT',getattr(config,'enable_articulation_director',False) and getattr(config,'apply_articulation_triggers',False),bool((art.get('structural_transaction') or {}).get('canonical_replay',{}).get('pass',False)) if art.get('inserted_events',0) else True)
    legacy_fx=bool(getattr(config,'enable_fx_intelligence',False) and not getattr(config,'enable_mix_fx_director',False) and getattr(config,'apply_existing_fx_sends',False) and not getattr(config,'preserve_controllers',True))
    add('LEGACY_FX_CC91_93',legacy_fx,ws.get('legacy_fx_transaction') is not None)
    mix_fx=bool(getattr(config,'enable_mix_fx_director',False) and getattr(config,'enable_fx_intelligence',False))
    add('MIX_FX_CC91_93',mix_fx,ws.get('mix_fx_proposal_commit') is not None)
    perf=bool(getattr(config,'enable_velocity',False) or getattr(config,'enable_timing',False) or getattr(config,'enable_gate',False))
    add('CORE_NOTE_PERFORMANCE',perf,ws.get('event_proposal_commit') is not None)
    refiners=bool(getattr(config,'enable_velocity_conductor',False) or getattr(config,'apply_performance_director',False) or getattr(config,'apply_baja_stage_profile',False))
    add('PERFORMANCE_REFINERS',refiners,ws.get('refiner_event_commit') is not None and ws.get('refiner_controller_commit') is not None)
    add('CUMULATIVE_VELOCITY_BUDGET',perf,bool((ws.get('velocity_budget_projection') or {}).get('commit')))
    failures=[r for r in rows if not r['pass']]
    return {'schema':'PA800_TRANSACTION_COVERAGE_AUDIT_V1','domains':rows,'failures':failures,'pass':not failures,
            'mutation_domains':len(rows),'covered_domains':sum(1 for r in rows if r['pass'])}
