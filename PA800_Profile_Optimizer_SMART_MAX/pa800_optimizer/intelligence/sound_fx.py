from __future__ import annotations

from collections import defaultdict,Counter
from dataclasses import dataclass, asdict
import math
import re
import statistics
import json
from pathlib import Path
from ..hardware_evidence import HardwareEvidenceRegistry


def normalize_family(family, sound_name=''):
    """Split ambiguous legacy families into musically distinct classes."""
    fam=(family or 'UNKNOWN').upper()
    name=' '.join((sound_name or '').lower().split())
    if fam=='ACCORDION_REED':
        if re.search(r'\b(harmonica|mouth harp)\b', name):
            return 'HARMONICA'
        if re.search(r'accordion|accord\.|musette|bandoneon|bayan|fisarm', name):
            return 'ACCORDION'
        return 'REED'
    if fam=='REED' and re.search(r'\b(harmonica|mouth harp)\b', name):
        return 'HARMONICA'
    return fam


FX_PROFILES = {
    'DRUM_KIT': dict(reverb=20, chorus=0, chain='ROOM / DRUM AMBIENCE', notes='Kick dry-ish; snare/toms/cymbals receive more ambience via kit programming.'),
    'PERCUSSION': dict(reverb=18, chorus=0, chain='SMALL ROOM', notes='Short room; avoid washing transient detail.'),
    'BASS': dict(reverb=4, chorus=0, chain='COMP/EQ or AMP-CAB', notes='Keep low end centered and dry; FX only when sound profile benefits.'),
    'GUITAR': dict(reverb=18, chorus=12, chain='AMP/CAB -> CHORUS/ROOM', notes='Clean guitars may use chorus; distorted/power guitar stays tighter.'),
    'PIANO': dict(reverb=24, chorus=4, chain='EQ -> ROOM/HALL', notes='Moderate room/hall; preserve attack.'),
    'ORGAN': dict(reverb=18, chorus=8, chain='ROTARY/CHORUS -> ROOM', notes='Prefer rotary/organ modulation where applicable.'),
    'ACCORDION': dict(reverb=20, chorus=5, chain='EQ -> ROOM/PLATE', notes='Accordion: short-medium room/plate; keep reeds articulate.'),
    'HARMONICA': dict(reverb=22, chorus=2, chain='EQ/AMP -> PLATE/DELAY', notes='Harmonica is separate from accordion; expressive lead treatment.'),
    'REED': dict(reverb=22, chorus=2, chain='EQ -> PLATE/ROOM', notes='Clarinet/oboe/sax-style reed line; preserve breath and phrasing.'),
    'PIPE': dict(reverb=25, chorus=3, chain='EQ -> HALL', notes='Airy winds tolerate slightly longer ambience.'),
    'STRINGS': dict(reverb=30, chorus=10, chain='ENSEMBLE -> HALL', notes='Wider hall/ensemble but retain headroom.'),
    'ENSEMBLE': dict(reverb=30, chorus=10, chain='ENSEMBLE -> HALL', notes='Background ensemble profile.'),
    'BRASS': dict(reverb=20, chorus=1, chain='EQ -> ROOM/PLATE', notes='Keep attacks forward; moderate ambience.'),
    'SYNTH_LEAD': dict(reverb=20, chorus=8, chain='MOD/DELAY -> REVERB', notes='Tempo-aware delay recommendation for lead parts.'),
    'SYNTH_PAD': dict(reverb=34, chorus=14, chain='CHORUS -> HALL', notes='Wide, soft background FX; protect mix headroom.'),
    'CHROMATIC_PERC': dict(reverb=24, chorus=5, chain='ROOM/PLATE', notes='Mallet/chromatic percussion profile.'),
    'ETHNIC': dict(reverb=20, chorus=2, chain='ROOM', notes='Conservative; preserve instrument identity.'),
    'PERCUSSIVE': dict(reverb=16, chorus=0, chain='SMALL ROOM', notes='Transient-first profile.'),
    'SFX': dict(reverb=12, chorus=0, chain='PRESERVE', notes='Do not reshape unknown/SFX material aggressively.'),
    'UNKNOWN': dict(reverb=0, chorus=0, chain='PRESERVE', notes='Unknown identity: no automatic FX rewrite.'),
}



