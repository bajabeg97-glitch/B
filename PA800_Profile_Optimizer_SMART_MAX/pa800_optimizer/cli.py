import argparse
from dataclasses import asdict
from .config import OptimizeConfig
from .optimizer import Optimizer
from .workstation import WorkstationSession,apply_export_preset,build_mixer_snapshot
from .musician_workflow import MUSICAL_PRESETS,configure_musical_preset,render_dashboard
from .neural.pattern_advisor import generate_chord_pattern

def main(argv=None):
    ap=argparse.ArgumentParser(description='PA800 Factory + Gold evidence-gated MIDI optimizer')
    ap.add_argument('input'); ap.add_argument('output'); ap.add_argument('--mode',default='auto',choices=['auto','preserve','gentle','natural','live','strong','max'],help='preserve is byte-preserving; gentle is the former low-strength profile pass')
    ap.add_argument('--musical-preset',default='custom',choices=list(MUSICAL_PRESETS),help='Musician-facing policy preset; replaces --mode defaults when selected')
    ap.add_argument('--vocal-friendly',action='store_true',help='Protect inferred LEAD/COUNTER foreground from note shaping')
    ap.add_argument('--live-performance',action='store_true',help='Bound dynamics and keep Sound/FX/articulation suggest-only for stage safety')
    ap.add_argument('--creative',default='off',choices=['off','preview'],help='Creative ideas are preview-only and never mutate MIDI')
    ap.add_argument('--report'); ap.add_argument('--seed',type=int,default=800)
    ap.add_argument('--content-type',default='auto',choices=['auto','style','song'])
    ap.add_argument('--smart',default='auto',choices=['auto','off','suggest','apply'],help='AUTO PILOT or explicit Sound/Kit+FX policy')
    ap.add_argument('--velocity-only',action='store_true'); ap.add_argument('--no-timing',action='store_true'); ap.add_argument('--no-gate',action='store_true')
    ap.add_argument('--no-repair',action='store_true',help='Disable deterministic MIDI Doctor repairs')
    ap.add_argument('--no-velocity-normalize',action='store_true',help='Disable final instrument-aware velocity normalization')
    ap.add_argument('--articulations',default='suggest',choices=['off','suggest','apply'],help='Exact DNC articulation policy; apply explicitly inserts documented CC80/CC81 pulses')
    ap.add_argument('--no-safe-voice-upgrades',action='store_true',help='Disable automatic same-program GM-to-Pa800 voice upgrades in AUTO mode')
    ap.add_argument('--hardware-calibration',help='JSON with confirmed per-address/per-family velocity offsets')
    ap.add_argument('--voice-whitelist',help='Hardware-approved Voice target JSON')
    ap.add_argument('--performance',default='shadow',choices=['off','shadow','apply'],help='Phrase/section Performance Director policy; Song E1 remains shadow-only')
    ap.add_argument('--aesthetic',default='original',choices=['original','natural','modern'],help='Voice candidate aesthetic target')
    ap.add_argument('--hardware-evidence',help='Versioned E3 hardware evidence registry JSON')
    ap.add_argument('--mix-fx',default='auto',choices=['auto','off','shadow','apply'],help='Ensemble Mix & FX Director policy; apply mutates only existing CC91/CC93')
    ap.add_argument('--export-preset',default='auto',choices=['auto','song','style','preserve'])
    ap.add_argument('--session',help='PA800_WORKSTATION_SESSION.json path')
    ap.add_argument('--variant-label',default='optimized')
    ap.add_argument('--audio-reference',help='Optional WAV/audio reference to attach to the committed variant')
    ap.add_argument('--test-full-optimization',action='store_true',help='Explicit audition mode: apply every non-destructive optimization path; RX/DNC, identity and verifier blocks remain active')
    ap.add_argument('--factory-gold-max',action='store_true',help='Velocity from Factory profiles only; timing/groove/strum/fill/solo/CC11 from Gold where evidence allows')
    ap.add_argument('--chords',help='Generate a chord-conditioned pattern, e.g. "C | Am | F | G7"; pitch-only explicit generator path')
    ap.add_argument('--no-solo-revoice',action='store_true',help='Preserve Solo/Lead pitches during --chords generation')
    ns=ap.parse_args(argv)
    if ns.chords:
        report=generate_chord_pattern(ns.input,ns.output,ns.chords,include_solo=not ns.no_solo_revoice,content_type=ns.content_type)
        print('PASS CHORD PATTERN: %s -> %s'%(ns.input,ns.output));print('Progression:',report['progression']);print('Summary:',report['summary']);print('Verifier:',report['verifier']);return
    cfg=OptimizeConfig.for_musical_preset(ns.musical_preset) if ns.musical_preset!='custom' else OptimizeConfig.for_mode(ns.mode)
    if ns.vocal_friendly:configure_musical_preset(cfg,'vocal_backing')
    if ns.live_performance:configure_musical_preset(cfg,'live_stage')
    if ns.creative=='preview':cfg.creative_policy='preview'
    cfg.seed=ns.seed; cfg.content_type=ns.content_type
    if ns.smart!='auto':
        requested_policy=ns.smart
        if requested_policy=='apply' and (ns.mode=='preserve' or ns.velocity_only):requested_policy='suggest'
        cfg.smart_policy_override=requested_policy
        cfg.enable_sound_kit_selector=ns.smart!='off'; cfg.enable_fx_intelligence=ns.smart!='off'
        apply_smart=requested_policy=='apply'
        cfg.apply_high_confidence_sound_changes=apply_smart; cfg.apply_existing_fx_sends=apply_smart
        cfg.preserve_controllers=not apply_smart
    else:
        apply_smart=False
    if ns.velocity_only: cfg.enable_timing=False; cfg.enable_gate=False
    if ns.no_timing: cfg.enable_timing=False
    if ns.no_gate: cfg.enable_gate=False
    if ns.no_repair:cfg.enable_midi_repair=False
    if ns.no_velocity_normalize:cfg.enable_velocity_conductor=False
    cfg.enable_articulation_director=ns.articulations!='off';cfg.apply_articulation_triggers=ns.articulations=='apply'
    if ns.no_safe_voice_upgrades:cfg.auto_apply_safe_voice_upgrades=False
    cfg.hardware_calibration_path=ns.hardware_calibration;cfg.voice_hardware_whitelist_path=ns.voice_whitelist
    cfg.enable_performance_director=ns.performance!='off';cfg.apply_performance_director=ns.performance=='apply'
    cfg.voice_aesthetic=ns.aesthetic;cfg.hardware_evidence_path=ns.hardware_evidence
    mix_policy='shadow' if ns.mix_fx=='apply' and ns.mode=='preserve' else ns.mix_fx
    cfg.mix_fx_policy=mix_policy;cfg.enable_mix_fx_director=mix_policy!='off';cfg.apply_mix_fx_director=mix_policy=='apply'
    apply_export_preset(cfg,ns.export_preset)
    if ns.test_full_optimization:cfg.enable_full_optimization_test()
    if ns.factory_gold_max:
        cfg.enable_autonomous_baja_max();cfg.autopilot=False;cfg.mode='max';cfg.export_preset='auto'
        cfg.velocity_factory_data_only=True;cfg.factory_gold_max=True
    rep=Optimizer(cfg).optimize(ns.input,ns.output,ns.report)
    if ns.session:
        session=WorkstationSession(ns.session);variant=session.record_variant(ns.input,ns.output,ns.report,asdict(cfg),ns.variant_label,build_mixer_snapshot(rep))
        if ns.audio_reference:session.attach_audio(ns.audio_reference,variant['id'])
        print('Session:',session.path,'Active variant:',variant['id'])
    print('PASS: %s -> %s' % (ns.input,ns.output)); print('Content type:',rep.content_type,rep.content_detection)
    print('AUTO PILOT:',rep.automation_decision)
    print('MIDI Doctor:',rep.midi_repair)
    print('Compatibility:',rep.compatibility)
    print('Velocity Conductor:',rep.velocity_conductor)
    print('Articulations:',rep.articulations)
    print('Musical understanding:',rep.musical_understanding)
    print('Musician workflow:\n'+render_dashboard(rep.musician_workflow))
    print('Performance Director:',rep.performance_director)
    print('Hardware evidence:',rep.hardware_evidence)
    print('Mix & FX Director:',rep.mix_fx_director)
    print('Audition queue:',rep.audition_queue)
    print('Workstation:',rep.workstation)
    print('Authority ledger:',rep.authority_ledger)
    print('Final quality gate:',rep.quality_gate)
    print('Changes:',len(rep.changes)); print('Warnings:',len(rep.warnings)); print('Verifier:',rep.verifier)

if __name__=='__main__': main()
