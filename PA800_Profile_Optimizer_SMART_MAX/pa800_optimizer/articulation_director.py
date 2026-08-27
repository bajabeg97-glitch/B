"""Exact Pa800 DNC articulation suggestions and explicit controller pulses."""
from __future__ import annotations

from collections import defaultdict
import mido

from .analysis.dnc_state import build_controller_states,tempo_events,ticks_to_ms
from .core.midi_io import absolute_track,rebuild_track
from .engines.performance_director import segment_phrases
from .hardware_evidence import HardwareEvidenceRegistry


class ArticulationDirector:
    def __init__(self,registry,evidence_path=None):self.registry=registry;self.hardware_evidence=HardwareEvidenceRegistry(evidence_path)

    @staticmethod
    def _candidate(note,prev,nxt,manual,state,ppq,tempos,phrase_context=None):
        arts=manual.get('articulations') or {};caps=set(manual.get('capabilities',[]));candidates=[]
        gap_ms=None;interval=None
        if prev is not None:
            gap_ms=ticks_to_ms(note.onset-prev.off,note.onset,ppq,tempos);interval=abs(note.note-prev.note)
        max_range=int((manual.get('legato') or {}).get('max_range_example_semitones',5))
        sc1=str(arts.get('sc1','')).lower();sc2=str(arts.get('sc2','')).lower()
        if 'sc1' in caps and 'slide' in sc1 and prev is not None and gap_ms is not None and -5<=gap_ms<=20 and 1<=interval<=max_range:
            candidates.append((80,'SC1',arts.get('sc1'),0.96,'documented_slide_on_close_legato_interval'))
        phrase_context=phrase_context or {};phrase_end=bool(phrase_context.get('position')=='END' or nxt is None or nxt.onset-note.off>=ppq//2)
        if 'sc2' in caps and 'fall' in sc2 and phrase_end and note.duration>=ppq//2:
            candidates.append((81,'SC2',arts.get('sc2'),0.93,'documented_fall_on_long_phrase_end'))
        if 'sc2' in caps and any(x in sc2 for x in ('growl','frullato')) and note.duration>=ppq and note.velocity>=90:
            candidates.append((81,'SC2',arts.get('sc2'),0.88,'documented_sustain_articulation_candidate'))
        if 'sc2' in caps and any(x in sc2 for x in ('mute','pizzicato')) and note.duration<=max(1,ppq//3) and note.velocity>=80:
            candidates.append((81,'SC2',arts.get('sc2'),0.86,'documented_short_articulation_candidate'))
        if not candidates:return None
        control,label,semantic,confidence,reason=max(candidates,key=lambda row:row[3])
        active=int((state or {}).get('cc%d'%control,0))>0
        return {'control':control,'controller':label,'semantic':semantic,'confidence':confidence,'reason':reason,'already_active':active,'gap_ms':None if gap_ms is None else round(gap_ms,3),'interval':interval,'phrase_position':phrase_context.get('position'),'phrase_index':phrase_context.get('phrase_index'),'repeated_note':bool(prev is not None and prev.note==note.note),'interval_direction':None if prev is None else ('UP' if note.note>prev.note else 'DOWN' if note.note<prev.note else 'REPEAT'),'accent_relative_to_phrase':round(note.velocity-float(phrase_context.get('velocity_median',note.velocity)),3)}

    def process(self,mid,contexts,notes,apply=False,max_per_context=16):
        by_context=defaultdict(list)
        for note in notes:by_context[(note.track_index,note.channel)].append(note)
        states=build_controller_states(mid);tempos=tempo_events(mid);rows=[];planned=[];rx_contexts=0;dnc_contexts=0
        for key,arr in by_context.items():
            ctx=contexts.get(key)
            if not ctx or ctx.identity.conflict:continue
            manual=self.registry.resolve_manual_dnc(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program)
            if not manual:
                if ctx.identity.rx_named:
                    profile,_status=self.registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role);ranges=(profile or {}).get('special_pitch_candidates',[]);special=[{'tick':note.onset,'note':note.note,'velocity':note.velocity} for note in arr if any(int(r.get('min',999))<=note.note<=int(r.get('max',-1)) for r in ranges)]
                    rows.append({'track':ctx.track_index,'channel':ctx.channel+1,'sound':ctx.identity.name,'address':list(ctx.identity.address()),'evidence_level':'E2','capabilities':['factory_rx_special_pitch_preserve'],'automatic_sound_noise':['rx_internal_or_special_pitch_existing_only'],'suggestions':[],'existing_special_events':special[:64],'existing_special_event_count':len(special),'applied':0,'policy':'preserve_existing_rx'});rx_contexts+=1
                continue
            dnc_contexts+=1
            arr.sort(key=lambda note:(note.onset,note.note));suggestions=[];last_tick=-10**12
            phrase_map={}
            for phrase_index,phrase in enumerate(segment_phrases(arr,mid.ticks_per_beat)):
                velocity_median=sorted(n.velocity for n in phrase)[len(phrase)//2]
                for phrase_pos,phrase_note in enumerate(phrase):phrase_map[phrase_note.on_index]={'phrase_index':phrase_index,'position':'START' if phrase_pos==0 else 'END' if phrase_pos==len(phrase)-1 else 'BODY','velocity_median':velocity_median}
            for index,note in enumerate(arr):
                prev=arr[index-1] if index else None;nxt=arr[index+1] if index+1<len(arr) else None
                candidate=self._candidate(note,prev,nxt,manual,states.get((note.track_index,note.on_index)),mid.ticks_per_beat,tempos,phrase_map.get(note.on_index))
                if not candidate:continue
                approval=self.hardware_evidence.articulation_approval(ctx.identity.address(),candidate['control'],candidate['semantic']);documented_safe=bool((candidate['control']==80 and 'slide' in str(candidate['semantic']).lower()) or (candidate['control']==81 and 'fall' in str(candidate['semantic']).lower()));evidence='E3' if approval and approval['approval'] in ('safe-auto','auto') else 'E2'
                item={'track':note.track_index,'channel':note.channel+1,'tick':note.onset,'note':note.note,**candidate,'evidence_level':evidence,'hardware_approval':None if not approval else approval['approval'],'action':'EXISTING_ACTIVE' if candidate['already_active'] else 'SUGGEST'}
                authorized=bool(documented_safe or evidence=='E3')
                minimum_confidence=.86 if evidence=='E3' else .90
                if apply and authorized and not candidate['already_active'] and candidate['confidence']>=minimum_confidence and len(planned)<1000 and note.onset-last_tick>=max(1,mid.ticks_per_beat//4):
                    item['action']='APPLY';planned.append({'track':note.track_index,'channel':note.channel,'tick':note.onset,'event_index':note.on_index,'control':candidate['control'],'note':note.note,'occurrence':note.occurrence});last_tick=note.onset
                elif apply and not authorized:item['action']='BLOCKED_REQUIRES_HARDWARE_E3'
                suggestions.append(item)
                if len(suggestions)>=max_per_context:break
            caps=set(manual.get('capabilities',[]));rows.append({'track':ctx.track_index,'channel':ctx.channel+1,'sound':manual['name'],'address':[manual['msb'],manual['lsb'],manual['program']],'evidence_level':'E2','capabilities':sorted(caps),'automatic_sound_noise':[name for name in ('key_on_noise','key_off_noise','rx_noise','damper_trigger') if name in caps],'suggestions':suggestions,'applied':sum(x['action']=='APPLY' for x in suggestions),'policy':'apply' if apply else 'suggest'})
        insertions=[]
        for track_index,items in self._by_track(planned).items():
            events=absolute_track(mid.tracks[track_index])
            for item in items:
                events.append([item['tick'],item['event_index']-0.25,mido.Message('control_change',channel=item['channel'],control=item['control'],value=127,time=0)])
                events.append([item['tick'],item['event_index']+0.25,mido.Message('control_change',channel=item['channel'],control=item['control'],value=0,time=0)])
                insertions.extend([(track_index,item['channel'],item['tick'],item['control'],127,item['note'],item['occurrence']),(track_index,item['channel'],item['tick'],item['control'],0,item['note'],item['occurrence'])])
            mid.tracks[track_index]=rebuild_track(events)
        return {'enabled':True,'policy':'apply' if apply else 'suggest','phrase_aware':True,'hardware_evidence':self.hardware_evidence.summary(),'exact_dnc_contexts':dnc_contexts,'rx_preserve_contexts':rx_contexts,'applied_triggers':len(planned),'inserted_events':len(insertions),'contexts':rows},insertions

    @staticmethod
    def _by_track(items):
        out=defaultdict(list)
        for item in items:out[item['track']].append(item)
        return out