def fx_profile_for(family, sound_name='', role=''):
    fam=normalize_family(family,sound_name)
    fx=dict(FX_PROFILES.get(fam,FX_PROFILES['UNKNOWN']))
    name=(sound_name or '').lower()
    role=(role or '').upper()
    fx['delay_hint']='NONE'
    fx['pa800_routing_hint']='Shared ambience; keep instrument-specific processing conservative.'
    if fam=='GUITAR':
        if any(x in name for x in ('dist','overdrive','power','mute','rock')):
            fx.update(reverb=9,chorus=0,chain='AMP/CAB -> SHORT ROOM',delay_hint='SHORT/SLAP only for lead',pa800_routing_hint='Prefer tighter guitar processing; avoid shared wash.')
        elif any(x in name for x in ('clean','funk','nylon','steel','jazz')):
            fx.update(reverb=18,chorus=14,chain='AMP/CAB -> CHORUS -> ROOM',delay_hint='Tempo delay only for lead/riff')
    elif fam=='BASS':
        if 'synth' in name: fx.update(reverb=3,chorus=2,chain='COMP/EQ -> FILTER',delay_hint='NONE')
        else: fx.update(reverb=3,chorus=0,chain='COMP/EQ -> AMP/CAB',delay_hint='NONE')
    elif fam=='PIANO':
        if any(x in name for x in ('electric','ep','tine','wurli')):
            fx.update(reverb=20,chorus=10,chain='EQ -> CHORUS/TREMOLO -> ROOM',delay_hint='Optional short stereo delay')
    elif fam=='ORGAN':
        fx.update(reverb=16,chorus=6,chain='ROTARY -> EQ -> ROOM',delay_hint='NONE',pa800_routing_hint='Rotary/modulation before shared ambience when available.')
    elif fam=='ACCORDION':
        if 'musette' in name: fx.update(reverb=18,chorus=3,chain='EQ -> SHORT ROOM',delay_hint='NONE')
        else: fx.update(reverb=20,chorus=2,chain='EQ -> ROOM/PLATE',delay_hint='Very short only for solo')
    elif fam=='HARMONICA':
        fx.update(reverb=22,chorus=0,chain='EQ/AMP -> PLATE',delay_hint='Short tempo/slap delay for lead')
    elif fam in ('REED','PIPE','BRASS') and ('SOLO' in role or 'LEAD' in role):
        fx['delay_hint']='Low-feedback tempo delay; keep phrase clear'
    elif fam=='SYNTH_LEAD':
        fx['delay_hint']='Tempo-synced delay candidate'
    elif fam in ('STRINGS','ENSEMBLE','SYNTH_PAD'):
        fx['pa800_routing_hint']='Prefer shared hall/ensemble; keep sends below lead and rhythm foundation.'
    elif fam=='DRUM_KIT':
        fx['pa800_routing_hint']='Per-key kit sends are preferred: kick dry, snare/toms/cymbals progressively wetter.'
    if role in ('BASS','DRUM','PERC'):
        fx['delay_hint']='NONE'
    return fx

ROLE_FAMILY_BONUS = {
    'DRUM': {'DRUM_KIT': 18}, 'PERC': {'DRUM_KIT': 10, 'PERCUSSION': 18, 'PERCUSSIVE': 12},
    'BASS': {'BASS': 18},
}

VOICE_THRESHOLDS={
    'PIANO':(.90,6.0,8.0),'BASS':(.90,6.0,8.0),'GUITAR':(.88,6.0,6.0),'BRASS':(.90,6.0,8.0),
    'STRINGS':(.92,7.0,9.0),'ENSEMBLE':(.92,7.0,9.0),'ACCORDION':(.91,7.0,9.0),'REED':(.91,7.0,9.0),
    'PIPE':(.92,7.0,10.0),'ORGAN':(.92,7.0,10.0),'SYNTH_PAD':(.94,8.0,11.0),'SYNTH_LEAD':(.95,8.0,12.0),
    'DRUM_KIT':(.97,10.0,14.0),'UNKNOWN':(.99,99.0,99.0),
}

@dataclass
class Recommendation:
    track: int
    channel: int
    role: str
    family: str
    current_address: tuple
    current_sound: str | None
    candidate_address: tuple | None
    candidate_sound: str | None
    current_score: float | None
    improvement: float | None
    score: float
    margin: float
    confidence: float
    support_grade: str
    support_styles: int
    stability: str
    auto_gate: str
    action: str
    reason: str
    fx: dict
    aesthetic: str = 'original'
    aesthetic_score: float = 0.0
    evidence_level: str = 'E1'
    hardware_approval: str | None = None

    def to_dict(self):
        return asdict(self)


