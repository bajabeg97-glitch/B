from dataclasses import dataclass

@dataclass
class OptimizeConfig:
    velocity_strength: float = 0.55
    velocity_random_strength: float = 0.55
    timing_strength: float = 0.45
    gate_strength: float = 0.35
    seed: int = 800
    protect_rx_low_velocity: bool = True
    protect_rx_special_pitch: bool = True
    enable_velocity: bool = True
    enable_timing: bool = True
    enable_gate: bool = True
    preserve_controllers: bool = True
    content_type: str = 'auto'
    use_factory_velocity_semantics: bool = True
    enable_sound_kit_selector: bool = True
    apply_high_confidence_sound_changes: bool = False
    enable_fx_intelligence: bool = True
    apply_existing_fx_sends: bool = False
    mode: str = 'live'
    autopilot: bool = False
    smart_policy_override: str | None = None
    enable_midi_repair: bool = True
    enable_velocity_conductor: bool = True
    velocity_conductor_strength: float = 0.88
    velocity_conductor_max_delta: int = 30
    enable_articulation_director: bool = True
    apply_articulation_triggers: bool = False
    auto_apply_safe_voice_upgrades: bool = True
    hardware_calibration_path: str | None = None
    velocity_min_iqr_retention: float = 0.75
    drum_key_min_hits: int = 100
    drum_key_min_styles: int = 3
    voice_hardware_whitelist_path: str | None = None
    enable_performance_director: bool = True
    apply_performance_director: bool = False
    hardware_evidence_path: str | None = None
    voice_aesthetic: str = 'original'
    enable_mix_fx_director: bool = True
    apply_mix_fx_director: bool = False
    mix_fx_policy: str = 'auto'
    export_preset: str = 'auto'
    require_style_import_contract: bool = False
    musical_preset: str = 'custom'
    vocal_friendly_mode: bool = False
    live_performance_mode: bool = False
    creative_policy: str = 'off'
    test_full_optimization: bool = False
    velocity_factory_data_only: bool = True
    enable_rhythm_trill_correction: bool = True
    apply_trained_rhythm_model: bool = False
    trained_rhythm_model_path: str | None = None
    trained_rhythm_only: bool = False
    factory_gold_max: bool = False
    apply_baja_stage_profile: bool = False
    ai_resource_policy: str = 'auto'

    def lock_preserve(self):
        """Apply strict preservation: analysis is allowed, mutation is not."""
        self.mode='preserve';self.export_preset='preserve';self.autopilot=False
        self.velocity_strength=0.0;self.velocity_random_strength=0.0;self.timing_strength=0.0;self.gate_strength=0.0
        self.enable_velocity=False;self.enable_timing=False;self.enable_gate=False
        self.enable_midi_repair=False;self.enable_velocity_conductor=False
        self.apply_trained_rhythm_model=False;self.trained_rhythm_only=False
        self.velocity_conductor_strength=0.0;self.velocity_conductor_max_delta=0
        self.smart_policy_override='suggest';self.apply_high_confidence_sound_changes=False;self.apply_existing_fx_sends=False;self.preserve_controllers=True
        self.auto_apply_safe_voice_upgrades=False;self.apply_articulation_triggers=False;self.apply_performance_director=False;self.mix_fx_policy='shadow';self.apply_mix_fx_director=False
        return self

    def enable_full_optimization_test(self):
        """Explicit audition mode: enable every non-destructive apply path.

        This deliberately bypasses conservative *suggest-only* defaults, but
        retains MIDI structural validation, rollback, identity-conflict,
        RX/DNC, special-pitch and verifier protections.
        """
        self.test_full_optimization=True;self.factory_gold_max=True;self.apply_baja_stage_profile=True;self.mode='max';self.export_preset='auto';self.autopilot=False
        self.velocity_strength=.90;self.velocity_random_strength=.85;self.timing_strength=.75;self.gate_strength=.65
        self.enable_velocity=True;self.enable_timing=True;self.enable_gate=True;self.enable_midi_repair=True;self.enable_velocity_conductor=True
        self.velocity_conductor_strength=.97;self.velocity_conductor_max_delta=36
        self.enable_sound_kit_selector=True;self.enable_fx_intelligence=True;self.smart_policy_override='apply';self.apply_high_confidence_sound_changes=True;self.apply_existing_fx_sends=True;self.preserve_controllers=False
        self.enable_articulation_director=True;self.apply_articulation_triggers=True;self.auto_apply_safe_voice_upgrades=True
        self.enable_performance_director=True;self.apply_performance_director=True;self.enable_mix_fx_director=True;self.apply_mix_fx_director=True;self.mix_fx_policy='apply'
        self.vocal_friendly_mode=False;self.live_performance_mode=False;self.creative_policy='off'
        return self

    def enable_autonomous_baja_max(self):
        """User-authorized autonomous MAX mode with fail-closed per-file policy.

        Keeps the BAJA/Factory/Gold/neural authorities enabled, while allowing
        the automation layer to reduce or preserve unsafe/low-evidence files.
        Resource governance remains independent via ai_resource_policy=auto.
        """
        self.enable_full_optimization_test()
        self.autopilot=True
        self.ai_resource_policy='auto'
        # R11: the bundled accepted encoder is an advisor only.  It may emit
        # timing/gate proposals, while Factory/Gold + verifier retain authority.
        self.apply_trained_rhythm_model=True
        self.trained_rhythm_only=False
        return self

    @classmethod
    def for_mode(cls, mode):
        m=(mode or 'live').lower()
        values = {
            'preserve': (0.00,0.00,0.00,0.00),
            'gentle':   (0.10,0.10,0.05,0.05),
            'natural':  (0.35,0.30,0.25,0.20),
            'live':     (0.55,0.55,0.45,0.35),
            'strong':   (0.75,0.70,0.60,0.50),
            'max':      (0.90,0.85,0.75,0.65),
            'auto':     (0.55,0.55,0.45,0.35),
        }
        if m not in values: raise ValueError('Unknown mode: %s' % mode)
        a,b,c,d=values[m]
        cfg=cls(a,b,c,d);cfg.mode=m;cfg.autopilot=(m=='auto')
        cfg.velocity_conductor_strength={'preserve':0.0,'gentle':0.20,'natural':0.82,'live':0.88,'strong':0.93,'max':0.97,'auto':0.88}[m]
        cfg.velocity_conductor_max_delta={'preserve':0,'gentle':8,'natural':28,'live':30,'strong':32,'max':36,'auto':30}[m]
        if m=='preserve':
            cfg.lock_preserve()
        return cfg

    @classmethod
    def for_musical_preset(cls,name):
        from .musician_workflow import MUSICAL_PRESETS,configure_musical_preset
        key=(name or 'custom').lower()
        if key not in MUSICAL_PRESETS:raise ValueError('Unknown musical preset: %s' % name)
        cfg=cls.for_mode(MUSICAL_PRESETS[key]['base_mode'])
        return configure_musical_preset(cfg,key)
