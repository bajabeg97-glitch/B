"""Conservative PA800 RX/DNC safety policy.

Important controller distinction from Korg OS 2.0 manual:
- Sound Controller 1 = CC80
- Sound Controller 2 = CC81
- Joystick Y+ = CC1, threshold 64
- Joystick Y- = CC2, threshold 64
- Damper = CC64
- Channel Aftertouch trigger threshold = 90 when programmed by the Sound
"""
SENSITIVE_CCS={1,2,64,80,81}

from ..instruments.policies import policy_for


def special_pitch(profile,note):
    if not profile:return False
    for c in profile.get('special_pitch_candidates',[]):
        if int(c.get('min',999))<=note<=int(c.get('max',-1)): return True
    return False


def protect_note(note, ctx, profile, config, manual_dnc=None):
    if not ctx:return False,''
    if ctx.identity.conflict:return True,'identity_conflict'
    family=str(ctx.family or ctx.identity.family or 'UNKNOWN').upper();name=str(ctx.identity.name or '').lower();policy=policy_for(family)
    if family in ('SFX','SYNTH_FX'):return True,'sfx_identity_preserve'
    if any(token in name for token in ('cycle','random','wave sequence','wave seq')):return True,'cycle_random_identity_preserve'
    if policy.get('protect_special_pitch') and special_pitch(profile,note.note):return True,'instrument_special_pitch_candidate'
    if ctx.identity.rx_named:
        if config.protect_rx_special_pitch and special_pitch(profile,note.note): return True,'rx_special_pitch_candidate'
        if config.protect_rx_low_velocity and note.velocity<=20: return True,'rx_low_velocity_guard'
    if ctx.identity.dnc_named:
        if special_pitch(profile,note.note): return True,'dnc_special_pitch_candidate'
        caps=set((manual_dnc or {}).get('capabilities',[]))
        if caps & {'legato','staccato','key_on_noise','key_off_noise','rx_noise','damper_trigger','cycle','random'}:
            return True,'dnc_articulation_integrity_guard'
        # Manual explicitly says some DNC Sounds rely on complex velocity switching
        # or previous-note velocity conditions. Generic velocity shaping is unsafe.
        if 'velocity_switch_complex' in caps:return True,'dnc_velocity_switch_complex_guard'
        if 'velocity_condition' in caps:return True,'dnc_velocity_condition_guard'
    return False,''


def sensitive_controller(cc, ctx=None):
    if cc not in SENSITIVE_CCS:return False
    if ctx is None:return True
    return bool(ctx.identity.rx_named or ctx.identity.dnc_named)