class SoundFxIntelligence:
    """Factory-informed conservative Sound/Kit + FX recommendation engine.

    It can apply a Sound change only when the target address can be rewritten
    without inventing missing Bank Select events and the candidate clears a
    strong confidence/margin gate. FX applies only to existing CC91/CC93 events;
    deeper Pa800 insert/master routing stays recommendation-only unless a future
    verified Korg-specific writer is supplied.
    """
    def __init__(self, registry, config=None):
        self.registry=registry
        self.config=config
        self.aesthetic=str(getattr(config,'voice_aesthetic','original') or 'original').lower()
        if self.aesthetic not in ('original','natural','modern'):self.aesthetic='original'
        self.hardware_evidence=HardwareEvidenceRegistry(getattr(config,'hardware_evidence_path',None) if config else None)
        self.hardware_targets=set()
        path=getattr(config,'voice_hardware_whitelist_path',None) if config else None
        if path:
            try:
                data=json.loads(Path(path).read_text(encoding='utf-8'))
                for row in data.get('approved_targets',[]):self.hardware_targets.add(tuple(int(x) for x in row['address']))
            except Exception:self.hardware_targets=set()
        self.by_family=defaultdict(list)
        for profile in registry.profiles:
            identity=profile.get('identity',{})
            family=normalize_family(identity.get('org_family'),identity.get('sound'))
            self.by_family[family].append(profile)

    @staticmethod
    def _name_tokens(name):
        return {token for token in re.findall(r'[a-z0-9]+',(name or '').lower()) if token not in {'gm','rx','rx1','rx2','rx3','dnc','sound','gtr','guitar','the'}}

    def _aesthetic_score(self,profile,ctx):
        ident=profile.get('identity',{});target_name=str(ident.get('sound') or '');source_name=str(ctx.identity.name or '');target_tokens=self._name_tokens(target_name);source_tokens=self._name_tokens(source_name);score=0.0
        if self.aesthetic=='original':
            # Compatibility baseline: established Factory ranking and its
            # hardware approvals must not move merely because the 1.5 UI now
            # exposes aesthetic choices. "Original" therefore adds no
            # timbral preference score; conservative authorization gates still
            # protect the current voice.
            score=0.0
        elif self.aesthetic=='natural':
            if not any(word in target_name.lower() for word in ('synth','analog','digital','wave','techno','dance','vox')):score+=4.0
            if any(word in target_name.lower() for word in ('acoustic','grand','natural','classic','nylon','steel','finger','studio')):score+=2.0
        elif self.aesthetic=='modern':
            score+=sum(1.5 for word in ('stereo','wide','pro','modern','bright','studio','clear','power') if word in target_name.lower())
            score+=min(3.0,math.log10(max(1,int((profile.get('support') or {}).get('notes',1)))))
        return score

    @staticmethod
    def _profile_range(profile):
        k=profile.get('key') or {}
        return float(k.get('working_min',0)), float(k.get('working_max',127)), float(k.get('ideal_center',64))

    @staticmethod
    def _observed_range(notes):
        if not notes:return 0.0,127.0,64.0
        vals=[n.note for n in notes]
        return float(min(vals)),float(max(vals)),sum(vals)/len(vals)

    @staticmethod
    def _overlap(a0,a1,b0,b1):
        inter=max(0.0,min(a1,b1)-max(a0,b0)+1.0)
        union=max(a1,b1)-min(a0,b0)+1.0
        return inter/max(1.0,union)

    @staticmethod
    def channel_features(mid,ctx):
        tick=0;controllers=Counter();fx_values={91:[],93:[]};level_values={7:[],11:[]};pitch_bend=aftertouch=0
        for msg in mid.tracks[ctx.track_index]:
            tick+=int(msg.time)
            if getattr(msg,'channel',None)!=ctx.channel:continue
            if msg.type=='control_change':
                controllers[msg.control]+=1
                if msg.control in fx_values:fx_values[msg.control].append(msg.value)
                if msg.control in level_values:level_values[msg.control].append(msg.value)
            elif msg.type=='pitchwheel' and getattr(msg,'pitch',0):pitch_bend+=1
            elif msg.type in ('aftertouch','polytouch'):aftertouch+=1
        return {'ticks_per_beat':mid.ticks_per_beat,'track_end_tick':tick,'controllers':dict(controllers),'pitch_bend_events':pitch_bend,'aftertouch_events':aftertouch,'existing_fx':fx_values,'level_values':level_values}

    def _controller_match(self,profile,features):
        if not features:return 0.0,[]
        i=profile['identity'];factory=self.registry.controller_profile(i.get('msb'),i.get('lsb'),i.get('program')) if hasattr(self.registry,'controller_profile') else None
        if not factory:return 0.0,[]
        counts=factory.get('counts',{});observed=[];score=0.0
        for cc,weight in ((1,2.0),(64,2.0),(11,1.0),(7,0.5)):
            if features.get('controllers',{}).get(cc):
                observed.append('CC%d'%cc)
                if counts.get('cc:%d'%cc):score+=weight
        if features.get('pitch_bend_events'):
            observed.append('PB')
            if counts.get('pb:None'):score+=2.0
        return min(6.0,score),observed

    @staticmethod
    def _safe_gm_upgrade(ctx, profile, improvement, margin, confidence):
        """Return True only for a timbre-preserving GM-bank upgrade.

        The program number must stay identical, so Piano cannot silently become
        Clav, Steel Guitar cannot become Nylon Guitar, and Strings cannot become
        a synth ensemble merely because their statistical envelopes look alike.
        Drum kits are excluded until per-key hardware audition confirms mapping.
        """
        ident=profile.get('identity',{})
        current=ctx.identity.address()
        target=(ident.get('msb'),ident.get('lsb'),ident.get('program'))
        if None in current or None in target:return False
        if current[0]!=121 or current[1]!=0:return False
        if current[2]!=target[2]:return False
        if normalize_family(ctx.family,ctx.identity.name)=='DRUM_KIT':return False
        if ident.get('rx_named') or ident.get('dnc_named'):return False
        return improvement>=10.0 and margin>=7.0 and confidence>=0.95

    def _score(self, profile, ctx, notes,features=None):
        ident=profile['identity']
        fam=normalize_family(ident.get('org_family'),ident.get('sound'))
        score=42.0
        if fam==normalize_family(ctx.family,ctx.identity.name): score+=22.0
        prole=ident.get('role')
        if prole==ctx.role:score+=12.0
        score+=ROLE_FAMILY_BONUS.get(ctx.role,{}).get(fam,0)
        score+=self._aesthetic_score(profile,ctx)
        o0,o1,oc=self._observed_range(notes); p0,p1,pc=self._profile_range(profile)
        score+=15.0*self._overlap(o0,o1,p0,p1)
        score+=max(0.0,8.0-min(8.0,abs(oc-pc)/3.0))
        if notes:
            vcenter=statistics.median(n.velocity for n in notes);pv=float((profile.get('velocity') or {}).get('ideal_center',vcenter))
            score+=max(0.0,6.0-min(6.0,abs(vcenter-pv)/5.0))
            dcenter=max(1.0,statistics.median(max(1,n.duration) for n in notes));pd=max(1.0,float((profile.get('duration_ticks') or {}).get('ideal_center',dcenter)))
            score+=max(0.0,6.0-min(6.0,abs(math.log2(dcenter/pd))*2.5))
            tpb=max(1,int((features or {}).get('ticks_per_beat',192)));span=max(tpb,max(n.off for n in notes)-min(n.onset for n in notes));density=len(notes)/(span/tpb)
            factory_density=float((profile.get('notes_per_bar') or {}).get('ideal_center',density*4) or density*4)/4.0
            score+=max(0.0,5.0-min(5.0,abs(math.log2(max(.1,density)/max(.1,factory_density)))*2.0))
            chord_counts=Counter(n.onset for n in notes);poly=statistics.mean(chord_counts.values());factory_poly=float((profile.get('exact_onset_chord_size') or {}).get('ideal_center',poly) or poly)
            score+=max(0.0,4.0-min(4.0,abs(poly-factory_poly)*1.5))
        if ctx.element and ctx.element in (profile.get('elements') or {}):score+=2.0
        if ctx.cv is not None and any(int(row[0])==int(ctx.cv) for row in (profile.get('cvs') or [])):score+=1.0
        cmatch,_observed=self._controller_match(profile,features);score+=cmatch
        sup=profile.get('support',{})
        score+=min(8.0, math.log10(max(1,int(sup.get('notes',1))))*1.8)
        if ident.get('rx_named'): score+=2.5
        if ident.get('dnc_named'): score+=1.5
        # Drum kit candidates need observed note coverage from per-key Factory profiles.
        if ctx.role in ('DRUM','PERC') or fam=='DRUM_KIT':
            used={n.note for n in notes}
            if used:
                address=(ident.get('msb'),ident.get('lsb'),ident.get('program'))
                covered=sum(1 for key in used if self.registry.resolve_drum_key(*address,key))
                score+=18.0*(covered/len(used))
        return score

    @staticmethod
    def _adapt_fx(fx,ctx,notes,features):
        fx=dict(fx);reverb=int(fx.get('reverb',0));chorus=int(fx.get('chorus',0));adjust=[]
        if notes:
            tpb=max(1,int((features or {}).get('ticks_per_beat',192)))
            span=max(tpb,max(n.off for n in notes)-min(n.onset for n in notes));density=len(notes)/(span/tpb)
            duration=statistics.median(max(1,n.duration) for n in notes)/tpb
            onset_counts=Counter(n.onset for n in notes);chord_fraction=sum(v for v in onset_counts.values() if v>1)/len(notes)
            if density>=8:reverb-=9;chorus-=4;adjust.append('dense_texture_dry')
            elif density>=4:reverb-=5;chorus-=2;adjust.append('busy_texture_control')
            elif density<=1.5:reverb+=2;adjust.append('sparse_texture_space')
            if duration<0.16:reverb-=3;adjust.append('short_articulation_clarity')
            elif duration>1.0:reverb+=2;adjust.append('sustained_texture_space')
            if chord_fraction>0.55:chorus-=2;adjust.append('polyphonic_width_guard')
            fx['context_metrics']={'density_notes_per_beat':round(density,3),'median_duration_beats':round(duration,3),'chord_note_fraction':round(chord_fraction,3)}
        if ctx.role=='BASS':reverb=min(reverb,6);chorus=min(chorus,2);adjust.append('bass_foundation_cap')
        elif ctx.role in ('DRUM','PERC'):reverb=min(reverb,20);chorus=0;adjust.append('rhythm_foundation_cap')
        elif ctx.role in ('ACC4','ACC5'):reverb+=2;adjust.append('background_depth')
        if (features or {}).get('pitch_bend_events') or (features or {}).get('aftertouch_events'):
            chorus-=2;adjust.append('expressive_lead_clarity')
        levels=(features or {}).get('level_values',{});cc7=statistics.median(levels.get(7) or [100]);cc11=statistics.median(levels.get(11) or [127]);energy=math.sqrt(max(.01,(cc7/100.0)*(cc11/127.0)))
        if energy<.72:reverb-=3;chorus-=2;adjust.append('low_effective_energy_clarity')
        elif energy>1.03:reverb-=2;adjust.append('high_effective_energy_headroom')
        fx['reverb']=max(0,min(48,int(round(reverb))));fx['chorus']=max(0,min(32,int(round(chorus))))
        existing=(features or {}).get('existing_fx',{91:[],93:[]})
        fx['existing_send_events']={'cc91':len(existing.get(91,[])),'cc93':len(existing.get(93,[]))}
        fx['effective_energy_inputs']={'cc7_median':cc7,'cc11_median':cc11,'scale':round(energy,4)}
        fx['dynamic_adjustments']=adjust;fx['basis']='expert_family_rule+observed_musical_context';fx['factory_cc91_cc93_evidence']='not_observed_in_factory_corpus'
        return fx

    def recommend(self, ctx, notes,features=None):
        fam=normalize_family(ctx.family,ctx.identity.name)
        candidates=list(self.by_family.get(fam,[]))
        # PERC role can legitimately use Drum Kit profiles too.
        if ctx.role=='PERC' and fam!='DRUM_KIT': candidates += self.by_family.get('DRUM_KIT',[])
        if not candidates:
            fx=fx_profile_for(fam,ctx.identity.name,ctx.role)
            fx=self._adapt_fx(fx,ctx,notes,features)
            return Recommendation(ctx.track_index,ctx.channel+1,ctx.role,fam,ctx.identity.address(),ctx.identity.name,None,None,None,None,0,0,0,'NONE',0,'UNKNOWN','missing_profile','PRESERVE','No same-family Factory candidate.',fx,aesthetic=self.aesthetic,aesthetic_score=0.0,evidence_level='E0')
        ranked=sorted(((self._score(p,ctx,notes,features),p) for p in candidates),key=lambda x:x[0],reverse=True)
        overall_score,overall=ranked[0]; current=ctx.identity.address()
        overall_ident=overall['identity']; overall_target=(overall_ident.get('msb'),overall_ident.get('lsb'),overall_ident.get('program'))
        current_rows=[(score,p) for score,p in ranked if (p['identity'].get('msb'),p['identity'].get('lsb'),p['identity'].get('program'))==current]
        current_score=current_rows[0][0] if current_rows else None
        eligible=[(score,p) for score,p in ranked if self.registry.auto_candidate_allowed(p)[0]]
        selected=overall; selected_score=overall_score; action='SUGGEST_ONLY'
        gate_ok,gate_reason=self.registry.auto_candidate_allowed(overall)
        second=ranked[1][0] if len(ranked)>1 else 0.0
        margin=overall_score-second
        confidence=max(0.0,min(1.0,(overall_score-60.0)/45.0 + max(0.0,margin)/40.0))
        reason='Best same-family candidate is suggestion-only ('+gate_reason+').' 
        evidence_level='E2';hardware_approval=None
        if current==overall_target:
            action='KEEP_BEST'; reason='Current exact Sound/Kit is already the strongest Factory match.'
        elif eligible and current_score is not None and str(ctx.resolution_status).startswith('EXACT') and not ctx.identity.conflict and not (ctx.identity.rx_named or ctx.identity.dnc_named):
            auto_score,auto=eligible[0]; auto_second=eligible[1][0] if len(eligible)>1 else 0.0
            auto_margin=auto_score-auto_second
            auto_confidence=max(0.0,min(1.0,(auto_score-60.0)/45.0 + max(0.0,auto_margin)/40.0))
            evidence_gap=overall_score-auto_score
            improvement=auto_score-current_score
            min_conf,min_margin,min_improvement=VOICE_THRESHOLDS.get(fam,VOICE_THRESHOLDS['UNKNOWN'])
            if auto_confidence>=min_conf and auto_margin>=min_margin and evidence_gap<=2.0 and improvement>=min_improvement:
                selected=auto; selected_score=auto_score; margin=auto_margin; confidence=auto_confidence
                gate_ok,gate_reason=self.registry.auto_candidate_allowed(auto)
                if self._safe_gm_upgrade(ctx,auto,improvement,auto_margin,auto_confidence):
                    action='SAFE_GM_UPGRADE'
                    reason='Safe GM-to-Pa800 upgrade keeps the exact program class and improves Factory fit by %.2f points.' % improvement
                else:
                    target=tuple(auto['identity'].get(x) for x in ('msb','lsb','program'))
                    approval=self.hardware_evidence.voice_approval(current,target,fam,self.aesthetic)
                    legacy_approved=target in self.hardware_targets
                    registry_approved=bool(approval and approval.get('approval') in ('safe-auto','auto'))
                    if legacy_approved or registry_approved:
                        action='AUTO_CANDIDATE'; reason='Evidence-gated Factory match improves current fit by %.2f points and clears the stability/margin corridor.' % improvement
                        evidence_level='E3';hardware_approval='legacy-target-whitelist' if legacy_approved else approval.get('approval')
                    else:
                        action='SUGGEST_ONLY';reason='Statistical candidate clears family thresholds but has no E3 safe-auto/auto hardware approval.'
        elif ctx.identity.rx_named or ctx.identity.dnc_named:
            reason='RX/DNC identity is protected: recommendation only, never automatic Sound rewrite.'
        ident=selected['identity']; target=(ident.get('msb'),ident.get('lsb'),ident.get('program'))
        support=selected.get('support',{}); grade=str(support.get('grade','UNKNOWN')); styles=int(support.get('styles',0))
        stability=self.registry.profile_stability(selected)
        candidate_action=action in ('AUTO_CANDIDATE','SAFE_GM_UPGRADE')
        fx_sound=(ident.get('sound') if candidate_action else ctx.identity.name) or ident.get('sound')
        fx=fx_profile_for(fam,fx_sound,ctx.role);fx=self._adapt_fx(fx,ctx,notes,features);fx['sound_basis']='candidate_sound' if candidate_action else 'current_sound'
        controller_match,observed_controls=self._controller_match(selected,features);fx['factory_controller_match_score']=round(controller_match,2);fx['observed_expression_inputs']=observed_controls
        improvement=None if current_score is None else selected_score-current_score
        return Recommendation(ctx.track_index,ctx.channel+1,ctx.role,fam,current,ctx.identity.name,target,ident.get('sound'),None if current_score is None else round(current_score,2),None if improvement is None else round(improvement,2),round(selected_score,2),round(margin,2),round(confidence,3),grade,styles,stability,gate_reason,action,reason,fx,aesthetic=self.aesthetic,aesthetic_score=round(self._aesthetic_score(selected,ctx),3),evidence_level=evidence_level,hardware_approval=hardware_approval)

    @staticmethod
    def _channel_event_presence(track, channel):
        has0=has32=haspc=0
        for msg in track:
            if getattr(msg,'channel',None)!=channel:continue
            if msg.type=='control_change' and msg.control==0:has0+=1
            elif msg.type=='control_change' and msg.control==32:has32+=1
            elif msg.type=='program_change':haspc+=1
        return has0,has32,haspc

    def apply_sound(self, mid, ctx, rec):
        if rec.action not in ('AUTO_CANDIDATE','SAFE_GM_UPGRADE') or not rec.candidate_address:return False,'not_auto_candidate'
        if tuple(rec.candidate_address) in self.registry.conflicts:return False,'target_identity_conflict'
        ti=ctx.track_index; ch=ctx.channel; track=mid.tracks[ti]
        has0,has32,haspc=self._channel_event_presence(track,ch)
        msb,lsb,pc=rec.candidate_address
        # Never invent address events: this protects Format-1/StyleWorks and unknown layouts.
        if not (has0 and has32 and haspc):return False,'missing_existing_bank_or_program_events'
        # StyleWorks and several real Pa800 Song exports repeat Bank Select
        # setup messages, but retain one Program Change. This is one voice state,
        # not multiple instruments. Multiple Program Changes remain blocked.
        if haspc!=1:return False,'ambiguous_multiple_program_events'
        changed=False
        for i,msg in enumerate(track):
            if getattr(msg,'channel',None)!=ch:continue
            if msg.type=='control_change' and msg.control==0 and msg.value!=msb:
                track[i]=msg.copy(value=int(msb)); changed=True
            elif msg.type=='control_change' and msg.control==32 and msg.value!=lsb:
                track[i]=msg.copy(value=int(lsb)); changed=True
            elif msg.type=='program_change' and msg.program!=pc:
                track[i]=msg.copy(program=int(pc)); changed=True
        if not changed:return False,'already_target'
        status='applied_redundant_bank_sequence' if has0>1 or has32>1 else 'applied'
        return True,status

    @staticmethod
    def apply_fx_sends(mid, ctx, rec, mutation_log=None):
        if rec.family in ('UNKNOWN','SFX'):return 0
        track=mid.tracks[ctx.track_index]; ch=ctx.channel
        targets={91:int(rec.fx.get('reverb',0)),93:int(rec.fx.get('chorus',0))}
        count=0;events=defaultdict(list);tick=0;occurrences=defaultdict(int)
        for i,msg in enumerate(track):
            tick+=int(msg.time)
            if getattr(msg,'channel',None)==ch and msg.type=='control_change' and msg.control in targets:
                occurrence=occurrences[msg.control];occurrences[msg.control]+=1;events[msg.control].append((i,msg,tick,occurrence))
        for control,rows in events.items():
            # One bounded offset preserves every existing breakpoint and contour slope.
            center=statistics.median(msg.value for _,msg,_,_ in rows);delta=int(round((targets[control]-center)*.28));delta=max(-10,min(10,delta))
            for i,msg,event_tick,occurrence in rows:
                new=max(0,min(127,msg.value+delta))
                if new!=msg.value:
                    track[i]=msg.copy(value=new);count+=1
                    if mutation_log is not None:mutation_log.append({'track':ctx.track_index,'channel':ch,'control':control,'occurrence':occurrence,'tick':event_tick,'old':msg.value,'new':new,'source':'sound_fx_intelligence'})
        return count