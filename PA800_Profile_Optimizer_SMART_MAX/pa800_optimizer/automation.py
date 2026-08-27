from __future__ import annotations

from dataclasses import asdict,dataclass

from .config import OptimizeConfig


@dataclass
class AutomationDecision:
    mode: str
    smart_policy: str
    exact_note_coverage: float
    trusted_note_coverage: float
    conflict_note_fraction: float
    sensitive_note_fraction: float
    total_notes: int
    reasons: list[str]

    def to_dict(self):return asdict(self)


def decide_automation(contexts,notes,registry,detection):
    counts={};total=len(notes)
    for n in notes:counts[(n.track_index,n.channel)]=counts.get((n.track_index,n.channel),0)+1
    exact=trusted=conflict=sensitive=0
    for key,count in counts.items():
        ctx=contexts.get(key)
        if not ctx:continue
        if ctx.identity.conflict:conflict+=count;continue
        p,status=registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role)
        if p:
            exact+=count
            if hasattr(registry,'auto_candidate_allowed'):
                is_trusted,_reason=registry.auto_candidate_allowed(p)
            else:
                support=p.get('support',{})
                is_trusted=support.get('grade') in ('STRONG','GOOD') and int(support.get('styles',0))>=5
            if is_trusted:trusted+=count
        if ctx.identity.rx_named or ctx.identity.dnc_named:sensitive+=count
    den=max(1,total);exact_cov=exact/den;trusted_cov=trusted/den;conflict_frac=conflict/den;sensitive_frac=sensitive/den
    reasons=[f'exact_note_coverage={exact_cov:.3f}',f'trusted_note_coverage={trusted_cov:.3f}',f'conflict_note_fraction={conflict_frac:.3f}',f'sensitive_note_fraction={sensitive_frac:.3f}',f'content_confidence={float(detection.get("confidence",0)):.3f}']
    if not total:
        mode,smart='preserve','off';reasons.append('no_note_events')
    elif detection.get('ambiguous') or float(detection.get('confidence',0))<0.70:
        mode,smart='preserve','suggest';reasons.append('ambiguous_content_guard')
    elif conflict_frac>0 or exact_cov<0.35:
        mode,smart='preserve','suggest';reasons.append('identity_or_profile_coverage_guard')
    elif exact_cov<0.60 or trusted_cov<0.35:
        mode='natural';smart='apply' if exact_cov>=0.90 and conflict_frac==0 and sensitive_frac<0.10 else 'suggest';reasons.append('limited_current_profile_support_with_per_context_smart_gate')
    elif exact_cov<0.85 or trusted_cov<0.60:
        mode='live';smart='apply' if exact_cov>=0.90 and conflict_frac==0 and sensitive_frac<0.10 else 'suggest';reasons.append('moderate_factory_support')
    elif detection.get('content_type')=='style' and exact_cov>=0.99 and trusted_cov>=0.95 and sensitive_frac==0 and total>=500:
        mode,smart='max','apply';reasons.append('maximum_confidence_style_factory_corridor')
    elif detection.get('content_type')=='style' and exact_cov>=0.95 and trusted_cov>=0.82 and sensitive_frac<0.20 and total>=200:
        mode,smart='strong','apply';reasons.append('high_confidence_style_factory_corridor')
    else:
        mode='live';smart='apply' if trusted_cov>=0.75 and sensitive_frac<0.40 else 'suggest';reasons.append('high_confidence_safe_corridor')
    return AutomationDecision(mode,smart,round(exact_cov,6),round(trusted_cov,6),round(conflict_frac,6),round(sensitive_frac,6),total,reasons)


def materialize_config(source,decision):
    cfg=OptimizeConfig.for_mode(decision.mode)
    for name in ('seed','protect_rx_low_velocity','protect_rx_special_pitch','enable_velocity','enable_timing','enable_gate','content_type','use_factory_velocity_semantics','enable_midi_repair','enable_velocity_conductor','enable_articulation_director','apply_articulation_triggers','auto_apply_safe_voice_upgrades','hardware_calibration_path','velocity_min_iqr_retention','drum_key_min_hits','drum_key_min_styles','voice_hardware_whitelist_path','enable_performance_director','apply_performance_director','hardware_evidence_path','voice_aesthetic','enable_mix_fx_director','apply_mix_fx_director','mix_fx_policy','export_preset','factory_gold_max','apply_baja_stage_profile','test_full_optimization','velocity_factory_data_only','enable_rhythm_trill_correction','apply_trained_rhythm_model','trained_rhythm_model_path','trained_rhythm_only','ai_resource_policy'):
        setattr(cfg,name,getattr(source,name))
    policy=source.smart_policy_override or decision.smart_policy
    if decision.mode=='preserve' and policy=='apply':policy='suggest'
    if decision.mode=='preserve':cfg.lock_preserve()
    cfg.enable_sound_kit_selector=policy!='off';cfg.enable_fx_intelligence=policy!='off'
    cfg.apply_high_confidence_sound_changes=policy=='apply';cfg.apply_existing_fx_sends=policy=='apply';cfg.preserve_controllers=policy!='apply'
    cfg.smart_policy_override=source.smart_policy_override
    cfg.autopilot=source.autopilot
    return cfg,policy